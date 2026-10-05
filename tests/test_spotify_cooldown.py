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
from spotify_api import SpotifyApiBridge, SpotifyPacingError, SpotifyRateLimitError  # noqa: E402
from config import ConfigManager  # noqa: E402


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
            self.assertEqual(actual_429[0].kwargs["total_429"], 1)
            self.assertNotIn("secret", str(actual_429[0]))

            restarted = SpotifyApiBridge("client", token_path)
            self.assertEqual(restarted.status()["pacing"]["rate_limits"]["total"], 1)
            self.assertEqual(restarted.poll_interval_seconds(), 60.0)
            with patch("spotify_api.urllib.request.urlopen") as http:
                with self.assertRaises(SpotifyRateLimitError) as cached:
                    restarted.get_playback()
                self.assertTrue(cached.exception.cached)
                http.assert_not_called()
            self.assertEqual(restarted.status()["pacing"]["rate_limits"]["total"], 1)

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
            self.assertEqual(restarted.poll_interval_seconds(), 60.0)

    def test_total_429_migrates_all_retained_events_and_never_resets_on_configure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tokens.json"
            now = time.time()
            path.write_text(json.dumps({
                "refresh_token": "secret", "adaptive_rate_limit_events": [
                    now - 3600, now - 25 * 3600, now - 10,
                ],
            }), encoding="utf-8")
            bridge = SpotifyApiBridge("client", path)
            counts = bridge.status()["pacing"]["rate_limits"]
            self.assertEqual(counts["total"], 3)
            self.assertEqual(counts["legacy_events_included"], 3)
            bridge.configure_pacing({"api_min_interval_seconds": 0.5,
                                     "api_reset_safety_requested_at": now + 1})
            self.assertEqual(SpotifyApiBridge("client", path).status()["pacing"]
                             ["rate_limits"]["total"], 3)
            with patch("spotify_api.time.time", return_value=now + 2 * 24 * 3600):
                later = SpotifyApiBridge("client", path).status()["pacing"]["rate_limits"]
            self.assertEqual(later["total"], 3)
            self.assertEqual(later["last_24_hours"], 0)

    def test_legacy_last_limit_is_a_lower_bound_when_event_list_is_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tokens.json"
            path.write_text(json.dumps({
                "refresh_token": "secret", "adaptive_last_limit_at": time.time() - 100000,
            }), encoding="utf-8")
            first = SpotifyApiBridge("client", path).status()["pacing"]["rate_limits"]
            second = SpotifyApiBridge("client", path).status()["pacing"]["rate_limits"]
            self.assertEqual(first["total"], 1)
            self.assertEqual(second["total"], 1)

    def test_rate_limit_and_quota_recovery_are_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge = SpotifyApiBridge("client", Path(folder) / "tokens.json")
            bridge._tokens["refresh_token"] = "secret"
            with patch("spotify_api.time.time", return_value=1000):
                bridge._record_rate_limit(30, "rate_limited", "playback_poll")
                self.assertEqual(bridge._quota_poll_floor(), 0)
                self.assertEqual(bridge.status()["pacing"]["rate_limits"]["total"], 1)
                bridge._record_rate_limit(36000, "quota_exceeded", "playback_poll")
                self.assertEqual(bridge._quota_poll_floor(), 60)
                self.assertEqual(bridge.status()["pacing"]["rate_limits"]["total"], 2)
            with patch("spotify_api.time.time", return_value=37000):
                previous = bridge._current_interval()
                bridge._record_success()
                self.assertEqual(bridge._current_interval(), previous)
                self.assertEqual(bridge.poll_interval_seconds(), 60)
                bridge.configure_pacing({
                    "api_min_interval_seconds": 0.5,
                    "api_reset_safety_requested_at": 37000,
                })
                self.assertEqual(bridge.poll_interval_seconds(), 60)

    def test_configured_connect_floor_and_window_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("builtins.print"):
                config = ConfigManager(folder)
            candidate = json.loads(json.dumps(config.default_config))
            candidate["spotify"]["api_only_poll_interval_seconds"] = 10
            with patch("builtins.print"):
                self.assertTrue(config.validate_config(candidate))
                candidate["connection"]["baudrate"] = 230400
                self.assertTrue(config.validate_config(candidate))
                candidate["spotify"]["api_only_poll_interval_seconds"] = 9.9
                self.assertFalse(config.validate_config(candidate))
                candidate["spotify"]["api_only_poll_interval_seconds"] = 121
                self.assertFalse(config.validate_config(candidate))

            media = WindowsMediaBridge(on_update=Mock(), spotify_settings={
                "api_only_poll_interval_seconds": 10,
            })
            media._spotify = Mock(is_ready=True)
            media._spotify.status.return_value = {"state": "ready"}
            media._spotify.poll_interval_seconds.return_value = 3
            media._spotify.poll_delay_seconds.return_value = 0.5
            media._current_source = "spotify_api"
            self.assertEqual(media._api_only_poll_delay(idle=False), 10)
            self.assertEqual(media.status()["effective_poll_interval_seconds"], 10)
            media._spotify.poll_interval_seconds.return_value = 60
            self.assertEqual(media._api_only_poll_delay(idle=False), 60)
            self.assertEqual(media.status()["effective_poll_interval_seconds"], 60)

            api = SpotifyApiBridge("client", Path(folder) / "tokens.json")
            api._tokens["refresh_token"] = "secret"
            api._request_times.extend([time.time() - 29, time.time() - 1])
            api._request_times_15m.extend([time.time() - 500, time.time() - 1])
            pacing = api.status()["pacing"]
            self.assertEqual(pacing["calls_last_30_seconds"], 2)
            self.assertEqual(pacing["calls_last_15_minutes"], 2)

    def test_one_end_probe_replaces_regular_poll_without_bypassing_safety(self):
        media = WindowsMediaBridge(on_update=Mock())
        media._spotify = Mock(is_ready=True)
        media._spotify.poll_interval_seconds.return_value = 3
        media._spotify.poll_delay_seconds.return_value = 0.5
        media._spotify.status.return_value = {"state": "ready", "pacing": {
            "quota_poll_floor_seconds": 0,
        }}
        nearly_done = MediaSnapshot(available=True, source="SPOTIFY API", playing=True,
                                    track_key="track", duration_seconds=180,
                                    position_seconds=170)
        with patch("media_bridge.diagnostics.event") as event:
            self.assertEqual(media._api_only_poll_delay(False, nearly_done), 10.75)
            self.assertEqual(media._api_only_poll_delay(False, nearly_done), 15)
        event.assert_called_once_with("SPOTIFY_END_PROBE", interval_ms=10750)
        media._spotify.poll_interval_seconds.return_value = 20
        other = MediaSnapshot(available=True, source="SPOTIFY API", playing=True,
                              track_key="other", duration_seconds=180,
                              position_seconds=175)
        self.assertEqual(media._api_only_poll_delay(False, other), 20)
        media._spotify.poll_interval_seconds.return_value = 60
        media._spotify.status.return_value = {"state": "ready", "pacing": {
            "quota_poll_floor_seconds": 60,
        }}
        self.assertEqual(media._api_only_poll_delay(False, other), 60)

    def test_touch_control_uses_guarded_urgent_request_and_prompt_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            api = SpotifyApiBridge("client", Path(folder) / "tokens.json")
            api._tokens["refresh_token"] = "secret"
            with patch.object(api, "_api_request") as request:
                api.control("NEXT")
            request.assert_called_once_with("POST", "/me/player/next",
                                            empty_ok=True, urgent=True)
        media = WindowsMediaBridge(on_update=Mock())
        spotify = Mock(is_ready=True)
        spotify.status.return_value = {"state": "ready"}
        spotify.get_playback.return_value = ({
            "title": "New", "artist": "Artist", "playing": True,
            "position_seconds": 0, "duration_seconds": 180,
            "track_key": "new",
        }, None)
        spotify.poll_interval_seconds.return_value = 15
        spotify.poll_delay_seconds.return_value = 0.5
        media._spotify = spotify
        media.control("NEXT")
        manager = Mock()
        manager.get_sessions.return_value = []

        def on_update(snapshot, artwork):
            if snapshot.available:
                media._stop.set()

        media._on_update = on_update
        with patch("media_bridge.GlobalSystemMediaTransportControlsSessionManager.request_async",
                   new_callable=AsyncMock, return_value=manager), \
             patch("media_bridge.asyncio.sleep", new_callable=AsyncMock), \
             patch.object(media, "_wait_for_spotify_work", new_callable=AsyncMock):
            asyncio.run(asyncio.wait_for(media._run(), timeout=2))
        spotify.control.assert_called_once_with("NEXT")
        spotify.get_playback.assert_called_once_with(urgent=True)

    def test_rapid_touch_is_retained_until_urgent_guard_allows_it(self):
        media = WindowsMediaBridge(on_update=Mock())
        media._spotify = Mock(is_ready=True)
        media._spotify.control.side_effect = [SpotifyPacingError(0.5), None, None]
        media.control("NEXT")
        media.control("PREVIOUS")
        with self.assertRaises(SpotifyPacingError):
            media._handle_spotify_commands()
        self.assertEqual(media._pending_spotify_command, "NEXT")
        self.assertTrue(media._handle_spotify_commands())
        self.assertIsNone(media._pending_spotify_command)
        self.assertEqual([call.args[0] for call in media._spotify.control.call_args_list],
                         ["NEXT", "NEXT", "PREVIOUS"])

    def test_unknown_429_reason_is_not_guessed(self):
        self.assertEqual(SpotifyApiBridge._classify_429(b"not json"),
                         "unspecified_429")
        self.assertEqual(SpotifyApiBridge._classify_429(b'{"error":{"message":"x"}}'),
                         "unspecified_429")
        self.assertEqual(SpotifyApiBridge._classify_429(
            b'{"error":{"reason":"RATE_LIMITED"}}'), "rate_limited")

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
        bridge._spotify.poll_interval_seconds.return_value = 0.5
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
        spotify.poll_interval_seconds.return_value = 0.5
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
