"""Local Spotify controls must not replace Windows state with an API snapshot."""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))

from media_bridge import MediaSnapshot, WindowsMediaBridge  # noqa: E402


class LocalMediaControlTests(unittest.TestCase):
    def test_touch_skip_uses_windows_session_without_api_snapshot(self):
        snapshots = []
        bridge = WindowsMediaBridge(on_update=lambda snapshot, artwork: (
            snapshots.append(snapshot), bridge._stop.set()
        ))
        bridge._spotify = Mock(is_ready=True)
        bridge._pending_spotify_command = "PREVIOUS"
        session = Mock(source_app_user_model_id="Spotify.exe")
        session.try_skip_next_async = AsyncMock(return_value=True)
        manager = Mock()
        manager.get_sessions.return_value = [session]
        local = MediaSnapshot(available=True, source="SPOTIFY", title="New",
                              artist="Artist", playing=True, track_key="windows:new")
        bridge._read_session = AsyncMock(return_value=(local, None))
        bridge._windows_api_artwork_due = Mock(return_value=False)
        bridge.control("NEXT")

        with patch("media_bridge.GlobalSystemMediaTransportControlsSessionManager.request_async",
                   new_callable=AsyncMock, return_value=manager), \
             patch("media_bridge.diagnostics.event") as event:
            asyncio.run(asyncio.wait_for(bridge._run(), timeout=2))

        session.try_skip_next_async.assert_awaited_once_with()
        bridge._spotify.get_playback.assert_not_called()
        self.assertIsNone(bridge._pending_spotify_command)
        session.try_skip_previous_async.assert_not_called()
        self.assertEqual(snapshots, [local])
        event.assert_any_call("MEDIA_CONTROL", action="NEXT", result="success")

    def test_windows_rejection_is_reported_without_fake_success(self):
        bridge = WindowsMediaBridge(on_update=Mock())
        session = Mock()
        session.try_toggle_play_pause_async = AsyncMock(return_value=False)
        bridge.control("PLAY_PAUSE")
        with patch("media_bridge.diagnostics.event") as event:
            self.assertFalse(asyncio.run(bridge._handle_commands(session)))
        event.assert_any_call("MEDIA_CONTROL", action="PLAY_PAUSE", result="failure")


if __name__ == "__main__":
    unittest.main()
