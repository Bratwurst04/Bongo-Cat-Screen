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

from diagnostics import diagnostics
from api_budget import ApiBudget, BudgetWait, OperationGrant


ACCOUNTS_URL = "https://accounts.spotify.com"
API_URL = "https://api.spotify.com/v1"
REDIRECT_URI = "http://127.0.0.1:43821/callback"
SCOPES = "user-read-playback-state user-read-currently-playing user-modify-playback-state"
API_USAGE_WINDOW_SECONDS = 15 * 60
QUOTA_RECOVERY_SECONDS = 24 * 60 * 60
QUOTA_POLL_FLOOR_SECONDS = 60.0
API_REQUEST_KINDS = ("playback_poll", "playback_urgent", "artwork_fallback", "control")


class SpotifyApiError(RuntimeError):
    pass


class SpotifyRateLimitError(SpotifyApiError):
    def __init__(self, retry_after_seconds: float, reason: str = "unspecified_429",
                 request_kind: str = "other", cached: bool = False):
        self.retry_after_seconds = max(1.0, retry_after_seconds)
        self.reason = reason
        self.request_kind = request_kind
        self.cached = cached
        super().__init__(f"Spotify rate limit; retry after {self.retry_after_seconds:.0f}s")


class SpotifyPacingError(SpotifyApiError):
    """Raised locally before an HTTP request would exceed our learned pace."""

    def __init__(self, wait_seconds: float):
        self.wait_seconds = max(0.05, wait_seconds)
        super().__init__(f"Spotify request paced; retry after {self.wait_seconds:.2f}s")


class SpotifyBudgetError(SpotifyPacingError):
    def __init__(self, wait_seconds: float, reason: str):
        super().__init__(wait_seconds)
        self.reason = reason


class SpotifyApiBridge:
    def __init__(self, client_id: str, token_path: Path, pacing_settings: Optional[dict] = None, *, budget=None):
        self.client_id = (client_id or "").strip()
        self.token_path = Path(token_path)
        self._tokens = self._load_tokens()
        self._budget = budget if budget is not None else ApiBudget(
            self.token_path.with_name("spotify_api_budget.json"), pacing_settings or {})
        self._budget_log_after = 0.0
        self._last_art_key = ""
        self._primary_available_revision = 0
        self._last_is_playing = False
        self.last_control_http_status = None
        self._lock = threading.Lock()
        self._request_times = deque()
        self._request_times_15m = deque()
        self._session_started_at = time.time()
        self._api_usage_started_at = time.time()
        self._api_usage_counts = {kind: 0 for kind in (*API_REQUEST_KINDS, "other")}
        self._pacing_settings = {}
        self._configure_pacing_locked(pacing_settings or {}, reset_if_missing=True)
        self._initialize_429_total()
        try:
            quota_retry = max(0, float(self._tokens.get("adaptive_quota_recovery_until", 0) or 0) - QUOTA_RECOVERY_SECONDS)
            self._budget.import_legacy_limits(self._rate_limit_until(), quota_retry,
                self._tokens.get("adaptive_last_limit_reason") == "quota_exceeded")
        except BudgetWait:
            pass  # Status/admission remains fail-closed; never erase the file.
        if self.token_path.exists():
            self._save_tokens()
        if self._tokens.get("refresh_token"):
            diagnostics.event(
                "SPOTIFY_API_429_TOTAL",
                total_429=int(self._tokens["adaptive_total_429"]),
                total_since=int(self._tokens["adaptive_total_429_since"]),
                legacy_events_included=int(self._tokens["adaptive_total_429_legacy_events"]),
            )

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
        local = self._budget.view(idle=not self._last_is_playing)
        remaining = max(0, math.ceil(retry_until - time.time()),
                        math.ceil(local.get("retry_remaining_seconds", 0)))
        pacing = self._pacing_status()
        if remaining:
            return {
                "state": "rate_limited",
                "retry_until": max(retry_until, time.time()+local.get("retry_remaining_seconds",0)),
                "retry_remaining_seconds": remaining,
                "limit_reason": "quota_exceeded" if local.get("retry_reason") == 2 else
                    self._tokens.get("adaptive_last_limit_reason", "unspecified_429"),
                "limit_request_kind": self._tokens.get("adaptive_last_limit_request_kind", "other"),
                "pacing": pacing,
                "local_budget": local,
            }
        local_block = local.get("wait_reason") not in ("none", "profile", "start_spacing")
        return {"state": "locally_limited" if local_block else "ready", "pacing": pacing,
                "local_budget": local}

    def configure_pacing(self, pacing_settings: dict) -> None:
        """Apply local limits. This makes no Spotify request."""
        with self._lock:
            self._budget.configure(pacing_settings)
            self._configure_pacing_locked(pacing_settings or {}, reset_if_missing=False)
            self._save_tokens()

    def poll_delay_seconds(self, idle: bool = False) -> float:
        """The next safe metadata poll delay, determined entirely locally."""
        with self._lock:
            now = time.time()
            poll_floor = max(
                self._quota_poll_floor(idle=idle),
                float(self._pacing_settings["idle_interval_seconds"]) if idle else 0.0,
            )
            due = max(now, self._next_allowed_at(), self._rate_limit_until(),
                      float(self._tokens.get("adaptive_last_request_at", 0)) + poll_floor)
            local = self._budget.view(idle=idle)
            return max(0.05, due - now, local["wait_seconds"])

    def poll_interval_seconds(self, idle: bool = False) -> float:
        """Base automatic interval, including persisted safety and quota recovery."""
        with self._lock:
            return max(
                self._current_interval(),
                float(self._tokens.get("adaptive_safe_interval_seconds", 0) or 0),
                float(self._pacing_settings["idle_interval_seconds"]) if idle else 0.0,
                self._quota_poll_floor(idle=idle),
                self._budget.view(idle=idle)["interval_seconds"],
            )

    def notify_local_activity(self) -> None:
        self._budget.notify_activity()

    def begin_operation(self, kind: str) -> OperationGrant:
        try:
            return self._budget.begin_operation(kind)
        except BudgetWait as exc:
            self._log_budget_wait(exc)
            if exc.reason == "server_retry":
                local = self._budget.view()
                raise SpotifyRateLimitError(exc.wait_seconds,
                    "quota_exceeded" if local.get("retry_reason") == 2 else
                    self._tokens.get("adaptive_last_limit_reason", "unspecified_429"), cached=True) from None
            raise SpotifyBudgetError(exc.wait_seconds, exc.reason) from None

    def _log_budget_wait(self, exc):
        now = time.monotonic()
        if now < self._budget_log_after:
            return
        self._budget_log_after = now + 60
        view = self._budget.view(idle=not self._last_is_playing)
        diagnostics.event("SPOTIFY_API_LOCAL_WAIT", reason=exc.reason,
            profile=view.get("profile", "guarded"), wait_seconds=int(math.ceil(exc.wait_seconds)),
            calls_30s=view.get("short_used",0), local_calls_24h=view.get("long_used",0),
            interval_ms=int(view.get("interval_seconds",60)*1000))

    def finish_operation(self, operation) -> None:
        try:
            self._budget.finish_operation(operation)
        except BudgetWait:
            pass  # An unused claim remains bounded by its ten-second expiry.

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

    @property
    def primary_playback_revision(self) -> int:
        """Content-free serial for available A responses, including background art reads."""
        return self._primary_available_revision

    def get_playback(self, urgent: bool = False,
                     artwork_fallback: bool = False, operation=None,
                     start_guard=None, retry_guard=None) -> Tuple[Optional[dict], Optional[str]]:
        """Return playback metadata immediately and an optional artwork URL.

        Artwork is downloaded by the media bridge after metadata has already
        been published.  This keeps a slow cover request from making the
        display look as if nothing is playing.
        """
        if not self.is_ready:
            return None, None
        urgent = urgent or operation is not None
        endpoint = "/me/player?additional_types=track%2Cepisode"
        def guarded_endpoint():
            if not start_guard():
                raise SpotifyBudgetError(0.05, "operation_expired")
            return endpoint
        data = self._api_request(
            "GET", guarded_endpoint if start_guard is not None else endpoint, urgent=urgent,
            request_kind=("artwork_fallback" if artwork_fallback else
                          "playback_urgent" if urgent else "playback_poll"),
            operation=None if artwork_fallback else operation,
            **({"retry_guard": retry_guard} if retry_guard is not None else {}),
        )
        if not data or not data.get("item"):
            self._last_is_playing = False
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

    def diagnose_devices(self, start_guard) -> bool:
        """Use one automatic slot, with no HTTP retry or playback-state mutation."""
        def endpoint_at_start():
            if not start_guard():
                raise SpotifyBudgetError(0.05, "operation_expired")
            return "/me/player/devices"
        try:
            if not self.is_ready:
                raise SpotifyApiError("Spotify unavailable")
            data = self._api_request("GET", endpoint_at_start, request_kind="playback_poll",
                                     retry_guard=lambda: False)
            return self._devices_summary(data) is not None
        except SpotifyPacingError:
            raise
        except Exception as exc:
            # HTTP status is already logged; shared 429/ledger guards remain active.
            # A diagnostic error must not clear or republish the primary snapshot.
            diagnostics.event("SPOTIFY_DEVICES_DIAGNOSTIC", source="spotify_api",
                              endpoint="available_devices", result="failure",
                              error_type=type(exc))
            return False

    @staticmethod
    def _devices_summary(data):
        if type(data) is not dict or type(data.get("devices")) is not list:
            return None
        counts = dict(devices_total=0, devices_active=0, devices_smartphones=0,
                      devices_active_smartphones=0, devices_private=0, devices_restricted=0)
        for device in data["devices"]:
            if (type(device) is not dict or type(device.get("type")) is not str or
                    any(type(device.get(key)) is not bool
                        for key in ("is_active", "is_private_session", "is_restricted"))):
                return None
            active = device["is_active"]
            smartphone = device["type"].casefold() == "smartphone"
            counts["devices_total"] += 1
            counts["devices_active"] += int(active)
            counts["devices_smartphones"] += int(smartphone)
            counts["devices_active_smartphones"] += int(active and smartphone)
            counts["devices_private"] += int(device["is_private_session"])
            counts["devices_restricted"] += int(device["is_restricted"])
        return counts



    def control(self, action: str, operation=None):
        if not self.is_ready:
            return
        action = action.upper()
        if action not in ("PLAY_PAUSE", "NEXT", "PREVIOUS"):
            return None
        created = operation is None
        operation = operation or self.begin_operation("control")
        try:
            if action == "PLAY_PAUSE":
                endpoint = "/me/player/pause" if self._last_is_playing else "/me/player/play"
                self._api_request("PUT", endpoint, empty_ok=True, urgent=True, operation=operation)
                self._last_is_playing = not self._last_is_playing
            else:
                endpoint = "/me/player/next" if action == "NEXT" else "/me/player/previous"
                self._api_request("POST", endpoint, empty_ok=True, urgent=True, operation=operation)
        except Exception:
            if created:
                self.finish_operation(operation)
            raise
        return operation

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
        self, method: str, endpoint: str, empty_ok: bool = False, urgent: bool = False,
        request_kind: str = "control", operation=None, retry_guard=None,
    ):
        with self._lock:
            if request_kind == "control":
                self.last_control_http_status = None
            return self._api_request_locked(method, endpoint, empty_ok, retry=True,
                                            urgent=urgent, request_kind=request_kind, operation=operation,
                                            retry_guard=retry_guard)

    def _api_request_locked(
        self, method: str, endpoint: str, empty_ok: bool, retry: bool, urgent: bool = False,
        request_kind: str = "control", operation=None, retry_guard=None,
    ):
        playback_read = method == "GET" and request_kind in (
            "playback_poll", "playback_urgent", "artwork_fallback")
        now = time.time()
        local = self._budget.view(idle=not self._last_is_playing)
        retry_remaining = max(0, math.ceil(self._rate_limit_until() - now),
                              math.ceil(local.get("retry_remaining_seconds", 0)))
        if retry_remaining:
            # Spotify's Retry-After is authoritative.  Persisting this means a
            # restart cannot turn into a burst of retries while it is active.
            raise SpotifyRateLimitError(
                retry_remaining,
                reason="quota_exceeded" if local.get("retry_reason") == 2 else
                    self._tokens.get("adaptive_last_limit_reason", "unspecified_429"),
                request_kind=self._tokens.get("adaptive_last_limit_request_kind", "other"),
                cached=True,
            )
        # Polling, controls and confirmation reads share one start-time gate.
        # Urgent identifies explicit user work; it never bypasses this gate.
        next_allowed_at = self._next_allowed_at()
        if not urgent:
            next_allowed_at = max(
                next_allowed_at,
                float(self._tokens.get("adaptive_last_request_at", 0)) + self._quota_poll_floor(),
            )
        if next_allowed_at > now:
            raise SpotifyPacingError(next_allowed_at - now)
        # OAuth may be slow. Prepare it before the final shared network guard,
        # then recheck pacing/grant/Retry-After after durable I/O as well.
        token = self._access_token()

        resolved_endpoint=None
        def endpoint_label():
            return "available_devices" if resolved_endpoint == "/me/player/devices" else "playback_state"
        def http_event():
            return "SPOTIFY_DEVICES_HTTP" if endpoint_label() == "available_devices" else "SPOTIFY_PLAYBACK_HTTP"
        def start_check():
            nonlocal resolved_endpoint
            actual_now=time.time()
            remaining=max(0,math.ceil(self._rate_limit_until()-actual_now))
            if remaining:raise SpotifyRateLimitError(remaining,cached=True)
            due=self._next_allowed_at()
            if not urgent:due=max(due,float(self._tokens.get('adaptive_last_request_at',0))+self._quota_poll_floor())
            if due>actual_now:raise SpotifyPacingError(due-actual_now)
            resolved_endpoint=endpoint() if callable(endpoint) else endpoint

        def invoke():
            request=urllib.request.Request(f'{API_URL}{resolved_endpoint}',
                data=b'' if method in ('POST','PUT') else None,method=method,
                headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'})
            actual_now=time.time()
            self._request_times.append(actual_now);self._request_times_15m.append(actual_now)
            self._record_api_request(request_kind,actual_now)
            self._tokens['adaptive_last_request_at']=actual_now
            self._tokens['adaptive_next_allowed_at']=actual_now+self._current_interval()
            self._tokens['adaptive_request_total']=int(self._tokens.get('adaptive_request_total',0))+1
            try:
                with urllib.request.urlopen(request,timeout=8) as response:
                    if playback_read:
                        status = getattr(response, "status", None)
                        diagnostics.event(http_event(), source="spotify_api",
                                          request_kind=request_kind, result="success",
                                          endpoint=endpoint_label(),
                                          http_status=status if type(status) is int else None)
                    if request_kind == "control":
                        status = getattr(response, "status", None)
                        self.last_control_http_status = status if type(status) is int else None
                    # Control endpoints acknowledge success without JSON.
                    # A body (even whitespace/non-JSON) is not a playback
                    # snapshot and must not turn an accepted action into a
                    # retry or discard its reserved confirmation.
                    if empty_ok:
                        return None
                    return response.read()
            except urllib.error.HTTPError as error:
                if playback_read:
                    diagnostics.event(http_event(), source="spotify_api",
                                      request_kind=request_kind, result="failure",
                                      endpoint=endpoint_label(),
                                      http_status=error.code)
                if request_kind == "control":
                    self.last_control_http_status = error.code
                if error.code==429:
                    try:seconds=float(error.headers.get('Retry-After','60'))
                    except (AttributeError,TypeError,ValueError):seconds=60.0
                    seconds=max(1.0,seconds) if math.isfinite(seconds) else 60.0
                    error._budget_retry_after=seconds
                    error._budget_reason=self._classify_429(error.read(4096))
                    error._budget_quota=error._budget_reason=='quota_exceeded'
                raise
        try:
            payload=self._budget.http_attempt(invoke,idle=not self._last_is_playing,
                                              operation=operation,start_check=start_check)
            try:
                self._record_success()
            except OSError as exc:
                if not empty_ok:
                    raise
                # A failed save of clean-window pacing metadata cannot undo
                # an acknowledged control. Durable budget/Retry guards remain.
                diagnostics.event("SPOTIFY_API_STATE", result="failure", reason="history_io",
                                  error_type=type(exc), http_status=self.last_control_http_status)
            try:
                data = json.loads(payload.decode('utf-8')) if payload else None
            except RecursionError:
                if playback_read and endpoint_label() == "available_devices":
                    diagnostics.event("SPOTIFY_DEVICES_BODY", source="spotify_api",
                                      endpoint="available_devices", devices_body="invalid")
                raise
            except (json.JSONDecodeError, UnicodeDecodeError):
                if playback_read and endpoint_label() == "available_devices":
                    diagnostics.event("SPOTIFY_DEVICES_BODY", source="spotify_api",
                                      endpoint="available_devices", devices_body="invalid")
                elif playback_read:
                    diagnostics.event("SPOTIFY_PLAYBACK_SHAPE", source="spotify_api",
                                      request_kind=request_kind, outcome="invalid",
                                      endpoint=endpoint_label(),
                                      body_shape="invalid")
                raise
            if playback_read and endpoint_label() == "available_devices":
                counts = self._devices_summary(data)
                diagnostics.event("SPOTIFY_DEVICES_BODY", source="spotify_api",
                                  endpoint="available_devices",
                                  devices_body="valid" if counts is not None else "invalid",
                                  **(counts or {}))
            elif playback_read:
                # Fixed enums only: never pass through response text, IDs or metadata.
                shape = "empty" if data is None else "object" if isinstance(data, dict) else "other"
                item = data.get("item") if isinstance(data, dict) else None
                item_state = ("missing" if not isinstance(data, dict) or "item" not in data else
                              "null" if item is None else
                              "present" if isinstance(item, dict) else "other")
                kind = data.get("currently_playing_type") if isinstance(data, dict) else None
                if kind is None and isinstance(item, dict):
                    kind = item.get("type")
                playback_type = ("missing" if kind is None else kind
                                 if kind in ("track", "episode", "ad", "unknown") else "unknown")
                outcome = ("empty" if not data or isinstance(data, dict) and not item else
                           "available" if isinstance(item, dict) else "invalid")
                if endpoint_label() == "playback_state" and outcome == "available":
                    # Still inside the existing client lock: a late Windows
                    # artwork response can invalidate a pending B as well.
                    self._primary_available_revision += 1
                diagnostics.event("SPOTIFY_PLAYBACK_SHAPE", source="spotify_api",
                                  request_kind=request_kind, outcome=outcome, body_shape=shape,
                                  endpoint=endpoint_label(),
                                  item_state=item_state, playback_type=playback_type)
            return data
        except BudgetWait as exc:
            self._log_budget_wait(exc)
            raise SpotifyBudgetError(exc.wait_seconds,exc.reason) from None
        except urllib.error.HTTPError as exc:
            if exc.code == 401 and retry and (retry_guard is None or retry_guard()):
                self._refresh()
                return self._api_request_locked(
                    method, endpoint, empty_ok, retry=False, urgent=urgent,
                    request_kind=request_kind,
                    operation=operation,
                    retry_guard=retry_guard,
                )
            if exc.code == 204 and empty_ok:
                return None
            if exc.code == 429:
                try:
                    retry_after = float(exc.headers.get("Retry-After", "60"))
                except (AttributeError, TypeError, ValueError):
                    retry_after = 60.0
                if not math.isfinite(retry_after):
                    retry_after = 60.0
                retry_after = max(1.0, retry_after)
                reason = getattr(exc,'_budget_reason',self._classify_429(b''))
                interval_before = self._current_interval()
                self._record_rate_limit(retry_after, reason, request_kind)
                try:
                    self._save_tokens()
                except OSError:
                    pass  # Keep the known server deadline in memory/ledger.
                self._trim_request_times()
                diagnostics.event(
                    "SPOTIFY_API_429", reason=reason, request_kind=request_kind,
                    wait_seconds=int(retry_after), calls_30s=len(self._request_times),
                    window_seconds=int(max(0, now - self._api_usage_started_at)),
                    interval_ms=int(round(interval_before * 1000)),
                    next_interval_ms=int(round(self._current_interval() * 1000)),
                    request_total=int(self._tokens.get("adaptive_request_total", 0)),
                    total_429=int(self._tokens["adaptive_total_429"]),
                    **self._api_usage_counts,
                )
                raise SpotifyRateLimitError(retry_after, reason, request_kind) from exc
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise SpotifyApiError(f"Spotify API {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise SpotifyApiError("Spotify API connection failed") from exc

    @staticmethod
    def _classify_429(body: bytes) -> str:
        """Whitelist Spotify's structured reason; never retain the response body."""
        try:
            payload = json.loads(body.decode("utf-8"))
            reason = payload.get("error", {}).get("reason")
        except (AttributeError, UnicodeError, ValueError, TypeError):
            return "unspecified_429"
        if reason == "QUOTA_EXCEEDED":
            return "quota_exceeded"
        if reason in ("RATE_LIMIT_EXCEEDED", "RATE_LIMITED"):
            return "rate_limited"
        return "unspecified_429"

    def _record_api_request(self, request_kind: str, now: float) -> None:
        if now - self._api_usage_started_at >= API_USAGE_WINDOW_SECONDS:
            diagnostics.event(
                "SPOTIFY_API_USAGE", window_seconds=int(now - self._api_usage_started_at),
                interval_ms=int(round(self._current_interval() * 1000)),
                request_total=int(self._tokens.get("adaptive_request_total", 0)),
                total_429=int(self._tokens["adaptive_total_429"]),
                **self._api_usage_counts,
            )
            self._api_usage_started_at = now
            self._api_usage_counts = {kind: 0 for kind in (*API_REQUEST_KINDS, "other")}
        kind = request_kind if request_kind in API_REQUEST_KINDS else "other"
        self._api_usage_counts[kind] += 1

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
        initial = float(settings.get("api_initial_interval_seconds", 1.0))
        minimum = float(settings.get("api_min_interval_seconds", 0.5))
        maximum = float(settings.get("api_max_interval_seconds", 30.0))
        idle = float(settings.get("api_idle_interval_seconds", 3.0))
        minimum = min(maximum, max(0.5, minimum))
        initial = min(maximum, max(minimum, initial))
        self._pacing_settings = {
            "initial_interval_seconds": initial,
            "minimum_interval_seconds": minimum,
            "maximum_interval_seconds": maximum,
            "idle_interval_seconds": max(initial, idle),
        }
        if reset_if_missing and not self._tokens.get("adaptive_interval_seconds"):
            self._tokens["adaptive_interval_seconds"] = minimum
        # A legacy start interval is not learned backoff. Start at the chosen
        # minimum when no rate limit has been recorded; retain actual history.
        if (not self._tokens.get("adaptive_last_limit_at")
                and self._rate_limit_until() <= time.time()
                and not self._quota_poll_floor()):
            self._tokens["adaptive_interval_seconds"] = minimum
            self._tokens["adaptive_safe_interval_seconds"] = minimum
        current = float(self._tokens.get("adaptive_interval_seconds", initial))
        self._tokens["adaptive_interval_seconds"] = min(maximum, max(minimum, current))
        safe = float(self._tokens.get("adaptive_safe_interval_seconds", minimum))
        self._tokens["adaptive_safe_interval_seconds"] = min(maximum, max(minimum, safe))
        self._tokens["adaptive_interval_seconds"] = max(
            self._tokens["adaptive_interval_seconds"],
            self._tokens["adaptive_safe_interval_seconds"],
        )
        self._tokens["adaptive_next_allowed_at"] = max(
            self._next_allowed_at(),
            float(self._tokens.get("adaptive_last_request_at", 0)) + self._current_interval(),
        )
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
        if not self._tokens.get("adaptive_clean_window_started_at"):
            self._tokens["adaptive_clean_window_started_at"] = now
        clean_start = float(self._tokens["adaptive_clean_window_started_at"])
        # Cooldown time is not a clean request window. After successful traffic
        # for a full window, decay both backoff and its learned margin so a 429
        # does not create a permanent floor above the configured minimum.
        clean_seconds = 6*3600 if self._tokens.get("adaptive_last_limit_reason") == "quota_exceeded" else 600
        if (now - max(last_limit, self._rate_limit_until(), clean_start) >= clean_seconds
                and now - last_adjustment >= clean_seconds
                and now >= float(self._tokens.get("adaptive_quota_recovery_until", 0) or 0)):
            safe_interval = float(self._tokens.get(
                "adaptive_safe_interval_seconds",
                self._pacing_settings["minimum_interval_seconds"],
            ))
            current = self._current_interval()
            minimum = self._pacing_settings["minimum_interval_seconds"]
            updated = max(minimum, current * 0.90)
            self._tokens["adaptive_safe_interval_seconds"] = max(minimum, safe_interval * 0.90)
            self._tokens["adaptive_interval_seconds"] = updated
            self._tokens["adaptive_next_allowed_at"] = (
                float(self._tokens.get("adaptive_last_request_at", 0)) + updated
            )
            self._tokens["adaptive_last_adjustment_at"] = now
            if updated < current - 0.001:
                self._tokens["adaptive_last_change"] = {
                    "at": now,
                    "reason": "clean_window",
                    "from_seconds": current,
                    "to_seconds": updated,
                }
            self._save_tokens()

    def _record_rate_limit(self, retry_after: float, reason: str = "unspecified_429",
                           request_kind: str = "other") -> None:
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
            max(current * 2.0, safe_interval, self._pacing_settings["initial_interval_seconds"]),
        )
        self._tokens["adaptive_safe_interval_seconds"] = safe_interval
        self._tokens["adaptive_interval_seconds"] = updated
        self._tokens["adaptive_last_limit_at"] = now
        self._tokens["adaptive_last_adjustment_at"] = now
        self._tokens["adaptive_clean_window_started_at"] = 0
        self._tokens["adaptive_last_retry_after_seconds"] = max(1.0, retry_after)
        self._tokens["adaptive_last_limit_reason"] = reason
        self._tokens["adaptive_last_limit_request_kind"] = request_kind
        self._tokens["rate_limit_until"] = now + max(1.0, retry_after)
        if reason == "quota_exceeded":
            # A development-mode quota is distinct from a rolling rate limit.
            # Keep a conservative automatic poll floor after Retry-After ends.
            self._tokens["adaptive_quota_recovery_until"] = (
                self._tokens["rate_limit_until"] + QUOTA_RECOVERY_SECONDS
            )
        self._tokens["adaptive_total_429"] = int(
            self._tokens.get("adaptive_total_429", 0)
        ) + 1
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
        try:
            self._budget.note_retry(retry_after, reason == "quota_exceeded")
        except BudgetWait:
            pass  # The token deadline still wins and the ledger stays guarded.

    def _trim_request_times(self) -> None:
        now = time.time()
        while self._request_times and self._request_times[0] < now - 30.0:
            self._request_times.popleft()
        while self._request_times_15m and self._request_times_15m[0] < now - 900.0:
            self._request_times_15m.popleft()

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
            "calls_last_15_minutes": len(self._request_times_15m),
            "observed_seconds": min(900, max(0, int(now - self._session_started_at))),
            "calls_per_second": last_five_seconds / 5.0,
            "interval_seconds": self._current_interval(),
            "minimum_interval_seconds": self._pacing_settings["minimum_interval_seconds"],
            "safe_interval_seconds": float(self._tokens.get(
                "adaptive_safe_interval_seconds",
                self._pacing_settings["minimum_interval_seconds"],
            )),
            "next_allowed_at": self._next_allowed_at(),
            "total": int(self._tokens.get("adaptive_request_total", 0)),
            "rate_limits": {
                "total": int(self._tokens.get("adaptive_total_429", 0)),
                "total_since": float(self._tokens.get("adaptive_total_429_since", 0) or 0),
                "legacy_events_included": int(self._tokens.get("adaptive_total_429_legacy_events", 0)),
                "last_15_minutes": sum(value >= now - 15 * 60 for value in events),
                "last_hour": sum(value >= now - 60 * 60 for value in events),
                "last_24_hours": sum(value >= now - 24 * 60 * 60 for value in events),
            },
            "last_change": latest_change,
            "quota_recovery_until": float(self._tokens.get("adaptive_quota_recovery_until", 0) or 0),
            "quota_poll_floor_seconds": self._quota_poll_floor(),
            "adjusting_now": bool(
                latest_change and now - float(latest_change.get("at", 0) or 0) < 5.0
            ),
        }

    def _quota_poll_floor(self, idle: bool = False) -> float:
        if time.time() >= float(self._tokens.get("adaptive_quota_recovery_until", 0) or 0):
            return 0.0
        if (self._last_is_playing and not idle and
                self._budget.view(idle=False).get("profile") == "day"):
            return 0.0
        return QUOTA_POLL_FLOOR_SECONDS

    def _initialize_429_total(self) -> None:
        if "adaptive_total_429" in self._tokens:
            try:
                self._tokens["adaptive_total_429"] = max(0, int(self._tokens["adaptive_total_429"]))
            except (TypeError, ValueError):
                self._tokens["adaptive_total_429"] = 0
            self._tokens.setdefault("adaptive_total_429_legacy_events", 0)
            self._tokens.setdefault("adaptive_total_429_since", time.time())
            return
        # The legacy list held at most 200 events. It was trimmed to a 24-hour
        # range only when a NEW 429 arrived, so old retained entries still
        # prove real responses and belong in the migrated lower bound.
        now = time.time()
        events = self._tokens.get("adaptive_rate_limit_events", [])
        known = [value for value in events if isinstance(value, (int, float))
                 and 0 < value <= now] if isinstance(events, list) else []
        legacy_total = len(known)
        if not legacy_total and isinstance(self._tokens.get("adaptive_last_limit_at"), (int, float)):
            if 0 < self._tokens["adaptive_last_limit_at"] <= now:
                legacy_total = 1
        self._tokens["adaptive_total_429"] = legacy_total
        self._tokens["adaptive_total_429_legacy_events"] = legacy_total
        self._tokens["adaptive_total_429_since"] = now

    def _rate_limit_until(self) -> float:
        try:
            return float(self._tokens.get("rate_limit_until", 0))
        except (TypeError, ValueError):
            return 0.0

    def _save_tokens(self) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.token_path.with_name(self.token_path.name + ".tmp")
        temporary.write_text(json.dumps(self._tokens, indent=2), encoding="utf-8")
        temporary.replace(self.token_path)
