"""Diagnostic package privacy and bounded artwork retry checks."""

import asyncio
import datetime as dt
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))

from diagnostics import Diagnostics  # noqa: E402
from media_bridge import WindowsMediaBridge  # noqa: E402
from tray import BongoCatSystemTray  # noqa: E402


class DiagnosticsTests(unittest.TestCase):
    def test_rotation_export_and_content_filter(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "logs").mkdir()
            (root / "logs" / "spotify_tokens.json").write_text("secret-token")
            with patch("diagnostics.LOG_BYTES", 512):
                diag = Diagnostics(root / "logs")
                diag.start()
            for number in range(100):
                diag.event("ART_FETCH", attempt=number, source="spotify_api",
                           reason="secret-title", title="secret-title",
                           token="secret-token", error_type=type("secret-token", (Exception,), {}))
            diag.event("SPOTIFY_API_429", reason="quota_exceeded",
                       request_kind="playback_poll", origin="http_response",
                       wait_seconds=36000, playback_poll=120,
                       token="secret-token", url="secret-title")
            diag.event("MEDIA_CMD_RX", action="NEXT", title="secret-title")
            diag.event("MEDIA_CONTROL", action="secret-title", result="failure")
            diag.event("SPOTIFY_API_429_TOTAL", total_429=7,
                       legacy_events_included=1, token="secret-token")
            diag.event("ART_CAPABILITY", result="success", protocol="art2",
                       challenge="secret-token")
            diag.event("ART_SENT", protocol="invalid", bytes=37632)
            bundle = diag.export(root / "Desktop")
            try:
                with zipfile.ZipFile(bundle) as archive:
                    self.assertLessEqual(len(archive.namelist()), 5)
                    self.assertIn("metadata.json", archive.namelist())
                    contents = b"".join(archive.read(name) for name in archive.namelist())
                    self.assertNotIn(b"secret-title", contents)
                    self.assertNotIn(b"secret-token", contents)
                    self.assertIn(b"ART_FETCH", contents)
                    self.assertIn(b"error_type=OtherError", contents)
                    self.assertIn(b"SPOTIFY_API_429 reason=quota_exceeded", contents)
                    self.assertIn(b"request_kind=playback_poll", contents)
                    self.assertIn(b"MEDIA_CMD_RX action=NEXT", contents)
                    self.assertIn(b"SPOTIFY_API_429_TOTAL total_429=7", contents)
                    self.assertIn(b"ART_CAPABILITY result=success protocol=art2", contents)
                    self.assertIn(b"ART_SENT bytes=37632", contents)
                    self.assertNotIn(b"protocol=invalid", contents)
                    self.assertNotIn(b"action=secret-title", contents)
            finally:
                diag._logger.removeHandler(diag._handler)
                diag._handler.close()

    def test_tray_export_reveals_saved_folder(self):
        tray = BongoCatSystemTray.__new__(BongoCatSystemTray)
        tray.show_notification = Mock()
        names = [entry.text for entry in tray.create_menu() if hasattr(entry, "text")]
        self.assertIn("Export diagnostics ZIP...", names)
        package = Path("C:/Users/Example/Desktop/BongoDesk-diagnostics.zip")
        with patch("tray.diagnostics.export", return_value=package), \
             patch("tray.os.startfile", create=True) as reveal:
            tray.export_diagnostics()
        reveal.assert_called_once_with(str(package.parent))
        tray.show_notification.assert_called_once()


class ArtworkRetryTests(unittest.TestCase):
    def make_bridge(self):
        bridge = WindowsMediaBridge(on_update=Mock())
        bridge._spotify = Mock()
        bridge._spotify.download_artwork.return_value = b"cover"
        bridge._artwork_retry_attempts = 2
        return bridge

    def test_api_conversion_failure_retries_same_track(self):
        bridge = self.make_bridge()
        with patch.object(bridge, "_to_vinyl_rgb888",
                          side_effect=[ValueError("corrupt"), b"rgb"]), \
             patch("media_bridge.time.monotonic") as clock:
            clock.return_value = 100
            self.assertIsNone(asyncio.run(bridge._try_api_artwork("track", "url")))
            self.assertEqual(bridge._api_artwork_complete_key, "")
            clock.return_value = 102
            self.assertEqual(asyncio.run(bridge._try_api_artwork("track", "url")), b"rgb")
        self.assertEqual(bridge._api_artwork_complete_key, "track")
        self.assertEqual(bridge._spotify.download_artwork.call_count, 2)

    def test_exhausted_api_retries_after_long_cooldown(self):
        bridge = self.make_bridge()
        bridge._spotify.download_artwork.side_effect = [None, None, b"cover"]
        with patch.object(bridge, "_to_vinyl_rgb888", return_value=b"rgb"), \
             patch("media_bridge.time.monotonic") as clock:
            clock.return_value = 100
            self.assertIsNone(asyncio.run(bridge._try_api_artwork("track", "url")))
            clock.return_value = 102
            self.assertIsNone(asyncio.run(bridge._try_api_artwork("track", "url")))
            clock.return_value = 150
            self.assertIsNone(asyncio.run(bridge._try_api_artwork("track", "url")))
            self.assertEqual(bridge._spotify.download_artwork.call_count, 2)
            clock.return_value = 193
            self.assertEqual(asyncio.run(bridge._try_api_artwork("track", "url")), b"rgb")
        self.assertEqual(bridge._spotify.download_artwork.call_count, 3)

    def test_windows_thumbnail_retries_same_track_after_cooldown(self):
        bridge = self.make_bridge()
        now = dt.datetime.now(dt.timezone.utc)
        session = Mock(source_app_user_model_id="Spotify.exe")
        session.try_get_media_properties_async = AsyncMock(return_value=SimpleNamespace(
            title="Private title", artist="Private artist", album_artist="",
            album_title="", track_number=1, thumbnail=object(),
        ))
        session.get_playback_info.return_value.playback_status = "PLAYING"
        session.get_timeline_properties.return_value = SimpleNamespace(
            position=dt.timedelta(seconds=1), end_time=dt.timedelta(seconds=100),
            last_updated_time=now,
        )
        with patch.object(bridge, "_read_thumbnail", new_callable=AsyncMock,
                          side_effect=[b"", b"", b"cover"]) as read, \
             patch.object(bridge, "_to_vinyl_rgb888", return_value=b"rgb"), \
             patch("media_bridge.time.monotonic") as clock:
            clock.return_value = 100
            self.assertIsNone(asyncio.run(bridge._read_session(session))[1])
            clock.return_value = 102
            self.assertIsNone(asyncio.run(bridge._read_session(session))[1])
            clock.return_value = 150
            self.assertIsNone(asyncio.run(bridge._read_session(session))[1])
            self.assertEqual(read.await_count, 2)
            clock.return_value = 193
            self.assertEqual(asyncio.run(bridge._read_session(session))[1], b"rgb")
        self.assertEqual(read.await_count, 3)

    def test_missing_windows_thumbnail_uses_paced_matching_api_art_only(self):
        bridge = self.make_bridge()
        bridge._windows_artwork_missing_reported = True
        bridge._spotify.get_playback.return_value = (
            {"title": "Private title", "artist": "Private artist",
             "track_key": "spotify:track"}, "https://example.invalid/cover"
        )
        snapshot = SimpleNamespace(
            available=True, track_key="windows:track", title="Private title",
            artist="Private artist",
        )
        session = Mock(source_app_user_model_id="Spotify.exe")
        with patch.object(bridge, "_try_api_artwork", new_callable=AsyncMock,
                          return_value=b"rgb") as fetch, \
             patch("media_bridge.time.monotonic", return_value=100):
            self.assertEqual(asyncio.run(
                bridge._try_windows_api_artwork(snapshot, session)), b"rgb")
            self.assertIsNone(asyncio.run(
                bridge._try_windows_api_artwork(snapshot, session)))
        bridge._spotify.get_playback.assert_called_once_with(artwork_fallback=True)
        fetch.assert_awaited_once_with("spotify:track", "https://example.invalid/cover")

    def test_api_fallback_rejects_other_song_and_waits_before_recheck(self):
        bridge = self.make_bridge()
        bridge._windows_artwork_missing_reported = True
        bridge._spotify.get_playback.return_value = (
            {"title": "Another song", "artist": "Private artist",
             "track_key": "spotify:other"}, "url"
        )
        snapshot = SimpleNamespace(
            available=True, track_key="windows:track", title="Private title",
            artist="Private artist",
        )
        session = Mock(source_app_user_model_id="Spotify.exe")
        with patch.object(bridge, "_try_api_artwork", new_callable=AsyncMock) as fetch, \
             patch("media_bridge.time.monotonic", return_value=100):
            self.assertIsNone(asyncio.run(
                bridge._try_windows_api_artwork(snapshot, session)))
            self.assertIsNone(asyncio.run(
                bridge._try_windows_api_artwork(snapshot, session)))
        bridge._spotify.get_playback.assert_called_once_with(artwork_fallback=True)
        fetch.assert_not_awaited()

    def test_api_cover_is_fetched_again_when_song_returns_after_windows_cover(self):
        bridge = self.make_bridge()
        now = dt.datetime.now(dt.timezone.utc)
        session = Mock(source_app_user_model_id="Spotify.exe")
        def properties(title, thumbnail):
            return SimpleNamespace(title=title, artist="Artist", album_artist="",
                                   album_title="", track_number=1, thumbnail=thumbnail)
        session.try_get_media_properties_async = AsyncMock(side_effect=[
            properties("Song A", None), properties("Song B", object()),
            properties("Song A", None),
        ])
        session.get_playback_info.return_value.playback_status = "PLAYING"
        session.get_timeline_properties.return_value = SimpleNamespace(
            position=dt.timedelta(seconds=1), end_time=dt.timedelta(seconds=100),
            last_updated_time=now,
        )
        bridge._spotify.get_playback.return_value = (
            {"title": "Song A", "artist": "Artist", "track_key": "spotify:A"}, "url"
        )
        with patch.object(bridge, "_read_thumbnail", new_callable=AsyncMock,
                          return_value=b"windows-cover"), \
             patch.object(bridge, "_to_vinyl_rgb888", return_value=b"rgb"), \
             patch("media_bridge.time.monotonic") as clock:
            clock.return_value = 100
            first, art = asyncio.run(bridge._read_session(session))
            self.assertIsNone(art)
            self.assertEqual(asyncio.run(
                bridge._try_windows_api_artwork(first, session)), b"rgb")
            clock.return_value = 101
            second, art = asyncio.run(bridge._read_session(session))
            self.assertEqual(second.title, "Song B")
            self.assertEqual(art, b"rgb")
            clock.return_value = 102
            again, art = asyncio.run(bridge._read_session(session))
            self.assertIsNone(art)
            self.assertEqual(asyncio.run(
                bridge._try_windows_api_artwork(again, session)), b"rgb")
        self.assertEqual(bridge._spotify.download_artwork.call_count, 2)


if __name__ == "__main__":
    unittest.main()
