"""Seek routing with fake Windows timelines/HTTP/clocks; no real controls."""
import asyncio
import datetime as dt
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
import urllib.error
import urllib.parse
from unittest.mock import AsyncMock, MagicMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from media_bridge import MediaSnapshot, WindowsMediaBridge
from media_seek import MEDIA_ACTIONS, clamp_seek, media_context_id, parse_media_command
from spotify_api import SpotifyPacingError, SpotifyRateLimitError
from transport_budget import TransportSpotifyApiBridge as SpotifyApiBridge


class SeekProtocolTests(unittest.TestCase):
    def test_only_five_exact_media_commands(self):
        for action in MEDIA_ACTIONS:
            suffix = ":123" if action.startswith("SEEK:") else ""
            self.assertEqual(parse_media_command("MEDIA_CMD:" + action + suffix),
                             (action, 123 if suffix else None))
        for line in ("MEDIA_CMD:SEEK:15", "MEDIA_CMD:SEEK:+150", "MEDIA_CMD:SEEK:0",
                     "MEDIA_CMD:SEEK:-1", "MEDIA_CMD:SEEK:+15:extra", "MEDIA_CMD:SEEK:+15\nNEXT",
                     "MEDIA_CMD:seek:+15", "MEDIA_CMD:SEEK:+١٥", "SEEK:+15",
                     "MEDIA_CMD:SEEK:+15:0", "MEDIA_CMD:SEEK:+15:4294967296",
                     "MEDIA_CMD:SEEK:+15:0123", "MEDIA_CMD:SEEK:+15:１２３"):
            self.assertIsNone(parse_media_command(line), line)
        self.assertEqual(parse_media_command("MEDIA_CMD:SEEK:-15:4294967295"), ("SEEK:-15", 0xFFFFFFFF))

    def test_clamp_keeps_both_ends_and_rejects_bad_bounds(self):
        self.assertEqual(clamp_seek(3, -15, 0, 99), 0)
        self.assertEqual(clamp_seek(90, 15, 0, 99), 99)
        self.assertEqual(clamp_seek(3, -15, 2, 99), 2)
        self.assertIsNone(clamp_seek(0, 15, 2, 1))

    def test_actual_serial_reader_routes_seek_and_rejects_invalid_delta(self):
        import test_artwork_v2
        engine = test_artwork_v2.ArtworkV2Tests().make_engine()
        engine.media_bridge = Mock()
        lines = iter([b"MEDIA_CMD:SEEK:+15:123\n", b"MEDIA_CMD:SEEK:-15:123\n",
                      b"MEDIA_CMD:SEEK:+150\n", b"MEDIA_CMD:SEEK:15\n",
                      b"MEDIA_CMD:SEEK:+\xff15\n", b"MEDIA_CMD:NEXT\n"])
        def read():
            line = next(lines)
            if line == b"MEDIA_CMD:NEXT\n":
                engine.running = False
            return line
        engine.serial_conn.readline.side_effect = read
        with patch("engine.diagnostics.event"), patch("builtins.print"):
            engine._serial_reader_loop()
        self.assertEqual([c.args[0] for c in engine.media_bridge.control.call_args_list],
                         ["SEEK:+15", "SEEK:-15", "NEXT"])
        self.assertEqual([c.kwargs for c in engine.media_bridge.control.call_args_list],
                         [{"expected_context":123}, {"expected_context":123}, {}])

    def test_confirmed_seek_refreshes_existing_media_time_and_anchor_packet(self):
        import test_artwork_v2
        engine = test_artwork_v2.ArtworkV2Tests().make_engine()
        first = MediaSnapshot(available=True, source="SPOTIFY", title="Song", artist="Artist",
                              track_key="same", playing=False, position_seconds=30, duration_seconds=180)
        engine._on_media_update(first, None)
        engine.serial_conn.write.reset_mock()
        confirmed = MediaSnapshot(**{**first.__dict__, "position_seconds": 45})
        engine._on_media_update(confirmed, None)
        self.assertIn(b"MEDIA_TIME:45:180\n", engine.serial_conn.write.call_args.args[0])
        self.assertEqual(engine._last_media_time, (45, 180))
        self.assertTrue(engine._artwork_queue.empty())

    def test_context_is_sent_only_on_track_source_change_or_resync(self):
        import test_artwork_v2
        engine = test_artwork_v2.ArtworkV2Tests().make_engine()
        snap = MediaSnapshot(available=True, source="SPOTIFY API", track_key="song", duration_seconds=180)
        engine._on_media_update(snap, None)
        context = media_context_id(snap.source, snap.track_key)
        self.assertIn(f"MEDIA_SEEK_CONTEXT:{context}\n".encode(), engine.serial_conn.write.call_args.args[0])
        engine.serial_conn.write.reset_mock()
        engine._last_media_full_sync = -100 # force existing regular metadata refresh
        engine._on_media_update(snap, None)
        self.assertNotIn(b"MEDIA_SEEK_CONTEXT:", engine.serial_conn.write.call_args.args[0])
        changed = MediaSnapshot(**{**snap.__dict__, "source":"SPOTIFY"})
        engine._on_media_update(changed, None)
        self.assertIn(f"MEDIA_SEEK_CONTEXT:{media_context_id(changed.source, changed.track_key)}\n".encode(), engine.serial_conn.write.call_args.args[0])
        engine.send_initial_sync = Mock()
        engine.serial_conn.write.reset_mock()
        engine._resync_device()
        self.assertEqual(engine._last_media_seek_context_id, media_context_id(changed.source, changed.track_key))
        self.assertIn(b"MEDIA_SEEK_CONTEXT:", engine.serial_conn.write.call_args.args[0])

    def test_deferred_metadata_keeps_old_id_and_context_is_final_bundle_marker(self):
        import test_artwork_v2
        engine = test_artwork_v2.ArtworkV2Tests().make_engine()
        old = MediaSnapshot(available=True, source="SPOTIFY", title="Old", artist="Artist",
                            track_key="old", duration_seconds=180)
        new = MediaSnapshot(available=True, source="SPOTIFY API", title="New", artist="New Artist",
                            track_key="new", duration_seconds=200, position_seconds=10)
        engine._on_media_update(old, None)
        old_id = engine._last_media_seek_context_id
        engine._write_media_payload = Mock(return_value=False)
        engine._on_media_update(new, None)
        self.assertEqual(engine._last_media_seek_context_id, old_id)
        self.assertEqual(engine._last_media_snapshot, new)
        payload = engine._write_media_payload.call_args.args[0].decode().splitlines()
        marker = f"MEDIA_SEEK_CONTEXT:{media_context_id(new.source, new.track_key)}"
        self.assertEqual(payload[-1], marker)
        for field in ("MEDIA_TITLE:New", "MEDIA_ARTIST:New Artist", "MEDIA_TIME:10:200", "MEDIA_ART_DEFAULT"):
            self.assertLess(payload.index(field), payload.index(marker))
        engine._write_media_payload.return_value = True
        engine._on_media_update(new, None)
        self.assertEqual(engine._last_media_seek_context_id, media_context_id(new.source, new.track_key))
        self.assertEqual(engine._write_media_payload.call_args.args[0].decode().splitlines()[-1], marker)

    def test_old_display_context_cannot_seek_new_companion_track(self):
        bridge = WindowsMediaBridge(on_update=Mock())
        bridge._current_source = "windows_spotify"
        old_id = media_context_id("SPOTIFY", "old")
        bridge._last_snapshot = MediaSnapshot(available=True, source="SPOTIFY", track_key="new")
        self.assertFalse(bridge.control("SEEK:+15", expected_context=old_id))
        self.assertTrue(bridge._commands.empty())
        self.assertFalse(bridge._seek_requests)
        current_id = media_context_id("SPOTIFY", "new")
        self.assertTrue(bridge.control("SEEK:+15", expected_context=current_id))


class WindowsSeekTests(unittest.TestCase):
    NOW = dt.datetime(2026, 10, 12, 12, tzinfo=dt.timezone.utc)

    def setup_session(self, position=30, end=180, playing=False, minimum=0, maximum=None):
        bridge = WindowsMediaBridge(on_update=Mock())
        bridge._current_source = "windows_spotify"
        props = NS(title="Song", artist="Artist", album_artist="", album_title="Album", track_number=1)
        timeline = NS(position=dt.timedelta(seconds=position), end_time=dt.timedelta(seconds=end),
            start_time=dt.timedelta(0), min_seek_time=dt.timedelta(seconds=minimum),
            max_seek_time=dt.timedelta(seconds=end if maximum is None else maximum),
            last_updated_time=self.NOW - dt.timedelta(seconds=2))
        playback = NS(playback_status="PLAYING" if playing else "PAUSED", playback_rate=1.0,
                      controls=NS(is_playback_position_enabled=True))
        session = Mock(source_app_user_model_id="Spotify.exe")
        session.try_get_media_properties_async = AsyncMock(return_value=props)
        session.get_timeline_properties.return_value = timeline
        session.get_playback_info.return_value = playback
        session.try_change_playback_position_async = AsyncMock(return_value=True)
        bridge._last_snapshot = MediaSnapshot(available=True, source="SPOTIFY", title="Song",
            track_key=bridge._windows_track_key(session, props), duration_seconds=int(end))
        return bridge, session, timeline, playback

    def run_controls(self, bridge, session):
        class ClockDate(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return WindowsSeekTests.NOW
        with patch("media_bridge.dt.datetime", ClockDate):
            return asyncio.run(bridge._handle_commands(session))

    def test_windows_ticks_clamp_playing_paused_and_seekable_bounds(self):
        for position, end, playing, minimum, maximum, action, expected in (
            (30, 180, False, 0, 180, "SEEK:+15", 450000000),
            (30, 180, True, 0, 180, "SEEK:+15", 470000000),
            (3, 180, False, 0, 180, "SEEK:-15", 0),
            (175, 180.123, False, 0, 180.123, "SEEK:+15", 1801220000),
            (30, 180, False, 20, 40, "SEEK:-15", 200000000),
            (30, 180, False, 20, 40, "SEEK:+15", 400000000),
        ):
            with self.subTest(position=position, playing=playing, action=action, max=maximum):
                bridge, session, _, _ = self.setup_session(position, end, playing, minimum, maximum)
                self.assertTrue(bridge.control(action))
                self.assertTrue(self.run_controls(bridge, session))
                session.try_change_playback_position_async.assert_awaited_once_with(expected)
                session.try_skip_next_async.assert_not_called()
                bridge._on_update.assert_not_called()
                self.assertFalse(bridge._seek_requests)

    def test_two_fast_swipes_add_or_reverse_using_new_actual_timeline(self):
        for second, expected in (("SEEK:+15", [450000000, 600000000]),
                                 ("SEEK:-15", [450000000, 300000000])):
            bridge, session, timeline, _ = self.setup_session()
            async def accept(ticks):
                timeline.position = dt.timedelta(microseconds=ticks // 10)
                return True
            session.try_change_playback_position_async.side_effect = accept
            self.assertTrue(bridge.control("SEEK:+15"))
            self.assertTrue(bridge.control(second))
            self.assertTrue(self.run_controls(bridge, session))
            self.assertTrue(self.run_controls(bridge, session))
            self.assertEqual([c.args[0] for c in session.try_change_playback_position_async.await_args_list], expected)
            self.assertFalse(bridge._seek_requests)

    def test_rejection_exception_unsupported_and_no_fake_snapshot(self):
        for fault in ("disabled", "reject", "exception", "bad_bounds"):
            bridge, session, timeline, playback = self.setup_session()
            if fault == "disabled": playback.controls.is_playback_position_enabled = False
            if fault == "reject": session.try_change_playback_position_async.return_value = False
            if fault == "exception": session.try_change_playback_position_async.side_effect = RuntimeError()
            if fault == "bad_bounds": timeline.min_seek_time = dt.timedelta(seconds=200)
            bridge.control("SEEK:+15")
            self.assertFalse(self.run_controls(bridge, session))
            bridge._on_update.assert_not_called()
            self.assertFalse(bridge._seek_requests)

    def test_track_source_expiry_and_change_during_property_read_cancel(self):
        for change in ("track", "source", "expiry", "during_read"):
            bridge, session, _, _ = self.setup_session()
            with patch("media_bridge.time.monotonic", return_value=100): bridge.control("SEEK:+15")
            if change == "track": bridge._last_snapshot = MediaSnapshot(available=True, track_key="new")
            if change == "source": bridge._current_source = "spotify_api"
            if change == "during_read":
                props = session.try_get_media_properties_async.return_value
                async def read():
                    bridge._last_snapshot = MediaSnapshot(available=True, track_key="new")
                    return props
                session.try_get_media_properties_async.side_effect = read
            with patch("media_bridge.time.monotonic", return_value=106 if change == "expiry" else 101):
                self.assertFalse(self.run_controls(bridge, session))
            session.try_change_playback_position_async.assert_not_called()
            self.assertFalse(bridge._seek_requests)

    def test_queue_is_bounded_to_four_and_expired_work_is_dropped(self):
        bridge, session, _, _ = self.setup_session()
        with patch("media_bridge.time.monotonic", return_value=100):
            self.assertEqual([bridge.control("SEEK:+15") for _ in range(5)], [True]*4+[False])
        with patch("media_bridge.time.monotonic", return_value=106):
            self.assertFalse(self.run_controls(bridge, session))
        self.assertFalse(bridge._seek_requests)
        session.try_change_playback_position_async.assert_not_called()


class ApiSeekTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.folder.cleanup)
        self.now = 1000.0
        self.mono = 100.0
        for name, value in (("spotify_api.time.time", lambda: self.now),
                            ("spotify_api.time.monotonic", lambda: self.mono)):
            clock = patch(name, side_effect=value)
            clock.start(); self.addCleanup(clock.stop)
        self.api = SpotifyApiBridge("fixture", Path(self.folder.name)/"tokens.json",
            {"api_min_interval_seconds":0.5, "api_initial_interval_seconds":1})
        self.api._tokens.update(access_token="fixture", refresh_token="fixture", expires_at=1000000)
        self.bridge = WindowsMediaBridge(on_update=Mock())
        self.bridge._spotify = self.api
        self.bridge._current_source = "spotify_api"
        self.data = {"item":{"id":"song", "name":"Song", "duration_ms":180123},
                     "device":{"id":"device", "is_restricted":False},
                     "progress_ms":30000, "is_playing":False, "actions":{"disallows":{}}}
        self.calls = []
        self.seek_error = None
        self.http = patch("spotify_api.urllib.request.urlopen", side_effect=self.response)
        self.http.start(); self.addCleanup(self.http.stop)
        playback, _ = self.api.get_playback()
        self.bridge._last_snapshot = MediaSnapshot(available=True, **playback)

    def advance(self, seconds):
        self.now += seconds; self.mono += seconds

    def response(self, request, **kwargs):
        self.calls.append((request.method, request.full_url, self.now))
        response = MagicMock()
        response.__enter__.return_value = response
        if request.method == "PUT":
            if self.seek_error: raise self.seek_error
            self.data["progress_ms"] = int(urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)["position_ms"][0])
            response.read.return_value = b""
        else: response.read.return_value = json.dumps(self.data).encode()
        return response

    def pump(self):
        for _ in range(10):
            try: return self.bridge._handle_spotify_commands()
            except SpotifyPacingError as exc: self.advance(exc.wait_seconds)
        self.fail("Pacing did not settle")

    def confirm(self):
        self.advance(0.8)
        playback, _ = self.api.get_playback(urgent=True, operation=self.bridge._confirmation_operation)
        self.api.finish_operation(self.bridge._confirmation_operation)
        self.bridge._confirmation_operation = None
        self.bridge._publish(MediaSnapshot(available=True, **playback), None)

    def test_two_fast_connect_swipes_use_fresh_relative_position_and_same_gate(self):
        for second, expected in (("SEEK:+15", 60000), ("SEEK:-15", 30000)):
            self.data["progress_ms"] = 30000
            self.bridge.control("SEEK:+15"); self.bridge.control(second)
            self.assertTrue(self.pump())
            self.bridge._on_update.assert_not_called() # accepted PUT alone never draws a position
            self.confirm()
            self.assertTrue(self.pump()); self.confirm()
            self.assertEqual(self.data["progress_ms"], expected)
            self.assertFalse(self.bridge._seek_requests)
            self.assertFalse(self.data["is_playing"])
            self.bridge._on_update.reset_mock()
        self.assertTrue(all(b[2]-a[2] >= 0.499 for a,b in zip(self.calls, self.calls[1:])))
        self.assertTrue(all("/seek?" in url for method,url,_ in self.calls if method == "PUT"))

    def test_exact_ms_end_zero_and_playing_extrapolation(self):
        for position, action, expected in ((179900, "SEEK:+15", 180122),
                                           (3000, "SEEK:-15", 0)):
            self.data["progress_ms"] = position
            self.bridge.control(action); self.assertTrue(self.pump())
            self.assertEqual(self.data["progress_ms"], expected)
            self.confirm()
        self.data.update(progress_ms=30000, is_playing=True)
        self.bridge.control("SEEK:+15"); self.assertTrue(self.pump())
        self.assertEqual(self.data["progress_ms"], 45500) # half-second paced PUT wait
        self.assertTrue(self.data["is_playing"])

    def test_fresh_track_device_disallow_and_restricted_source_reject(self):
        for change in ("track", "device", "disallow", "restricted"):
            self.data["item"]["id"] = "song"; self.data["device"].update(id="device", is_restricted=False)
            self.data["actions"]["disallows"] = {}
            self.bridge.control("SEEK:+15")
            if change == "track": self.data["item"]["id"] = "new"
            if change == "device": self.data["device"]["id"] = "new-device"
            if change == "disallow": self.data["actions"]["disallows"]["seeking"] = True
            if change == "restricted": self.data["device"]["is_restricted"] = True
            self.assertFalse(self.pump())
            self.assertFalse(self.bridge._seek_requests)
        self.assertFalse(any(method == "PUT" for method,_,_ in self.calls))
        self.bridge._on_update.assert_not_called()

    def test_429_drops_seek_keeps_saved_retry_after_and_blocks_all_request_kinds(self):
        self.seek_error = urllib.error.HTTPError("fixture", 429, "limited", {"Retry-After":"10"}, io.BytesIO(b"{}"))
        self.bridge.control("SEEK:+15"); self.bridge.control("SEEK:-15")
        with self.assertRaises(SpotifyRateLimitError): self.pump()
        count = len(self.calls)
        self.assertIsNone(self.bridge._pending_spotify_command)
        self.assertEqual(len(self.bridge._seek_requests), 1)
        for call in (self.api.get_playback, lambda:self.api.control("NEXT"),
                     lambda:self.api.get_playback(urgent=True)):
            with self.assertRaises(SpotifyRateLimitError): call()
        self.assertEqual(len(self.calls), count)
        self.assertGreater(json.loads(self.api.token_path.read_text())["rate_limit_until"], self.now)
        self.advance(11)
        self.assertFalse(self.pump()) # second old swipe expires rather than replaying
        self.assertFalse(self.bridge._seek_requests)
        self.assertEqual(len(self.calls), count)

    def test_source_change_or_expiry_while_paced_drops_without_put(self):
        for change in ("source", "expiry"):
            self.bridge._current_source = "spotify_api"
            self.bridge.control("SEEK:+15")
            with self.assertRaises(SpotifyPacingError): self.bridge._handle_spotify_commands()
            if change == "source": self.bridge._current_source = "windows_spotify"
            self.advance(6 if change == "expiry" else 0.5)
            self.assertFalse(self.pump())
            self.assertFalse(self.bridge._seek_requests)
        self.assertFalse(any(method == "PUT" for method,_,_ in self.calls))

    def test_http_failure_does_not_crash_publish_or_retry_seek(self):
        self.seek_error = urllib.error.URLError("fixture")
        self.bridge.control("SEEK:+15")
        self.assertFalse(self.pump())
        self.assertFalse(self.bridge._seek_requests)
        self.assertFalse(self.pump())
        self.bridge._on_update.assert_not_called()
        self.assertEqual(sum(method == "PUT" for method,_,_ in self.calls), 1)

    def test_actual_worker_confirms_seek_from_normal_snapshot_without_optimism(self):
        # This case begins with an already authoritative API snapshot, not a
        # new Windows->API waiting epoch.
        self.bridge._source_mode = "spotify_api"
        self.bridge._source_epoch = self.bridge._api_snapshot_epoch = 1
        self.bridge.control("SEEK:+15")
        manager = Mock(get_sessions=Mock(return_value=[]))
        async def sleep(seconds): self.advance(seconds)
        async def wait(seconds): self.bridge._stop.set()
        with patch("media_bridge.GlobalSystemMediaTransportControlsSessionManager.request_async",
                   new_callable=AsyncMock, return_value=manager), \
             patch("media_bridge.asyncio.sleep", side_effect=sleep), \
             patch.object(self.bridge, "_wait_for_spotify_work", side_effect=wait), \
             patch.object(self.bridge, "_try_api_artwork", new_callable=AsyncMock, return_value=None):
            asyncio.run(self.bridge._run())
        self.bridge._on_update.assert_called_once()
        snapshot = self.bridge._on_update.call_args.args[0]
        self.assertEqual(snapshot.position_seconds, 45)
        self.assertFalse(snapshot.playing)
        self.assertEqual(snapshot.track_key, "spotify:song")
        self.assertEqual([method for method,_,_ in self.calls], ["GET", "GET", "PUT", "GET"])
        self.assertFalse(self.bridge._seek_requests)


if __name__ == "__main__":
    unittest.main()
