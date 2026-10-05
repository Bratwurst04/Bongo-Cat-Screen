"""Serial recovery and content resync without a connected ESP32."""

import queue
import sys
import unittest
from pathlib import Path
from threading import Event, Lock, RLock, Thread
from unittest.mock import Mock, patch

import serial


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))

from engine import BongoCatEngine  # noqa: E402
from media_bridge import MediaSnapshot  # noqa: E402


class PowerResumeTests(unittest.TestCase):
    def make_engine(self):
        engine = BongoCatEngine.__new__(BongoCatEngine)
        engine.serial_conn = Mock(is_open=True)
        engine._serial_lock = Lock()
        engine._stop_requested = Event()
        engine.running = True
        engine.tray = Mock()
        engine.port = "COM6"
        engine._auto_port = False
        engine.baudrate = 115200
        engine._next_reconnect_at = 0.0
        engine._last_device_reply_at = 0.0
        engine._last_media_meta = None
        engine._last_media_state = None
        engine._last_media_time = None
        engine._last_media_full_sync = 0.0
        engine._last_media_track_key = ""
        engine._last_media_snapshot = None
        engine._cached_artwork = None
        engine._cached_artwork_track_key = ""
        engine._media_lock = RLock()
        engine._media_deferred_since = 0.0
        engine._artwork_queue = queue.Queue(maxsize=1)
        engine._artwork_ack = Event()
        engine._artwork_v2_supported = False
        engine._artwork_v2_challenge = ""
        engine._artwork_v2_epoch = 0
        engine._artwork_v2_next_id = 0
        engine._artwork_v2_pending_id = None
        engine._artwork_v2_ack_result = None
        engine._artwork_transfer_active = Event()
        engine._last_artwork_transfer_at = 0.0
        return engine

    def test_latest_metadata_flushes_after_artwork_lock_releases(self):
        engine = self.make_engine()
        first = MediaSnapshot(available=True, source="SPOTIFY", title="Old",
                              artist="Artist", playing=True, track_key="old")
        latest = MediaSnapshot(available=True, source="SPOTIFY", title="New",
                               artist="Artist", playing=True, track_key="new")
        engine._on_media_update(first, None)
        engine.serial_conn.write.reset_mock()
        engine._serial_lock.acquire()
        try:
            engine._on_media_update(latest, None)
            self.assertEqual(engine.serial_conn.write.call_count, 0)
            self.assertGreater(engine._media_deferred_since, 0)
        finally:
            engine._serial_lock.release()
        with patch("engine.diagnostics.event") as event:
            engine._flush_latest_media()
        payload = engine.serial_conn.write.call_args.args[0]
        self.assertIn(b"MEDIA_TITLE:New", payload)
        self.assertIn(b"MEDIA_ART_DEFAULT", payload)
        self.assertEqual(engine._media_deferred_since, 0)
        self.assertTrue(any(call.args[0] == "MEDIA_SEND_DELAY" for call in event.call_args_list))

    def test_write_error_retires_port_and_reconnects_once(self):
        engine = self.make_engine()
        broken = engine.serial_conn
        broken.write.side_effect = serial.SerialException("port vanished")
        self.assertFalse(engine.send_command("STATS:CPU:1,RAM:2,WPM:0"))
        self.assertIsNone(engine.serial_conn)
        broken.close.assert_called_once_with()

        reopened = Mock(is_open=True)
        engine.send_initial_sync = Mock()
        with patch("engine.serial.Serial", return_value=reopened) as open_port, \
             patch("engine.time.sleep"), patch("engine.time.monotonic", return_value=10):
            engine._attempt_reconnect()
            engine._attempt_reconnect()

        self.assertIs(engine.serial_conn, reopened)
        open_port.assert_called_once()
        engine.send_initial_sync.assert_called_once_with()

    def test_shutdown_during_reopen_closes_new_handle(self):
        engine = self.make_engine()
        engine.serial_conn = None
        reopened = Mock(is_open=True)
        with patch("engine.serial.Serial", return_value=reopened), \
             patch("engine.time.sleep", side_effect=lambda _: engine._stop_requested.set()), \
             patch("engine.time.monotonic", return_value=10):
            engine._attempt_reconnect()

        self.assertIsNone(engine.serial_conn)
        reopened.close.assert_called_once_with()

    def test_silent_stale_handle_is_reopened(self):
        engine = self.make_engine()
        stale = engine.serial_conn
        reopened = Mock(is_open=True)
        engine.send_initial_sync = Mock()
        with patch("engine.serial.Serial", return_value=reopened), \
             patch("engine.time.sleep"), patch("engine.time.time", return_value=100), \
             patch("engine.time.monotonic", return_value=10):
            engine._attempt_reconnect()

        stale.close.assert_called_once_with()
        self.assertIs(engine.serial_conn, reopened)
        engine.send_initial_sync.assert_called_once_with()

    def test_artwork_upload_and_ack_grace_do_not_trigger_stale_reconnect(self):
        engine = self.make_engine()
        engine._last_device_reply_at = 100
        engine._artwork_transfer_active.set()
        with patch("engine.time.time", return_value=120):
            engine._attempt_reconnect()
        self.assertTrue(engine.serial_conn.is_open)
        engine.serial_conn.close.assert_not_called()

        engine._artwork_transfer_active.clear()
        engine._last_artwork_transfer_at = 120
        with patch("engine.time.time", return_value=134):
            engine._attempt_reconnect()
        engine.serial_conn.close.assert_not_called()

        stale = engine.serial_conn
        engine._next_reconnect_at = float("inf")
        with patch("engine.time.time", return_value=136):
            engine._attempt_reconnect()
        self.assertIsNone(engine.serial_conn)
        stale.close.assert_called_once_with()

    def test_reader_survives_a_port_error_without_new_thread(self):
        engine = self.make_engine()
        broken = engine.serial_conn
        broken.readline.side_effect = serial.SerialException("removed")
        reopened = Mock(is_open=True)
        engine._resync_device = Mock()

        def read_after_reopen():
            engine.running = False
            return b"SYNC_REQUEST\n"

        reopened.readline.side_effect = read_after_reopen
        with patch("engine.time.sleep", side_effect=lambda _: setattr(engine, "serial_conn", reopened)):
            engine._serial_reader_loop()

        broken.close.assert_called_once_with()
        engine._resync_device.assert_called_once_with()

    def test_existing_stats_cadence_supplies_presence_without_extra_packets(self):
        engine = self.make_engine()
        engine.current_wpm = 0
        engine.last_stats_sent = 0
        engine.last_time_sent = 99
        engine.get_system_stats = Mock(return_value=(12, 34))
        engine.send_command = Mock()
        with patch("engine.time.time", side_effect=[100, 101, 102]):
            engine.update_system_stats()
            engine.update_system_stats()
            engine.update_system_stats()

        self.assertEqual(
            [call.args[0] for call in engine.send_command.call_args_list],
            ["STATS:CPU:12,RAM:34,WPM:0", "STATS:CPU:12,RAM:34,WPM:0"],
        )

    def test_reader_handles_sync_request_and_resends_same_cover(self):
        engine = self.make_engine()
        snapshot = MediaSnapshot(
            available=True, source="SPOTIFY", title="Same song", artist="Artist",
            playing=True, position_seconds=30, duration_seconds=120,
            track_key="same-track",
        )
        cover = bytes([11, 22, 33]) * (112 * 112)
        engine._on_media_update(snapshot, cover)
        engine.serial_conn.write.reset_mock()
        engine._artwork_queue.get_nowait()
        engine.send_initial_sync = Mock()

        def read_request():
            engine.running = False
            return b"SYNC_REQUEST\n"

        engine.serial_conn.readline.side_effect = read_request
        engine._serial_reader_loop()

        engine.send_initial_sync.assert_called_once_with()
        payload = b"".join(call.args[0] for call in engine.serial_conn.write.call_args_list)
        self.assertIn(b"MEDIA_TITLE:Same song\n", payload)
        self.assertIn(b"MEDIA_STATE:PLAYING\n", payload)
        self.assertIn(b"MEDIA_TIME:30:120\n", payload)
        self.assertEqual(engine._artwork_queue.get_nowait(), ("same-track", cover, 0))

    def test_device_artwork_error_is_logged_without_faking_ack(self):
        engine = self.make_engine()
        engine._artwork_ack = Event()

        def read_error():
            engine.running = False
            return b"MEDIA_ART_ERROR\n"

        engine.serial_conn.readline.side_effect = read_error
        with patch("engine.diagnostics.event") as record:
            engine._serial_reader_loop()
        record.assert_any_call("ART_ACK", result="failure", reason="device_error",
                               protocol="legacy")
        self.assertFalse(engine._artwork_ack.is_set())

    def test_new_track_cannot_reuse_old_cover(self):
        engine = self.make_engine()
        engine.serial_conn = None
        old = MediaSnapshot(available=True, track_key="old")
        new = MediaSnapshot(available=True, track_key="new")
        engine._on_media_update(old, b"old cover")
        engine._on_media_update(new, None)

        self.assertIs(engine._last_media_snapshot, new)
        self.assertIsNone(engine._cached_artwork)

    def test_cover_waits_for_track_metadata_when_serial_is_busy(self):
        engine = self.make_engine()
        song = MediaSnapshot(available=True, source="SPOTIFY", title="New",
                             artist="Artist", playing=True, track_key="new")
        engine._serial_lock.acquire()
        try:
            engine._on_media_update(song, b"cover")
        finally:
            engine._serial_lock.release()
        self.assertEqual(engine._last_media_track_key, "")
        self.assertEqual(engine._artwork_queue.get_nowait(), ("new", b"cover", 0))
        engine._flush_latest_media()
        payload = b"".join(call.args[0] for call in engine.serial_conn.write.call_args_list)
        self.assertIn(b"MEDIA_TITLE:New\n", payload)
        self.assertIn(b"MEDIA_ART_DEFAULT\n", payload)
        self.assertEqual(engine._last_media_track_key, "new")

    def test_fast_track_change_during_cover_flushes_new_state_before_new_cover(self):
        engine = self.make_engine()
        old = MediaSnapshot(available=True, source="SPOTIFY", title="Old",
                            artist="Artist", playing=True, track_key="old")
        new = MediaSnapshot(available=True, source="SPOTIFY", title="New",
                            artist="Artist", playing=True, track_key="new")
        writes = []
        switched = False

        def write(payload):
            nonlocal switched
            writes.append(payload)
            if payload == b"old-cover" and not switched:
                switched = True
                engine._on_media_update(new, b"new-cover")
            elif payload == b"new-cover":
                engine.running = False
            return len(payload)

        engine.serial_conn.write.side_effect = write
        engine._artwork_ack.wait = Mock(return_value=True)
        engine._on_media_update(old, b"old-cover")
        with patch("engine.time.sleep"):
            engine._artwork_sender_loop()

        wire = b"".join(writes)
        old_cover_end = wire.index(b"old-cover") + len(b"old-cover")
        next_meta = wire.index(b"MEDIA_TITLE:New\n")
        next_default = wire.index(b"MEDIA_ART_DEFAULT\n", next_meta)
        new_cover = wire.index(b"new-cover")
        self.assertLess(old_cover_end, next_meta)
        self.assertLess(next_meta, next_default)
        self.assertLess(next_default, new_cover)
        self.assertEqual(engine._last_media_track_key, "new")

    def test_touch_is_read_while_artwork_holds_outbound_lock(self):
        engine = self.make_engine()
        engine.media_bridge = Mock()

        def read_command():
            engine.running = False
            return b"MEDIA_CMD:NEXT\n"

        engine.serial_conn.readline.side_effect = read_command
        engine._serial_lock.acquire()
        try:
            reader = Thread(target=engine._serial_reader_loop)
            reader.start()
            reader.join(timeout=1)
            self.assertFalse(reader.is_alive())
        finally:
            engine._serial_lock.release()
        engine.media_bridge.control.assert_called_once_with("NEXT")


if __name__ == "__main__":
    unittest.main()
