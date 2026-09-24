"""Small Spotify Web API client for BongoDesk Spotify Connect support.

Uses Authorization Code with PKCE, so a desktop build never needs to contain
or store a Spotify Client Secret. Tokens are kept in the user's BongoCat
configuration directory.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import math
from collections import deque
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional, Tuple


ACCOUNTS_URL = "https://accounts.spotify.com"
API_URL = "https://api.spotify.com/v1"
REDIRECT_URI = "http://127.0.0.1:43821/callback"
SCOPES = "user-read-playback-state user-read-currently-playing user-modify-playback-state"


class SpotifyApiError(RuntimeError):
    pass


class SpotifyRateLimitError(SpotifyApiError):
    def __init__(self, retry_after_seconds: float):
        self.retry_after_seconds = max(1.0, retry_after_seconds)
        super().__init__(f"Spotify rate limit; retry after {self.retry_after_seconds:.0f}s")


class SpotifyPacingError(SpotifyApiError):
    """Raised locally before an HTTP request would exceed our learned pace."""

    def __init__(self, wait_seconds: float):
        self.wait_seconds = max(0.05, wait_seconds)
        super().__init__(f"Spotify request paced; retry after {self.wait_seconds:.2f}s")


class SpotifyApiBridge:
    def __init__(self, client_id: str, token_path: Path, pacing_settings: Optional[dict] = None):
        self.client_id = (client_id or "").strip()
        self.token_path = Path(token_path)
        self._tokens = self._load_tokens()
        self._last_art_key = ""
        self._last_is_playing = False
        self._lock = threading.Lock()
        self._request_times = deque()
        self._pacing_settings = {}
        self._configure_pacing_locked(pacing_settings or {}, reset_if_missing=True)

    @property
    def is_ready(self) -> bool:
        return bool(self.client_id and self._tokens.get("refresh_token"))

    def status(self) -> dict:
        """Return local Spotify state without making a Web API request."""
        with self._lock:
            return self._status_locked()

    def _status_locked(self) -> dict:
        if not self.client_id:
            return {"state": "not_configured"}
        if not self._tokens.get("refresh_token"):
            return {"state": "not_linked"}

        self._trim_request_times()
        retry_until = self._rate_limit_until()
        remaining = max(0, math.ceil(retry_until - time.time()))
        pacing = self._pacing_status()
        if remaining:
            return {
                "state": "rate_limited",
                "retry_until": retry_until,
                "retry_remaining_seconds": remaining,
                "pacing": pacing,
            }
        return {"state": "ready", "pacing": pacing}

    def configure_pacing(self, pacing_settings: dict) -> None:
        """Apply local limits. This makes no Spotify request."""
        with self._lock:
            self._configure_pacing_locked(pacing_settings or {}, reset_if_missing=False)
            self._save_tokens()

    def poll_delay_seconds(self, idle: bool = False) -> float:
        """The next safe metadata poll delay, determined entirely locally."""
        with self._lock:
            now = time.time()
            due = max(now, self._next_allowed_at())
            delay = max(0.05, due - now)
            if idle:
                delay = max(delay, float(self._pacing_settings["idle_interval_seconds"]))
            return delay

    def authorize_interactive(self, timeout_seconds: int = 180) -> bool:
        if not self.client_id:
            raise SpotifyApiError("Spotify Client ID is missing")

        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        state = secrets.token_urlsafe(24)
        result = {}

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                result["code"] = query.get("code", [""])[0]
                result["state"] = query.get("state", [""])[0]
                result["error"] = query.get("error", [""])[0]
                ok = bool(result["code"] and result["state"] == state)
                body = (
                    "<html><body style='font-family:sans-serif;background:#101214;color:#fff;"
                    "text-align:center;padding:60px'><h1>Spotify anslutet</h1>"
                    "<p>Du kan stanga den har fliken och aterga till BongoDesk.</p></body></html>"
                    if ok else
                    "<html><body><h1>Spotify-kopplingen misslyckades</h1>"
                    "<p>Stang fliken och forsok igen.</p></body></html>"
                )
                payload = body.encode("utf-8")
                self.send_response(200 if ok else 400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                return

        server = HTTPServer(("127.0.0.1", 43821), CallbackHandler)
        server.timeout = timeout_seconds
        auth_query = urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "response_type": "code",
                "redirect_uri": REDIRECT_URI,
                "scope": SCOPES,
                "code_challenge_method": "S256",
                "code_challenge": challenge,
                "state": state,
            }
        )
        webbrowser.open(f"{ACCOUNTS_URL}/authorize?{auth_query}")
        server.handle_request()
        server.server_close()

        if result.get("error"):
            raise SpotifyApiError(f"Spotify authorization denied: {result['error']}")
        if not result.get("code") or result.get("state") != state:
            raise SpotifyApiError("Spotify authorization timed out or state did not match")

        payload = self._form_request(
            f"{ACCOUNTS_URL}/api/token",
            {
                "client_id": self.client_id,
                "grant_type": "authorization_code",
                "code": result["code"],
                "redirect_uri": REDIRECT_URI,
                "code_verifier": verifier,
            },
        )
        self._set_tokens(payload)
        return True

    def get_playback(self, urgent: bool = False) -> Tuple[Optional[dict], Optional[str]]:
        """Return playback metadata immediately and an optional artwork URL.

        Artwork is downloaded by the media bridge after metadata has already
        been published.  This keeps a slow cover request from making the
        display look as if nothing is playing.
        """
        if not self.is_ready:
            return None, None
        data = self._api_request(
            "GET", "/me/player?additional_types=track%2Cepisode", urgent=urgent
        )
        if not data or not data.get("item"):
            return None, None

        item = data["item"]
        item_type = item.get("type", "track")
        title = item.get("name") or "Unknown track"
        if item_type == "episode":
            show = item.get("show") or {}
            artist = show.get("name") or show.get("publisher") or "Spotify Podcast"
            images = item.get("images") or show.get("images") or []
        else:
            artist = ", ".join(
                value.get("name", "") for value in item.get("artists", [])
                if value.get("name")
            ) or "Unknown artist"
            images = (item.get("album") or {}).get("images") or []

        track_key = item.get("id") or item.get("uri") or title
        playback = {
            "source": "SPOTIFY",
            "title": title,
            "artist": artist,
            "playing": bool(data.get("is_playing")),
            "position_seconds": max(0, int((data.get("progress_ms") or 0) / 1000)),
            "duration_seconds": max(0, int((item.get("duration_ms") or 0) / 1000)),
            "track_key": f"spotify:{track_key}",
        }
        self._last_is_playing = playback["playing"]

        # Return the current URL on every metadata response. The bridge owns
        # the bounded retry policy, so a temporary thumbnail failure cannot
        # leave the generic record stuck forever.
        artwork_url = images[0].get("url") if images else None
        self._last_art_key = track_key
        return playback, artwork_url

    def download_artwork(self, url: str) -> bytes:
        return self._download(url) if url else b""

    def control(self, action: str) -> None:
        if not self.is_ready:
            return
        action = action.upper()
        if action == "PLAY_PAUSE":
            endpoint = "/me/player/pause" if self._last_is_playing else "/me/player/play"
            self._api_request("PUT", endpoint, empty_ok=True)
            self._last_is_playing = not self._last_is_playing
        elif action == "NEXT":
            self._api_request("POST", "/me/player/next", empty_ok=True)
        elif action == "PREVIOUS":
            self._api_request("POST", "/me/player/previous", empty_ok=True)

    def _access_token(self) -> str:
        if not self._tokens.get("access_token") or time.time() >= self._tokens.get("expires_at", 0) - 60:
            self._refresh()
        return self._tokens.get("access_token", "")

    def _refresh(self) -> None:
        refresh_token = self._tokens.get("refresh_token")
        if not refresh_token:
            raise SpotifyApiError("Spotify needs to be linked")
        payload = self._form_request(
            f"{ACCOUNTS_URL}/api/token",
            {
                "client_id": self.client_id,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        if "refresh_token" not in payload:
            payload["refresh_token"] = refresh_token
        self._set_tokens(payload)

    def _api_request(
        self, method: str, endpoint: str, empty_ok: bool = False, urgent: bool = False
    ):
        with self._lock:
            return self._api_request_locked(method, endpoint, empty_ok, retry=True, urgent=urgent)

    def _api_request_locked(
        self, method: str, endpoint: str, empty_ok: bool, retry: bool, urgent: bool = False
    ):
        now = time.time()
        retry_remaining = max(0, math.ceil(self._rate_limit_until() - now))
        if retry_remaining:
            # Spotify's Retry-After is authoritative.  Persisting this means a
            # restart cannot turn into a burst of retries while it is active.
            raise SpotifyRateLimitError(retry_remaining)
        # A screen-originated track change is an explicit user action, not a
        # polling loop. Allow it to confirm immediately, while keeping a
        # small local guard so rapid swiping cannot turn into a request burst.
        if urgent:
            urgent_next = float(self._tokens.get("adaptive_urgent_next_allowed_at", 0) or 0)
            if urgent_next > now:
                raise SpotifyPacingError(urgent_next - now)
            self._tokens["adaptive_urgent_next_allowed_at"] = now + 0.75
        next_allowed_at = self._next_allowed_at()
        if not urgent and next_allowed_at > now:
            raise SpotifyPacingError(next_allowed_at - now)
        self._request_times.append(now)
        self._tokens["adaptive_next_allowed_at"] = now + self._current_interval()
        self._tokens["adaptive_request_total"] = int(
            self._tokens.get("adaptive_request_total", 0)
        ) + 1
        token = self._access_token()
        request = urllib.request.Request(
            f"{API_URL}{endpoint}",
            data=b"" if method in ("POST", "PUT") else None,
            method=method,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                payload = response.read()
                self._record_success()
                if not payload:
                    return None
                return json.loads(payload.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 401 and retry:
                self._refresh()
                return self._api_request_locked(
                    method, endpoint, empty_ok, retry=False, urgent=urgent
                )
            if exc.code == 204 and empty_ok:
                return None
            if exc.code == 429:
                try:
                    retry_after = float(exc.headers.get("Retry-After", "60"))
                except (TypeError, ValueError):
                    retry_after = 60.0
                self._record_rate_limit(retry_after)
                self._save_tokens()
                raise SpotifyRateLimitError(retry_after) from exc
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise SpotifyApiError(f"Spotify API {exc.code}: {detail}") from exc

    @staticmethod
    def _download(url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "BongoDeskSpotify/3"})
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read(8 * 1024 * 1024)

    @staticmethod
    def _form_request(url: str, values: dict) -> dict:
        request = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(values).encode("ascii"),
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise SpotifyApiError(f"Spotify token error {exc.code}: {detail}") from exc

    def _load_tokens(self) -> dict:
        try:
            if self.token_path.exists():
                return json.loads(self.token_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _set_tokens(self, payload: dict) -> None:
        rate_limit_until = self._rate_limit_until()
        pacing_state = {
            key: value for key, value in self._tokens.items()
            if key.startswith("adaptive_")
        }
        tokens = dict(payload)
        tokens["expires_at"] = time.time() + int(tokens.get("expires_in", 3600))
        if rate_limit_until > time.time():
            tokens["rate_limit_until"] = rate_limit_until
        tokens.update(pacing_state)
        self._tokens = tokens
        self._save_tokens()

    def _configure_pacing_locked(self, settings: dict, reset_if_missing: bool) -> None:
        initial = float(settings.get("api_initial_interval_seconds", 3.0))
        minimum = float(settings.get("api_min_interval_seconds", 1.0))
        maximum = float(settings.get("api_max_interval_seconds", 30.0))
        idle = float(settings.get("api_idle_interval_seconds", 10.0))
        minimum = min(maximum, max(0.5, minimum))
        initial = min(maximum, max(minimum, initial))
        self._pacing_settings = {
            "initial_interval_seconds": initial,
            "minimum_interval_seconds": minimum,
            "maximum_interval_seconds": maximum,
            "idle_interval_seconds": max(initial, idle),
        }
        if reset_if_missing and not self._tokens.get("adaptive_interval_seconds"):
            self._tokens["adaptive_interval_seconds"] = initial
        current = float(self._tokens.get("adaptive_interval_seconds", initial))
        self._tokens["adaptive_interval_seconds"] = min(maximum, max(minimum, current))
        safe = float(self._tokens.get("adaptive_safe_interval_seconds", minimum))
        self._tokens["adaptive_safe_interval_seconds"] = min(maximum, max(minimum, safe))
        requested_reset_at = float(settings.get("api_reset_safety_requested_at", 0) or 0)
        completed_reset_at = float(self._tokens.get("adaptive_last_manual_reset_at", 0) or 0)
        if requested_reset_at > completed_reset_at:
            # This is an explicit user request to try the selected lower bound
            # again. A future 429 immediately restores adaptive protection.
            self._tokens["adaptive_interval_seconds"] = minimum
            self._tokens["adaptive_safe_interval_seconds"] = minimum
            self._tokens["adaptive_last_manual_reset_at"] = requested_reset_at
            self._tokens["adaptive_last_adjustment_at"] = time.time()
            self._tokens["adaptive_last_change"] = {
                "at": time.time(),
                "reason": "manual_reset",
                "from_seconds": current,
                "to_seconds": minimum,
            }

    def _current_interval(self) -> float:
        return float(self._tokens.get(
            "adaptive_interval_seconds", self._pacing_settings["initial_interval_seconds"]
        ))

    def _next_allowed_at(self) -> float:
        try:
            return float(self._tokens.get("adaptive_next_allowed_at", 0))
        except (TypeError, ValueError):
            return 0.0

    def _record_success(self) -> None:
        now = time.time()
        last_limit = float(self._tokens.get("adaptive_last_limit_at", 0) or 0)
        last_adjustment = float(self._tokens.get("adaptive_last_adjustment_at", 0) or 0)
        # After a clean rolling window, cautiously probe a little faster, but
        # never beyond the user's minimum interval or the learned safety margin.
        if now - last_limit >= 30 and now - last_adjustment >= 30:
            safe_interval = float(self._tokens.get(
                "adaptive_safe_interval_seconds",
                self._pacing_settings["minimum_interval_seconds"],
            ))
            current = self._current_interval()
            updated = max(safe_interval, current * 0.90)
            self._tokens["adaptive_interval_seconds"] = updated
            self._tokens["adaptive_last_adjustment_at"] = now
            if updated < current - 0.001:
                self._tokens["adaptive_last_change"] = {
                    "at": now,
                    "reason": "clean_window",
                    "from_seconds": current,
                    "to_seconds": updated,
                }
            self._save_tokens()

    def _record_rate_limit(self, retry_after: float) -> None:
        now = time.time()
        current = self._current_interval()
        # A 25% margin below the rate that hit 429 avoids repeatedly tapping
        # the edge once Spotify has told us where it is.
        safe_interval = min(
            self._pacing_settings["maximum_interval_seconds"],
            max(self._pacing_settings["minimum_interval_seconds"], current * 1.25),
        )
        updated = min(
            self._pacing_settings["maximum_interval_seconds"],
            max(current * 2.0, safe_interval),
        )
        self._tokens["adaptive_safe_interval_seconds"] = safe_interval
        self._tokens["adaptive_interval_seconds"] = updated
        self._tokens["adaptive_last_limit_at"] = now
        self._tokens["adaptive_last_adjustment_at"] = now
        self._tokens["adaptive_last_retry_after_seconds"] = max(1.0, retry_after)
        self._tokens["rate_limit_until"] = now + max(1.0, retry_after)
        events = self._tokens.get("adaptive_rate_limit_events", [])
        if not isinstance(events, list):
            events = []
        events.append(now)
        self._tokens["adaptive_rate_limit_events"] = [
            float(value) for value in events
            if isinstance(value, (int, float)) and value >= now - 24 * 60 * 60
        ][-200:]
        self._tokens["adaptive_last_change"] = {
            "at": now,
            "reason": "spotify_rate_limit",
            "from_seconds": current,
            "to_seconds": updated,
        }

    def _trim_request_times(self) -> None:
        cutoff = time.time() - 30.0
        while self._request_times and self._request_times[0] < cutoff:
            self._request_times.popleft()

    def _pacing_status(self) -> dict:
        self._trim_request_times()
        now = time.time()
        last_five_seconds = sum(1 for value in self._request_times if value >= now - 5.0)
        events = self._tokens.get("adaptive_rate_limit_events", [])
        if not isinstance(events, list):
            events = []
        events = [float(value) for value in events if isinstance(value, (int, float))]
        latest_change = self._tokens.get("adaptive_last_change")
        if not isinstance(latest_change, dict):
            latest_change = None
        return {
            "calls_last_30_seconds": len(self._request_times),
            "calls_per_second": last_five_seconds / 5.0,
            "interval_seconds": self._current_interval(),
            "safe_interval_seconds": float(self._tokens.get(
                "adaptive_safe_interval_seconds",
                self._pacing_settings["minimum_interval_seconds"],
            )),
            "next_allowed_at": self._next_allowed_at(),
            "total": int(self._tokens.get("adaptive_request_total", 0)),
            "rate_limits": {
                "last_15_minutes": sum(value >= now - 15 * 60 for value in events),
                "last_hour": sum(value >= now - 60 * 60 for value in events),
                "last_24_hours": sum(value >= now - 24 * 60 * 60 for value in events),
            },
            "last_change": latest_change,
            "adjusting_now": bool(
                latest_change and now - float(latest_change.get("at", 0) or 0) < 5.0
            ),
        }

    def _rate_limit_until(self) -> float:
        try:
            return float(self._tokens.get("rate_limit_until", 0))
        except (TypeError, ValueError):
            return 0.0

    def _save_tokens(self) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(json.dumps(self._tokens, indent=2), encoding="utf-8")
