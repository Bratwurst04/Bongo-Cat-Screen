"""Request-start pacing with fake wall clock/HTTP; no Spotify or user profile."""

import asyncio
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))

from config import ConfigManager
from media_bridge import WindowsMediaBridge
from spotify_api import SpotifyPacingError, SpotifyRateLimitError
from transport_budget import TransportSpotifyApiBridge as SpotifyApiBridge


class AdaptiveConnectTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "tokens.json"
        self.now = 1000.0
        self.clock = patch("spotify_api.time.time", side_effect=lambda: self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.api = SpotifyApiBridge("fixture-client", self.path, {
            "api_min_interval_seconds": 0.5,
            "api_initial_interval_seconds": 1,
            "api_idle_interval_seconds": 3,
        })
        self.api._tokens.update(access_token="fixture", refresh_token="fixture",
                                expires_at=1000000)
        self.starts = []

    def response(self, request, **kwargs):
        self.starts.append(self.now)
        self.now += 0.12  # HTTP latency must consume, not extend, the interval.
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({
            "item": {"id": "same", "name": "Song", "artists": [], "duration_ms": 60000},
            "is_playing": True, "progress_ms": 59500,
        }).encode()
        return response

    def test_active_worker_same_track_ignores_legacy_floor_and_http_latency(self):
        media = WindowsMediaBridge(on_update=Mock(), spotify_settings={
            "api_only_poll_interval_seconds": 15,
        })
        media._spotify = self.api
        manager = Mock()
        manager.get_sessions.return_value = []

        async def wait(seconds):
            self.now += seconds
            if len(self.starts) == 4:
                media._stop.set()

        with patch("spotify_api.urllib.request.urlopen", side_effect=self.response), \
             patch("media_bridge.GlobalSystemMediaTransportControlsSessionManager.request_async",
                   new_callable=AsyncMock, return_value=manager), \
             patch.object(media, "_try_api_artwork", new_callable=AsyncMock), \
             patch.object(media, "_wait_for_spotify_work", side_effect=wait):
            asyncio.run(media._run())
        self.assertEqual(self.starts, [1000, 1000.5, 1001, 1001.5])
        self.assertEqual(media.status()["effective_poll_interval_seconds"], 0.5)
        self.assertEqual(media.status()["polling_mode"], "adaptive")

    def test_poll_controls_and_urgent_confirmation_share_the_gate(self):
        with patch("spotify_api.urllib.request.urlopen", side_effect=self.response) as http:
            self.api.get_playback()
            for action in (lambda: self.api.control("NEXT"),
                           lambda: self.api.get_playback(urgent=True)):
                with self.assertRaises(SpotifyPacingError):
                    action()
            self.now = 1000.5
            self.api.control("NEXT")
            with self.assertRaises(SpotifyPacingError):
                self.api.control("PREVIOUS")
            self.now = 1001
            self.api.get_playback(urgent=True)
        self.assertEqual(http.call_count, 3)
        self.assertEqual(self.starts, [1000, 1000.5, 1001])

    def test_429_restart_deadline_and_gradual_margin_recovery(self):
        error = urllib.error.HTTPError("fixture", 429, "limited", {"Retry-After": "10"},
                                       io.BytesIO(b'{"error":{"reason":"RATE_LIMITED"}}'))
        with patch("spotify_api.urllib.request.urlopen", side_effect=error):
            with self.assertRaises(SpotifyRateLimitError):
                self.api.get_playback()
        self.assertEqual(self.api._current_interval(), 1)
        self.assertEqual(self.api.poll_delay_seconds(), 10)
        self.now = 1005
        self.api = SpotifyApiBridge("fixture-client", self.path, {
            "api_min_interval_seconds": 0.5, "api_initial_interval_seconds": 1,
        })
        with patch("spotify_api.urllib.request.urlopen", side_effect=self.response) as http:
            for now in (1005, 1009.999):
                self.now = now
                for action in (self.api.get_playback,
                               lambda: self.api.get_playback(urgent=True),
                               lambda: self.api.control("NEXT")):
                    with self.assertRaises(SpotifyRateLimitError):
                        action()
            http.assert_not_called()
            self.now = 1010
            self.api.get_playback()
            self.assertEqual(self.api._current_interval(), 1)
            self.assertGreater(self.api.poll_delay_seconds(), 0.8)
            self.now = 1039.9
            self.api.get_playback()
            self.assertEqual(self.api._current_interval(), 1)
            self.now = 1040.5
            with self.assertRaises(SpotifyPacingError):
                self.api.get_playback(urgent=True)
            for _ in range(8):
                self.now += 600.1
                self.api.get_playback()
            self.assertEqual(self.api._current_interval(), 0.5)
            self.assertEqual(self.api.status()["pacing"]["safe_interval_seconds"], 0.5)
        persisted = json.loads(self.path.read_text())
        self.assertEqual(persisted["refresh_token"], "fixture")
        self.assertEqual(persisted["adaptive_total_429"], 1)
        self.assertEqual(persisted["adaptive_rate_limit_events"], [1000])
        self.assertEqual(persisted["rate_limit_until"], 1010)

    def test_quota_and_idle_deadlines_survive_the_removed_connect_floor(self):
        with patch("spotify_api.urllib.request.urlopen", side_effect=self.response):
            self.api.get_playback()
        self.assertAlmostEqual(self.api.poll_delay_seconds(idle=True), 2.88)
        self.api._record_rate_limit(60, "quota_exceeded", "playback_poll")
        self.api._save_tokens()
        until = self.api._tokens["rate_limit_until"]
        self.now = until - 1
        with self.assertRaises(SpotifyRateLimitError):
            self.api.get_playback()
        self.now = until
        with patch("spotify_api.urllib.request.urlopen", side_effect=self.response):
            self.api.get_playback()
        current = self.api._current_interval()
        self.now += 30
        self.api._record_success()
        self.assertEqual(self.api._current_interval(), current)
        # Transport fixture has no policy interval: active day follows the
        # retained adaptive gate; explicit idle still keeps local recovery.
        self.assertEqual(self.api.poll_interval_seconds(), current)
        self.assertEqual(self.api.poll_interval_seconds(idle=True), 60)
        self.assertAlmostEqual(self.api.poll_delay_seconds(idle=True), 29.88)
        with patch("spotify_api.urllib.request.urlopen", side_effect=self.response) as http:
            self.api.get_playback()
            http.assert_called_once()
        self.api.configure_pacing({"api_min_interval_seconds": 0.5,
                                   "api_reset_safety_requested_at": self.now})
        self.assertEqual(self.api.poll_interval_seconds(), 0.5)
        self.assertEqual(self.api.poll_interval_seconds(idle=True), 60)

    def test_old_profile_deprecated_key_keeps_config_and_tokens(self):
        profile = Path(self.folder.name) / "config.json"
        original = json.loads((ROOT / "companion/default_config.json").read_text())
        original["spotify"].update(api_only_poll_interval_seconds=15, custom_value="keep")
        profile.write_text(json.dumps(original))
        token_bytes = b'{"refresh_token":"fixture","rate_limit_until":999999}'
        token_path = profile.parent / "spotify_tokens.json"
        token_path.write_bytes(token_bytes)
        before = profile.read_bytes()
        config = ConfigManager(self.folder.name)
        self.assertEqual(profile.read_bytes(), before)
        self.assertEqual(config.get_setting("spotify", "api_only_poll_interval_seconds"), 15)
        config.set_setting("display", "show_wpm", False)
        config.save_config()
        saved = json.loads(profile.read_text())
        self.assertEqual(saved["spotify"], {**config.default_config["spotify"], **original["spotify"]})
        self.assertEqual(token_path.read_bytes(), token_bytes)

    def test_start_is_idempotent_for_an_existing_poll_worker(self):
        media = WindowsMediaBridge(on_update=Mock())
        media._thread = Mock(is_alive=Mock(return_value=True))
        with patch("media_bridge.threading.Thread") as worker:
            media.start()
            media.start()
        worker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
