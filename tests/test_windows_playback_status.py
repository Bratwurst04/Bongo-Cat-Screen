"""Use the actual WinRT IntEnum, whose str() changed in Python 3.11."""

import asyncio
import datetime as dt
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "companion"),
                str(Path(__file__).resolve().parent)]
from media_bridge import WindowsMediaBridge
import test_power_resume as power_resume
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status


class WindowsPlaybackStatusTests(unittest.TestCase):
    def session(self, status, source="Spotify.exe"):
        session = Mock(source_app_user_model_id=source)
        session.try_get_media_properties_async = AsyncMock(return_value=SimpleNamespace(
            title="Synthetic track", artist="Synthetic artist", album_artist="",
            album_title="", track_number=1, thumbnail=None))
        session.get_playback_info.return_value = SimpleNamespace(playback_status=status)
        session.get_timeline_properties.return_value = SimpleNamespace(
            position=dt.timedelta(seconds=3), end_time=dt.timedelta(seconds=180),
            last_updated_time=dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=5))
        return session

    def test_real_windows_status_reaches_snapshot_and_wire(self):
        for status, playing, wire in ((Status.PLAYING, True, b"MEDIA_STATE:PLAYING\n"),
                                      (Status.PAUSED, False, b"MEDIA_STATE:PAUSED\n"),
                                      (Status.STOPPED, False, b"MEDIA_STATE:PAUSED\n")):
            with self.subTest(status=status.name):
                engine = power_resume.PowerResumeTests().make_engine()
                bridge = WindowsMediaBridge(on_update=engine._on_media_update)
                snapshot, art = asyncio.run(bridge._read_session(self.session(status)))
                bridge._publish(snapshot, art)
                self.assertIs(snapshot.playing, playing)
                self.assertEqual(engine._last_media_state, "PLAYING" if playing else "PAUSED")
                payload = b"".join(call.args[0] for call in engine.serial_conn.write.call_args_list)
                self.assertIn(wire, payload)
                self.assertEqual(snapshot.duration_seconds, 180)
                self.assertGreaterEqual(snapshot.position_seconds, 8 if playing else 3)
                if not playing:
                    self.assertEqual(snapshot.position_seconds, 3)

    def test_same_track_play_pause_play_updates_wire_without_metadata_change(self):
        engine = power_resume.PowerResumeTests().make_engine()
        bridge = WindowsMediaBridge(on_update=engine._on_media_update)
        session = self.session(Status.PLAYING)
        keys = []
        for status in (Status.PLAYING, Status.PAUSED, Status.PLAYING):
            session.get_playback_info.return_value.playback_status = status
            snapshot, art = asyncio.run(bridge._read_session(session))
            keys.append(snapshot.track_key)
            bridge._publish(snapshot, art)
        wire = b"".join(call.args[0] for call in engine.serial_conn.write.call_args_list)
        self.assertEqual(len(set(keys)), 1)
        self.assertEqual([line for line in wire.splitlines() if line.startswith(b"MEDIA_STATE:")],
                         [b"MEDIA_STATE:PLAYING", b"MEDIA_STATE:PAUSED", b"MEDIA_STATE:PLAYING"])

    def test_non_spotify_session_detection_uses_real_enum(self):
        manager = Mock()
        for status in (Status.PLAYING, Status.PAUSED, Status.STOPPED):
            with self.subTest(status=status.name):
                manager.get_sessions.return_value = [self.session(status, "OtherPlayer.exe")]
                self.assertEqual(WindowsMediaBridge._find_media_sources(manager),
                                 (None, status == Status.PLAYING))

    def test_existing_spotify_priority_is_preserved(self):
        spotify = self.session(Status.PAUSED)
        manager = Mock()
        manager.get_sessions.return_value = [self.session(Status.PLAYING, "OtherPlayer.exe"), spotify]
        self.assertEqual(WindowsMediaBridge._find_media_sources(manager), (spotify, False))


if __name__ == "__main__":
    unittest.main()
