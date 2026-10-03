"""Spotify 429 cooldown, API-only pacing and display fallback."""

import asyncio
import io
import json
import sys
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))

from media_bridge import MediaSnapshot, WindowsMediaBridge  # noqa: E402
from spotify_api import SpotifyApiBridge, SpotifyRateLimitError  # noqa: E402


class SpotifyCooldownTests(unittest.TestCase):
    def test_real_quota_429_is_classified_logged_and_persisted_once(self):
        with tempfile.TemporaryDirectory() as folder:
            token_path = Path(folder) / "tokens.json"
            bridge = SpotifyApiBridge("client", token_path)
            bridge._tokens.update(access_token="secret", refresh_token="secret",
                                  expires_at=time.time() + 72000)
            error = urllib.error.HTTPError(
                "https://api.spotify.com/v1/me/player", 429, "limited",
                {"Retry-After": "36000"},
                io.BytesIO(json.dumps({"error": {"status": 429,
                                                 "reason": "QUOTA_EXCEEDED"}}).encode()),
            )
            with patch("spotify_api.urllib.request.urlopen", side_effect=error) as http, \
                 patch("spotify_api.diagnostics.event") as event:
                with self.assertRaises(SpotifyRateLimitError) as raised:
                    bridge.get_playback()
            self.assertFalse(raised.exception.cached)
            self.assertEqual(raised.exception.reason, "quota_exceeded")
            self.assertEqual(raised.exception.request_kind, "playback_poll")
            self.assertEqual(bridge.status()["limit_reason"], "quota_exceeded")
            self.assertEqual(http.call_count, 1)
            actual_429 = [call for call in event.call_args_list
                          if call.args[0] == "SPOTIFY_API_429"]
            self.assertEqual(len(actual_429), 1)
            self.assertEqual(actual_429[0].kwargs["request_kind"], "playback_poll")
            self.assertEqual(actual_429[0].kwargs["wait_seconds"], 36000)
            self.assertEqual(actual_429[0].kwargs["playback_poll"], 1)
            self.assertNotIn("secret", str(actual_429[0]))

            restarted = SpotifyApiBridge("client", token_path)
            with patch("spotify_api.urllib.request.urlopen") as http:
                with self.assertRaises(SpotifyRateLimitError) as cached:
                    restarted.get_playback()
                self.assertTrue(cached.exception.cached)
                http.assert_not_called()

            response = MagicMock()
            response.__enter__.return_value = response
            response.read.return_value = json.dumps({
                "item": {"id": "track", "name": "Song", "artists": [{"name": "Artist"}],
                         "duration_ms": 60000},
                "is_playing": True, "progress_ms": 1000,
            }).encode()
            after_retry = restarted._tokens["rate_limit_until"] + 1
            with patch("spotify_api.time.time", return_value=after_retry), \
                 patch("spotify_api.urllib.request.urlopen", return_value=response) as http:
                playback, _ = restarted.get_playback()
            self.assertEqual(playback["title"], "Song")
            http.assert_called_once()

    def test_unknown_429_reason_is_not_guessed(self):
        self.assertEqual(SpotifyApiBridge._classify_429(b"not json"),
                         "unspecified_429")
        self.assertEqual(SpotifyApiBridge._classify_429(b'{"error":{"message":"x"}}'),
                         "unspecified_429")

    def test_usage_summary_categorizes_calls_without_paths_or_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge = SpotifyApiBridge("client", Path(folder) / "tokens.json")
            bridge._api_usage_started_at = 100
            bridge._api_usage_counts["playback_poll"] = 42
            with patch("spotify_api.diagnostics.event") as event:
                bridge._record_api_request("playback_urgent", 1000)
            event.assert_called_once()
            self.assertEqual(event.call_args.args, ("SPOTIFY_API_USAGE",))
            self.assertEqual(event.call_args.kwargs["playback_poll"], 42)
            self.assertEqual(event.call_args.kwargs["window_seconds"], 900)
            self.assertEqual(bridge._api_usage_counts["playback_urgent"], 1)
            self.assertEqual(bridge._api_usage_counts["playback_poll"], 0)

    def test_waiting_status_uses_existing_media_fields_and_no_stale_commands(self):
        on_update = Mock()
        bridge = WindowsMediaBridge(on_update=on_update)
        bridge._spotify = Mock(is_ready=True)
        bridge._spotify.status.return_value = {
            "state": "rate_limited", "retry_until": time.time() + 36000,
        }
        bridge._spotify.poll_delay_seconds.return_value = 0.5
        bridge._last_snapshot = MediaSnapshot(available=True, track_key="same")
        bridge._api_artwork_key = "same"
        bridge._api_artwork_complete_key = "same"
        bridge.control("NEXT")
        self.assertEqual(bridge._api_only_poll_delay(idle=False), 15.0)

        bridge._publish_no_windows_status()
        bridge._publish_no_windows_status()
        self.assertEqual(on_update.call_count, 1)
        waiting = on_update.call_args.args[0]
        self.assertFalse(waiting.available)
        self.assertEqual(waiting.source, "SPOTIFY API")
        self.assertEqual(waiting.title, "Spotify API paused")
        self.assertTrue(waiting.artist.startswith("Retry "))
        self.assertEqual(bridge._current_source, "spotify_api")
        self.assertEqual(bridge._api_artwork_complete_key, "")
        self.assertTrue(bridge._commands.empty())

        bridge._spotify.download_artwork.return_value = b"cover"
        with patch.object(bridge, "_to_vinyl_rgb888", return_value=b"rgb"):
            self.assertEqual(asyncio.run(bridge._try_api_artwork("same", "url")), b"rgb")
        bridge._spotify.download_artwork.assert_called_once_with("url")

    def test_no_windows_session_recovers_after_long_429_without_premature_poll(self):
        snapshots = []
        bridge = WindowsMediaBridge(on_update=lambda snapshot, art: snapshots.append(snapshot))
        retry_until = time.time() + 1.0
        spotify = Mock(is_ready=True)
        spotify.status.side_effect = lambda: (
            {"state": "rate_limited", "retry_until": retry_until}
            if time.time() < retry_until else {"state": "ready"}
        )
        spotify.get_playback.side_effect = [
            SpotifyRateLimitError(1, "quota_exceeded", "playback_poll", cached=True),
            ({"title": "Recovered", "artist": "Artist", "playing": True,
              "position_seconds": 0, "duration_seconds": 60,
              "track_key": "spotify:track"}, None),
        ]
        spotify.poll_delay_seconds.return_value = 0.5
        bridge._spotify = spotify
        manager = Mock()
        manager.get_sessions.return_value = []

        def on_update(snapshot, artwork):
            snapshots.append(snapshot)
            if snapshot.available:
                bridge._stop.set()

        bridge._on_update = on_update
        with patch("media_bridge.GlobalSystemMediaTransportControlsSessionManager.request_async",
                   new_callable=AsyncMock, return_value=manager), \
             patch.object(bridge, "_wait_for_spotify_work", new_callable=AsyncMock) as wait, \
             patch("media_bridge.diagnostics.event") as event:
            asyncio.run(asyncio.wait_for(bridge._run(), timeout=3.0))

        self.assertEqual(spotify.get_playback.call_count, 2)
        wait.assert_awaited_once_with(15.0)
        fallbacks = [call for call in event.call_args_list
                     if call.args[0] == "SPOTIFY_FALLBACK"]
        self.assertEqual(len(fallbacks), 1)
        self.assertEqual(fallbacks[0].kwargs["origin"], "saved_cooldown")
        self.assertEqual(snapshots[0].title, "Spotify API paused")
        self.assertFalse(snapshots[0].available)
        self.assertEqual(snapshots[-1].title, "Recovered")
        self.assertTrue(snapshots[-1].available)


if __name__ == "__main__":
    unittest.main()
