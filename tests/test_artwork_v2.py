"""Artwork v2 framing, metadata priority, and explicit legacy fallback."""

import base64
import queue
import sys
import unittest
import zlib
from dataclasses import replace
from pathlib import Path
from threading import Event, Lock, RLock, Thread
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))

from engine import (ARTWORK_CHUNK_BYTES, ARTWORK_V2_FRAME_BYTES,
                    ARTWORK_V2_RETRY_DELAYS_SECONDS, BongoCatEngine)  # noqa: E402
from media_bridge import MediaSnapshot  # noqa: E402


class ArtworkV2Tests(unittest.TestCase):
    def make_engine(self):
        engine = BongoCatEngine.__new__(BongoCatEngine)
        engine.serial_conn = Mock(is_open=True)
        engine.serial_conn.write.side_effect = lambda payload: len(payload)
        engine.baudrate = 115200
        engine._serial_lock = Lock()
        engine._media_lock = RLock()
        engine._artwork_queue = queue.Queue(maxsize=1)
        engine._artwork_ack = Event()
        engine._artwork_transfer_active = Event()
        engine._artwork_v2_supported = False
        engine._artwork_v2_challenge = ""
        engine._artwork_v2_epoch = 0
        engine._artwork_v2_next_id = 0
        engine._artwork_v2_pending_id = None
        engine._artwork_v2_ack_result = None
        engine._artwork_v2_error_reason = None
        engine._artwork_retry = None
        engine._last_artwork_transfer_at = 0.0
        engine._last_media_meta = None
        engine._last_media_state = None
        engine._last_media_time = None
        engine._last_media_full_sync = 0.0
        engine._last_media_track_key = ""
        engine._last_media_snapshot = None
        engine._cached_artwork = None
        engine._cached_artwork_track_key = ""
        engine._media_deferred_since = 0.0
        engine.running = True
        engine._stop_requested = Event()
        engine.tray = None
        return engine

    @staticmethod
    def snapshot(key):
        return MediaSnapshot(available=True, source="SPOTIFY", title=key,
                             artist="Artist", playing=True, track_key=key)

    def test_complete_frame_needs_matching_length_order_and_crc(self):
        engine = self.make_engine()
        artwork = bytes(range(256)) * (ARTWORK_V2_FRAME_BYTES // 256)
        engine._on_media_update(self.snapshot("song"), None)
        frames = []

        def write(payload):
            frames.append(payload)
            if payload.startswith(b"MEDIA_ART2_END:"):
                engine._artwork_v2_ack_result = True
                engine._artwork_ack.set()
            return len(payload)

        engine.serial_conn.write.side_effect = write
        with patch("engine.time.sleep"), patch("engine.diagnostics.event") as event, \
             patch("builtins.print"):
            engine._send_artwork_v2(engine.serial_conn, "song", artwork, 0)
        self.assertTrue(any(call.args == ("ART_SENT",) and
                            call.kwargs.get("protocol") == "art2"
                            for call in event.call_args_list))

        begin = next(frame for frame in frames if frame.startswith(b"MEDIA_ART2_BEGIN:"))
        chunks = [frame for frame in frames if frame.startswith(b"MEDIA_ART2_CHUNK:")]
        end = next(frame for frame in frames if frame.startswith(b"MEDIA_ART2_END:"))
        self.assertEqual(len(chunks), ARTWORK_V2_FRAME_BYTES // ARTWORK_CHUNK_BYTES)
        self.assertTrue(begin.endswith(f":{zlib.crc32(artwork) & 0xFFFFFFFF:08X}\n".encode()))
        self.assertEqual(end, b"MEDIA_ART2_END:1\n")
        self.assertTrue(all(len(frame) <= 225 for frame in chunks))

        decoded = bytearray()
        for frame in chunks:
            _, transfer_id, offset, encoded = frame.rstrip(b"\n").split(b":", 3)
            self.assertEqual(transfer_id, b"1")
            self.assertEqual(int(offset), len(decoded))
            decoded.extend(base64.b64decode(encoded, validate=True))
        self.assertEqual(decoded, artwork)
        self.assertNotIn(b"MEDIA_ART_RGB", b"".join(frames))

        corrupted = bytearray(decoded)
        corrupted[100] ^= 1
        self.assertNotEqual(zlib.crc32(corrupted), zlib.crc32(artwork))
        self.assertNotEqual(len(decoded[:-ARTWORK_CHUNK_BYTES]), len(artwork))

    def test_fast_link_batches_complete_frames_and_retries_slowly(self):
        engine = self.make_engine()
        engine.baudrate = 230400
        artwork = bytes(range(256)) * (ARTWORK_V2_FRAME_BYTES // 256)
        engine._on_media_update(self.snapshot("song"), None)
        writes = []

        def accept(payload):
            writes.append(payload)
            if payload.startswith(b"MEDIA_ART2_END:"):
                engine._artwork_v2_ack_result = True
                engine._artwork_ack.set()
            return len(payload)

        engine.serial_conn.write.side_effect = accept
        with patch("engine.time.sleep"), patch("engine.diagnostics.event") as event:
            engine._send_artwork_v2(engine.serial_conn, "song", artwork, 0)
        batches = [payload for payload in writes
                   if payload.startswith(b"MEDIA_ART2_CHUNK:")]
        self.assertEqual(len(batches), ARTWORK_V2_FRAME_BYTES //
                         (2 * ARTWORK_CHUNK_BYTES))
        self.assertTrue(all(payload.count(b"MEDIA_ART2_CHUNK:") == 2
                            for payload in batches))
        chunks = [line for payload in batches for line in payload.splitlines(keepends=True)]
        self.assertTrue(all(len(line) <= 225 for line in chunks))
        decoded = bytearray()
        for line in chunks:
            _, transfer_id, offset, encoded = line.rstrip(b"\n").split(b":", 3)
            self.assertEqual(transfer_id, b"1")
            self.assertEqual(int(offset), len(decoded))
            decoded.extend(base64.b64decode(encoded, validate=True))
        self.assertEqual(decoded, artwork)
        self.assertTrue(any(call.args == ("ART_SENT",) and
                            call.kwargs.get("frames_per_write") == 2
                            for call in event.call_args_list))

        writes.clear()
        engine.serial_conn.write.side_effect = accept
        with patch("engine.time.sleep"), patch("engine.diagnostics.event"):
            engine._send_artwork_v2(engine.serial_conn, "song", artwork, 1)
        retry_chunks = [payload for payload in writes
                        if payload.startswith(b"MEDIA_ART2_CHUNK:")]
        self.assertEqual(len(retry_chunks), ARTWORK_V2_FRAME_BYTES // ARTWORK_CHUNK_BYTES)
        self.assertTrue(all(payload.count(b"MEDIA_ART2_CHUNK:") == 1
                            for payload in retry_chunks))

    def test_long_artwork_flush_does_not_rewind_playback_time(self):
        engine = self.make_engine()
        engine._artwork_v2_supported = True
        song = MediaSnapshot(available=True, source="SPOTIFY API", title="Song",
                             artist="Artist", playing=True, position_seconds=0,
                             duration_seconds=120, track_key="song")
        clock = [100.0]
        writes = []

        def write(payload):
            writes.append((clock[0], payload))
            if payload.startswith(b"MEDIA_ART2_END:"):
                engine._artwork_v2_ack_result = True
                engine._artwork_ack.set()
            return len(payload)

        def advance(seconds):
            clock[0] += seconds

        engine.serial_conn.write.side_effect = write
        artwork = bytes([1, 2, 3]) * (112 * 112)
        with patch("engine.time.monotonic", side_effect=lambda: clock[0]), \
             patch("engine.time.sleep", side_effect=advance), \
             patch("engine.diagnostics.event"), patch("builtins.print"):
            engine._on_media_update(song, None)
            engine._send_artwork_v2(engine.serial_conn, "song", artwork, 0)
            self.assertGreater(clock[0] - 100.0, 3.0)
            # The cover callback still carries the original zero-position
            # snapshot and must not rewind the locally ticking display.
            clock[0] += 4.0
            engine._on_media_update(song, artwork)
            engine._flush_latest_media()

        time_packets = [payload for _, payload in writes if b"MEDIA_TIME:" in payload]
        self.assertEqual(len(time_packets), 1)
        self.assertIn(b"MEDIA_TIME:0:120\n", time_packets[0])

    def test_fresh_seek_repeat_track_and_pause_still_update_time(self):
        engine = self.make_engine()
        song = MediaSnapshot(available=True, source="SPOTIFY API", title="Song",
                             artist="Artist", playing=True, position_seconds=38,
                             duration_seconds=120, track_key="song")
        engine._on_media_update(song, None)
        engine.serial_conn.write.reset_mock()
        engine._on_media_update(replace(song, position_seconds=12), None)
        self.assertIn(b"MEDIA_TIME:12:120\n", engine.serial_conn.write.call_args.args[0])
        engine._on_media_update(replace(song, position_seconds=0), None)
        self.assertIn(b"MEDIA_TIME:0:120\n", engine.serial_conn.write.call_args.args[0])
        engine._on_media_update(replace(song, playing=False, position_seconds=0), None)
        self.assertIn(b"MEDIA_STATE:PAUSED\n", engine.serial_conn.write.call_args.args[0])
        next_song = replace(song, title="Next", track_key="next", position_seconds=0)
        engine._on_media_update(next_song, None)
        self.assertIn(b"MEDIA_TIME:0:120\n", engine.serial_conn.write.call_args.args[0])

    def test_local_windows_snapshot_full_sync_keeps_local_progress(self):
        engine = self.make_engine()
        song = MediaSnapshot(available=True, source="SPOTIFY", title="Local song",
                             artist="Artist", playing=True, position_seconds=7,
                             duration_seconds=120, track_key="windows-song")
        clock = [100.0]
        with patch("engine.time.monotonic", side_effect=lambda: clock[0]):
            engine._on_media_update(song, None)
            engine.serial_conn.write.reset_mock()
            clock[0] += 4.0
            engine._flush_latest_media()
            payload = engine.serial_conn.write.call_args.args[0]
            self.assertIn(b"MEDIA_STATE:PLAYING\n", payload)
            self.assertNotIn(b"MEDIA_TIME:", payload)
            engine._on_media_update(replace(song, position_seconds=3), None)
            self.assertIn(b"MEDIA_TIME:3:120\n",
                          engine.serial_conn.write.call_args.args[0])

    def test_new_title_passes_between_chunks_and_old_cover_aborts(self):
        engine = self.make_engine()
        engine.baudrate = 230400
        engine._artwork_v2_supported = True
        artwork = bytes([10, 20, 30]) * (112 * 112)
        engine._on_media_update(self.snapshot("Old"), artwork)
        writes = []
        switched = False

        def write(payload):
            nonlocal switched
            writes.append(payload)
            if payload.startswith(b"MEDIA_ART2_CHUNK:") and not switched:
                switched = True
                engine._on_media_update(self.snapshot("New"), None)
            if payload.startswith(b"MEDIA_ART2_ABORT:"):
                engine.running = False
            return len(payload)

        engine.serial_conn.write.side_effect = write
        with patch("engine.time.sleep"), patch("engine.diagnostics.event"):
            engine._artwork_sender_loop()

        wire = b"".join(writes)
        self.assertIn(b"MEDIA_ART2_BEGIN:1:", wire)
        self.assertIn(b"MEDIA_ART2_CHUNK:1:0:", wire)
        self.assertEqual(wire.count(b"MEDIA_ART2_CHUNK:"), 2)
        self.assertIn(b"MEDIA_TITLE:New\n", wire)
        self.assertIn(b"MEDIA_ART_DEFAULT\n", wire)
        self.assertIn(b"MEDIA_ART2_ABORT:1\n", wire)
        self.assertNotIn(b"MEDIA_ART2_END:1\n", wire)
        self.assertLess(wire.index(b"MEDIA_ART2_CHUNK:1:0:"),
                        wire.index(b"MEDIA_TITLE:New\n"))
        self.assertLess(wire.index(b"MEDIA_TITLE:New\n"),
                        wire.index(b"MEDIA_ART2_ABORT:1\n"))
        self.assertEqual(engine._last_media_track_key, "New")

    def test_no_capability_uses_legacy_raw_protocol(self):
        engine = self.make_engine()
        artwork = bytes([1, 2, 3]) * (112 * 112)
        engine._on_media_update(self.snapshot("Legacy"), artwork)
        writes = []
        raw_bytes = 0

        def write(payload):
            nonlocal raw_bytes
            writes.append(payload)
            if not payload.endswith(b"\n"):
                raw_bytes += len(payload)
            return len(payload)

        engine.serial_conn.write.side_effect = write
        def acknowledge(timeout):
            engine.running = False
            return True

        engine._artwork_ack.wait = Mock(side_effect=acknowledge)
        with patch("engine.time.sleep"), patch("engine.diagnostics.event") as event, \
             patch("builtins.print"):
            engine._artwork_sender_loop()

        self.assertIn(b"MEDIA_ART_RGB:112:112:37632\n", writes)
        self.assertEqual(raw_bytes, len(artwork))
        self.assertNotIn(b"MEDIA_ART2_BEGIN", b"".join(writes))
        self.assertTrue(any(call.args == ("ART_SENT",) and
                            call.kwargs.get("protocol") == "legacy"
                            for call in event.call_args_list))

    def test_touch_command_is_read_during_v2_transfer(self):
        engine = self.make_engine()
        engine._artwork_v2_supported = True
        engine.media_bridge = Mock()
        touched = Event()
        engine.media_bridge.control.side_effect = lambda action: touched.set()
        engine._on_media_update(self.snapshot("song"), None)
        artwork = bytes([1, 2, 3]) * (112 * 112)
        first_chunk = False
        reader = None

        def read():
            if not touched.is_set():
                return b"MEDIA_CMD:NEXT\n"
            return b""

        engine.serial_conn.readline.side_effect = read

        def write(payload):
            nonlocal first_chunk, reader
            if payload.startswith(b"MEDIA_ART2_CHUNK:") and not first_chunk:
                first_chunk = True
                reader = Thread(target=engine._serial_reader_loop)
                reader.start()
                self.assertTrue(touched.wait(timeout=1))
            if payload.startswith(b"MEDIA_ART2_END:"):
                engine._artwork_v2_ack_result = True
                engine._artwork_ack.set()
                engine.running = False
            return len(payload)

        engine.serial_conn.write.side_effect = write
        with patch("engine.time.sleep"), patch("engine.diagnostics.event"), \
             patch("builtins.print"):
            engine._send_artwork_v2(engine.serial_conn, "song", artwork, 0)
        reader.join(timeout=1)
        self.assertFalse(reader.is_alive())
        engine.media_bridge.control.assert_called_once_with("NEXT")

    def test_device_rejection_stops_frame_and_schedules_delayed_retry(self):
        engine = self.make_engine()
        engine.baudrate = 230400
        artwork = bytes([5, 6, 7]) * (112 * 112)
        engine._on_media_update(self.snapshot("song"), None)
        writes = []

        def write(payload):
            writes.append(payload)
            if payload.startswith(b"MEDIA_ART2_CHUNK:"):
                engine._artwork_v2_ack_result = False
                engine._artwork_ack.set()
            return len(payload)

        engine.serial_conn.write.side_effect = write
        with patch("engine.time.sleep"), patch("engine.diagnostics.event"):
            engine._send_artwork_v2(engine.serial_conn, "song", artwork, 0)
        self.assertEqual(sum(p.startswith(b"MEDIA_ART2_CHUNK:") for p in writes), 1)
        self.assertEqual(b"".join(writes).count(b"MEDIA_ART2_CHUNK:"), 2)
        self.assertFalse(any(p.startswith(b"MEDIA_ART2_END:") for p in writes))
        self.assertEqual(engine._artwork_retry[1:4], ("song", artwork, 1))
        self.assertIsNone(engine._take_due_artwork_v2_retry())
        self.assertFalse(engine._artwork_transfer_active.is_set())

    def test_fast_and_slow_failures_recover_from_cached_cover(self):
        engine = self.make_engine()
        engine.baudrate = 230400
        engine._artwork_v2_supported = True
        artwork = bytes([5, 6, 7]) * (112 * 112)
        engine._on_media_update(self.snapshot("song"), None)
        clock = [100.0]
        attempts = []

        def write(payload):
            if payload.startswith(b"MEDIA_ART2_BEGIN:"):
                attempts.append(int(payload.split(b":", 2)[1]))
            if payload.startswith(b"MEDIA_ART2_CHUNK:") and len(attempts) == 1:
                engine._artwork_v2_ack_result = False
                engine._artwork_ack.set()
            if payload.startswith(b"MEDIA_ART2_END:"):
                engine._artwork_v2_ack_result = len(attempts) >= 3
                engine._artwork_ack.set()
            return len(payload)

        engine.serial_conn.write.side_effect = write
        with patch("engine.time.monotonic", side_effect=lambda: clock[0]), \
             patch("engine.time.sleep"), patch("engine.diagnostics.event") as event:
            engine._send_artwork_v2(engine.serial_conn, "song", artwork, 0)
            self.assertIsNone(engine._take_due_artwork_v2_retry())
            clock[0] += ARTWORK_V2_RETRY_DELAYS_SECONDS[0]
            self.assertEqual(engine._take_due_artwork_v2_retry(),
                             ("song", artwork, 1))
            engine._send_artwork_v2(engine.serial_conn, "song", artwork, 1)
            self.assertIsNone(engine._take_due_artwork_v2_retry())
            clock[0] += ARTWORK_V2_RETRY_DELAYS_SECONDS[1]
            self.assertEqual(engine._take_due_artwork_v2_retry(),
                             ("song", artwork, 2))
            engine._send_artwork_v2(engine.serial_conn, "song", artwork, 2)

        self.assertEqual(attempts, [1, 2, 3])
        self.assertIsNone(engine._artwork_retry)
        self.assertTrue(any(call.args == ("ART_RETRY",) and
                            call.kwargs.get("attempt") == 3
                            for call in event.call_args_list))

    def test_retries_are_bounded_and_new_track_cancels_pending_cover(self):
        engine = self.make_engine()
        artwork = bytes([5, 6, 7]) * (112 * 112)
        engine._on_media_update(self.snapshot("song"), None)
        clock = [100.0]
        engine.serial_conn.write.side_effect = lambda payload: len(payload)
        engine._artwork_ack.wait = Mock(return_value=False)
        with patch("engine.time.monotonic", side_effect=lambda: clock[0]), \
             patch("engine.time.sleep"), patch("engine.diagnostics.event") as event:
            engine._send_artwork_v2(engine.serial_conn, "song", artwork, 0)
            self.assertIsNone(engine._take_due_artwork_v2_retry())
            for attempt, delay in enumerate(ARTWORK_V2_RETRY_DELAYS_SECONDS, 1):
                clock[0] += delay
                self.assertEqual(engine._take_due_artwork_v2_retry(),
                                 ("song", artwork, attempt))
                engine._send_artwork_v2(engine.serial_conn, "song", artwork,
                                        attempt)
            self.assertIsNone(engine._artwork_retry)
            self.assertTrue(any(call.args == ("ART_RETRY",) and
                                call.kwargs.get("reason") == "retry_exhausted"
                                for call in event.call_args_list))

            engine._schedule_artwork_v2_retry(engine.serial_conn, "song", artwork,
                                               0, engine._artwork_v2_epoch)
            engine._on_media_update(self.snapshot("new song"), None)
            clock[0] += 100
            self.assertIsNone(engine._take_due_artwork_v2_retry())

    def test_resync_and_old_ack_cancel_delayed_retry(self):
        engine = self.make_engine()
        artwork = bytes([5, 6, 7]) * (112 * 112)
        engine._on_media_update(self.snapshot("song"), None)
        engine._schedule_artwork_v2_retry(engine.serial_conn, "song", artwork,
                                           0, engine._artwork_v2_epoch)
        engine._artwork_v2_pending_id = 9
        engine._artwork_ack.clear()
        replies = iter([b"MEDIA_ART2_REASON:8:art2_crc\n",
                        b"MEDIA_ART2_OK:8\n", b"MEDIA_ART2_REASON:9:art2_offset\n",
                        b"MEDIA_ART2_ERROR:9\n"])

        def read_reply():
            reply = next(replies)
            if reply.startswith(b"MEDIA_ART2_ERROR:"):
                engine.running = False
            return reply

        engine.serial_conn.readline.side_effect = read_reply
        with patch("engine.diagnostics.event") as event:
            engine._serial_reader_loop()
        self.assertFalse(engine._artwork_v2_ack_result)
        self.assertEqual(engine._artwork_v2_error_reason, "art2_offset")
        event.assert_any_call("ART_ACK", result="failure", reason="art2_offset",
                              protocol="art2")
        engine.running = True
        engine.send_initial_sync = Mock()
        engine._resync_device()
        self.assertIsNone(engine._artwork_retry)

    def test_sender_runs_due_retry_without_another_media_callback(self):
        engine = self.make_engine()
        engine._artwork_v2_supported = True
        artwork = bytes([5, 6, 7]) * (112 * 112)
        engine._on_media_update(self.snapshot("song"), None)
        engine._artwork_retry = (engine.serial_conn, "song", artwork, 2,
                                 engine._artwork_v2_epoch, 100.0)
        sent = []

        def send(conn, track_key, cover, attempt):
            sent.append((conn, track_key, cover, attempt))
            engine.running = False

        engine._send_artwork_v2 = Mock(side_effect=send)
        with patch("engine.time.monotonic", return_value=100.0), \
             patch("engine.diagnostics.event"):
            engine._artwork_sender_loop()
        self.assertEqual(sent, [(engine.serial_conn, "song", artwork, 2)])
        self.assertIsNone(engine._artwork_retry)

    def test_resync_disables_capability_and_late_ack_cannot_complete_new_id(self):
        engine = self.make_engine()
        engine._artwork_v2_supported = True
        engine.send_initial_sync = Mock()
        engine._resync_device()
        self.assertFalse(engine._artwork_v2_supported)
        self.assertEqual(engine._artwork_v2_epoch, 1)

        engine._artwork_v2_pending_id = 8
        replies = iter([b"MEDIA_ART2_OK:7\n", b"MEDIA_ART2_ERROR:8\n"])

        def read_reply():
            reply = next(replies)
            if reply.startswith(b"MEDIA_ART2_ERROR:"):
                engine.running = False
            return reply

        engine.serial_conn.readline.side_effect = read_reply
        with patch("engine.diagnostics.event") as event:
            engine._serial_reader_loop()
        self.assertTrue(engine._artwork_ack.is_set())
        self.assertFalse(engine._artwork_v2_ack_result)
        event.assert_any_call("ART_ACK", result="failure", reason="device_error",
                              protocol="art2")

    def test_capability_requires_current_challenge(self):
        engine = self.make_engine()
        engine._artwork_v2_challenge = "0123456789ABCDEF"
        replies = iter([b"CAPS:MEDIA_ART2:AAAAAAAAAAAAAAAA\n",
                        b"CAPS:MEDIA_ART2:0123456789ABCDEF\n"])
        seen = []

        def read_reply():
            seen.append(engine._artwork_v2_supported)
            reply = next(replies)
            if len(seen) == 2:
                engine.running = False
            return reply

        engine.serial_conn.readline.side_effect = read_reply
        with patch("engine.diagnostics.event") as event:
            engine._serial_reader_loop()
        self.assertEqual(seen, [False, False])
        self.assertTrue(engine._artwork_v2_supported)
        event.assert_called_once_with("ART_CAPABILITY", result="success", protocol="art2")

    def test_initial_sync_asks_once_with_fresh_capability_challenge(self):
        engine = self.make_engine()
        engine.get_system_stats = Mock(return_value=(12, 34))
        engine.send_command = Mock(return_value=True)
        with patch("engine.secrets.token_hex", return_value="abcd1234abcd1234"), \
             patch("builtins.print"):
            engine.send_initial_sync()
        commands = [call.args[0] for call in engine.send_command.call_args_list]
        self.assertEqual(commands[-2:], ["STATS:CPU:12,RAM:34,WPM:0",
                                         "CAPS?:ABCD1234ABCD1234"])
        self.assertEqual(engine._artwork_v2_challenge, "ABCD1234ABCD1234")


if __name__ == "__main__":
    unittest.main()
