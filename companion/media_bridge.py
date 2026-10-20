"""Windows media-session bridge for BongoDesk.

Reads Spotify (or another active Windows media session) through GSMTC.  This
keeps account credentials off the ESP32 and also lets touch commands use the
same controls as the Windows media overlay.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import io
import queue
import threading
import time
from dataclasses import dataclass, replace
from typing import Callable, Optional
from diagnostics import diagnostics
from media_commands import MEDIA_ACTIONS, MediaControlRequest, MediaRefreshRequest

from PIL import Image, ImageDraw, ImageOps
from artwork_crop import spotify_smtc_album_box
from spotify_api import (
    SpotifyApiBridge,
    SpotifyApiError,
    SpotifyPacingError,
    SpotifyBudgetError,
    SpotifyRateLimitError,
)
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
)
from winrt.windows.storage.streams import DataReader


ART_SIZE = 112
POLL_INTERVAL_SECONDS = 0.45
SPOTIFY_COMMAND_CHECK_SECONDS = 0.05
DEFAULT_ARTWORK_RETRY_ATTEMPTS = 5
ARTWORK_EXHAUSTED_COOLDOWN_SECONDS = 90.0
WINDOWS_API_ART_FALLBACK_SECONDS = 60.0
MANUAL_REFRESH_TTL_SECONDS = 3.0
MANUAL_REFRESH_COOLDOWN_SECONDS = 5.0
MANUAL_REFRESH_GESTURE_QUIET_SECONDS = 0.5  # F406 groups taps for 320 ms.
DEVICES_DIAGNOSTIC_TTL_SECONDS = 90.0


@dataclass(frozen=True)
class MediaSnapshot:
    available: bool = False
    source: str = "WINDOWS"
    title: str = "Nothing playing"
    artist: str = "Start Spotify on this PC"
    playing: bool = False
    position_seconds: int = 0
    duration_seconds: int = 0
    track_key: str = ""


class WindowsMediaBridge:
    def __init__(
        self,
        on_update: Callable[[MediaSnapshot, Optional[bytes]], None],
        on_error: Optional[Callable[[str], None]] = None,
        spotify_client_id: str = "",
        spotify_token_path=None,
        spotify_settings: Optional[dict] = None,
    ):
        self._on_update = on_update
        self._on_error = on_error or (lambda message: None)
        self._commands: queue.Queue = queue.Queue()
        self._pending_spotify_command = None
        self._control_lock = threading.Lock()
        self._control_requests = {}
        self._confirmation_operation = None
        self._pending_control_operation = None
        self._next_api_poll_at = 0.0
        self._activity_pending = False
        self._activity_can_wake = False
        self._last_api_snapshot_at = 0.0
        self._source_mode = ""
        self._source_epoch = 0
        self._api_snapshot_epoch = -1
        self._api_waiting = False
        self._manual_refresh = None
        self._manual_next_at = 0.0
        self._manual_quiet_until = 0.0
        self._devices_probe_used = False
        self._devices_probe_deadline = 0.0
        self._devices_probe_epoch = -1
        self._devices_probe_attempts = 0
        self._devices_probe_primary_revision = 0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_snapshot: Optional[MediaSnapshot] = None
        self._last_reported_source = ""
        self._last_reported_track = ""
        self._track_seq = 0
        self._last_refresh_error_at = 0.0
        self._windows_api_fallback_next_at = 0.0
        self._api_fallback_complete_windows_key = ""
        self._windows_api_fallback_task = None
        self._last_track_key = ""
        self._spotify_retry_at = 0.0
        self._spotify_retry_is_rate_limit = False
        self._spotify_retry_message = ""
        self._windows_spotify_available = False
        self._other_windows_media_available = False
        self._current_source = "generic"
        self._api_only_idle = False
        self._spotify_settings = dict(spotify_settings or {})
        self._artwork_retry_attempts = self._artwork_attempt_limit()
        self._windows_artwork_key = ""
        self._windows_artwork_attempts = 0
        self._windows_artwork_next_retry = 0.0
        self._windows_artwork_complete_key = ""
        self._windows_artwork_missing_reported = False
        self._api_artwork_key = ""
        self._api_artwork_attempts = 0
        self._api_artwork_next_retry = 0.0
        self._api_artwork_complete_key = ""
        self._api_artwork_missing_reported = False
        self._spotify = None
        self._spotify_load_error = False
        if spotify_client_id and spotify_token_path:
            try:
                self._spotify = SpotifyApiBridge(
                    spotify_client_id, spotify_token_path, self._spotify_settings
                )
            except SpotifyApiError:
                # Keep tray, settings and local media available, while leaving
                # unreadable credentials untouched for deliberate recovery.
                self._on_error("Spotify token file could not be loaded; retained unchanged")
                self._spotify_load_error = True

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._thread_main,
            name="BongoDeskMedia",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def control(self, action: str) -> bool:
        action = action.upper()
        if action not in MEDIA_ACTIONS:
            return False
        # The input slot never holds API/file locks; log only after releasing it.
        refresh_phase = None
        with self._control_lock:
            received_epoch = self._source_epoch
            if self._manual_refresh is not None:
                refresh_phase, accepted = "coalesced", True
            elif time.monotonic() < self._manual_quiet_until:
                refresh_phase, accepted = "suppressed", False
            elif self._api_waiting and self._source_mode == "spotify_api":
                if action != "PLAY_PAUSE" or time.monotonic() < self._manual_next_at:
                    refresh_phase, accepted = "suppressed", False
                else:
                    self._manual_refresh = MediaRefreshRequest(
                        self._source_epoch, time.monotonic() + MANUAL_REFRESH_TTL_SECONDS)
                    self._manual_next_at = time.monotonic() + MANUAL_REFRESH_COOLDOWN_SECONDS
                    refresh_phase, accepted = "accepted", True
        if refresh_phase is not None:
            diagnostics.event("MEDIA_REFRESH", source="spotify_api", read_origin="manual",
                              phase=refresh_phase, action=action)
            return accepted
        self.notify_local_activity()
        with self._control_lock:
            if received_epoch != self._source_epoch:
                return False
            if len(self._control_requests) >= 8:
                diagnostics.event("MEDIA_CONTROL", action=action, result="skipped", reason="queue_full")
                return False
            command = MediaControlRequest(action,
                self._current_source if self._current_source in ("windows_spotify", "spotify_api") else None,
                time.monotonic() + 5, source_epoch=self._source_epoch if
                self._source_mode == "spotify_api" else None)
            self._control_requests[id(command)] = command
            self._commands.put(command)
        return True

    def notify_local_activity(self):
        self._activity_pending = True
        if self._spotify:
            self._spotify.notify_local_activity()



    def _finish_control(self, command, accepted=False, reason="", error_type=None, http_status=None):
        if isinstance(command, MediaControlRequest):
            with self._control_lock:
                self._control_requests.pop(id(command), None)
            if not accepted and command.operation is not None:
                self._spotify.finish_operation(command.operation)
            if not accepted:
                diagnostics.event("MEDIA_CONTROL", action=command.action, result="skipped",
                                  **({"reason":reason} if reason else {}),
                                  error_type=error_type, http_status=http_status)

    def _finish_manual_refresh(self, request, phase="cancelled", outcome=None):
        if request is None:
            return
        owned = False
        with self._control_lock:
            if self._manual_refresh is request:
                owned = True
                self._manual_refresh = None
                self._manual_quiet_until = time.monotonic() + MANUAL_REFRESH_GESTURE_QUIET_SECONDS
        if request.operation is not None:
            self._spotify.finish_operation(request.operation)
            request.operation = None
        if owned:
            diagnostics.event("MEDIA_REFRESH", source="spotify_api", read_origin="manual",
                              phase=phase, outcome=outcome, attempt=request.attempts)

    def _manual_refresh_valid(self, request, check_ttl=True):
        return bool(request is not None and self._manual_refresh is request and
                    request.source_epoch == self._source_epoch and self._source_mode == "spotify_api" and
                    self._api_waiting and (not check_ttl or time.monotonic() < request.expires_at))

    def _finish_devices_probe(self, phase="cancelled", reason=None):
        if not self._devices_probe_deadline:
            return
        self._devices_probe_deadline = 0.0
        self._devices_probe_epoch = -1
        diagnostics.event("SPOTIFY_DEVICES_DIAGNOSTIC", source="spotify_api",
                          endpoint="available_devices", phase=phase, reason=reason,
                          attempt=self._devices_probe_attempts)

    def _devices_probe_pending(self):
        if not self._devices_probe_deadline:
            return False
        if time.monotonic() >= self._devices_probe_deadline:
            self._finish_devices_probe("expired", "operation_expired")
            return False
        if (self._stop.is_set() or self._source_mode != "spotify_api" or
                self._source_epoch != self._devices_probe_epoch):
            self._finish_devices_probe(reason="source_mismatch")
            return False
        if getattr(self._spotify, "primary_playback_revision", 0) != self._devices_probe_primary_revision:
            self._finish_devices_probe()
            return False
        if (self._manual_refresh is not None or not self._commands.empty() or
                self._pending_spotify_command is not None or
                self._confirmation_operation is not None or self._pending_control_operation is not None):
            self._finish_devices_probe(reason="pending_work")
            return False
        return True

    def _observe_primary_playback(self, data, automatic):
        if data and data.get("track_key"):
            self._finish_devices_probe()
        elif automatic and not self._devices_probe_used:
            # Consume the one session opportunity even if it later expires.
            self._devices_probe_used = True
            self._devices_probe_epoch = self._source_epoch
            self._devices_probe_deadline = time.monotonic() + DEVICES_DIAGNOSTIC_TTL_SECONDS
            self._devices_probe_attempts = 0
            self._devices_probe_primary_revision = getattr(self._spotify, "primary_playback_revision", 0)
            diagnostics.event("SPOTIFY_DEVICES_DIAGNOSTIC", source="spotify_api",
                              endpoint="available_devices", phase="accepted")

    def _devices_probe_can_start(self, manager):
        return (self._devices_probe_pending() and self._devices_probe_attempts < 1 and
                self._manual_refresh is None and self._commands.empty() and
                self._pending_spotify_command is None and self._confirmation_operation is None and
                self._find_media_sources(manager)[0] is None)

    def _start_devices_probe(self, manager):
        if not self._devices_probe_can_start(manager):
            return False
        self._devices_probe_attempts += 1
        diagnostics.event("SPOTIFY_DEVICES_DIAGNOSTIC", source="spotify_api",
                          endpoint="available_devices", phase="guarded",
                          attempt=self._devices_probe_attempts)
        return True

    def _enter_source_mode(self, mode):
        if self._source_mode == mode:
            return
        with self._control_lock:
            initial_owner = not self._source_mode
            self._source_mode = mode
            self._source_epoch += 1
            self._api_snapshot_epoch = -1
            self._last_api_snapshot_at = 0.0
            self._api_waiting = mode == "spotify_api"
            self._current_source = mode
        if not initial_owner:
            self._clear_api_work("source_mismatch")
            if mode == "windows_spotify":
                # Waiting's NONE cleared the engine cover. Re-read even the
                # same Windows song instead of trusting its old completion.
                self._last_track_key = ""
                self._windows_artwork_complete_key = ""
                self._api_fallback_complete_windows_key = ""
        if self._api_waiting:
            self._publish_api_waiting()

    def _publish_api_waiting(self, busy=False):
        if not self._api_waiting:
            return
        state = self._spotify.status()
        if state.get("state") == "rate_limited":
            snapshot = self._spotify_waiting_snapshot()
        else:
            local = state.get("local_budget", {})
            can_reserve = (local.get("profile") != "guarded" and
                not local.get("retry_remaining_seconds", 0) and not local.get("clock_guard_remaining_seconds", 0) and
                local.get("short_total_limit", 0)-local.get("short_used", 0)-local.get("reserved", 0) >= 3 and
                local.get("long_total_limit", 0)-local.get("long_used", 0)-local.get("reserved", 0) >= 3)
            admitted = (busy and self._manual_refresh is not None and
                        self._manual_refresh.operation is not None and local.get("profile") != "guarded" and
                        not local.get("retry_remaining_seconds", 0) and not local.get("clock_guard_remaining_seconds", 0) and
                        state.get("pacing", {}).get("next_allowed_at", 0) <= time.time())
            artist = "Checking status..." if admitted else (
                "Tap to check status" if can_reserve and time.monotonic() >= self._manual_next_at else
                "Waiting for next check")
            snapshot = MediaSnapshot(source="SPOTIFY API", title="Waiting for Spotify", artist=artist)
        self._current_source = "spotify_api"
        self._publish(snapshot, None)

    def _clear_api_work(self, reason):
        self._finish_devices_probe(reason=reason)
        self._finish_manual_refresh(self._manual_refresh)
        pending = self._pending_spotify_command
        self._pending_spotify_command = None
        items = [pending] if pending is not None else []
        while True:
            try:
                items.append(self._commands.get_nowait())
            except queue.Empty:
                break
        for command in items:
            self._finish_control(command, False, reason)
        for operation in (self._confirmation_operation, self._pending_control_operation):
            if operation is not None and self._spotify:
                self._spotify.finish_operation(operation)
        self._confirmation_operation = self._pending_control_operation = None

    def configure_spotify(self, spotify_settings: dict) -> None:
        """Apply local API and artwork settings without network traffic."""
        self._spotify_settings = dict(spotify_settings or {})
        self._artwork_retry_attempts = self._artwork_attempt_limit()
        if self._spotify:
            self._spotify.configure_pacing(self._spotify_settings)

    def status(self) -> dict:
        """Return diagnostic state only; this never polls Spotify."""
        if self._spotify is None:
            spotify = ({"state": "error", "message": "Spotify token file could not be loaded; retained unchanged"}
                       if self._spotify_load_error else {"state": "not_configured"})
        else:
            spotify = self._spotify.status()
        effective = None
        if self._spotify and self._current_source == "spotify_api":
            effective = self._spotify.poll_interval_seconds(idle=self._api_only_idle)
        return {
            "spotify": spotify,
            "windows_spotify_available": self._windows_spotify_available,
            "other_windows_media_available": self._other_windows_media_available,
            "current_source": self._current_source,
            "polling_mode": "adaptive",
            "effective_poll_interval_seconds": effective,
            "api_only_idle": self._api_only_idle,
            "api_snapshot_age_seconds": max(0,time.monotonic()-self._last_api_snapshot_at) if self._last_api_snapshot_at else None,
            "artwork_retry_attempts": self._artwork_retry_attempts,
            "checked_at": time.time(),
        }

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._run())
        except Exception as exc:
            diagnostics.event("MEDIA_BRIDGE_STOP", result="failure", reason="refresh_error",
                              stage="media_bridge", error_type=type(exc))
            self._on_error(f"Windows media bridge stopped: {exc}")

    async def _run(self) -> None:
        manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()

        while not self._stop.is_set():
            try:
                # Only a Spotify Windows session replaces the Web API. A
                # YouTube/Chrome session must not hide Spotify Connect data
                # from a phone or another device.
                spotify_session, other_media_playing = self._find_media_sources(manager)
                self._windows_spotify_available = spotify_session is not None
                self._other_windows_media_available = other_media_playing
                self._enter_source_mode("windows_spotify" if spotify_session is not None else
                    "spotify_api" if self._spotify and self._spotify.is_ready else "generic")
                self._devices_probe_pending()
                if spotify_session is not None:
                    self._current_source = "windows_spotify"
                    # A deferred Connect action belongs to the old remote
                    # source. Never replay it on Windows or hours later.
                    self._finish_control(self._pending_spotify_command, False, "source_mismatch")
                    self._pending_spotify_command = None
                    for operation in (self._confirmation_operation, self._pending_control_operation):
                        if operation is not None:
                            self._spotify.finish_operation(operation)
                    self._confirmation_operation = self._pending_control_operation = None
                    # The local Windows session owns both controls and display
                    # state. An API snapshot has a different track key and can
                    # overwrite a newer local song while its cover is in flight.
                    await self._handle_commands(spotify_session)
                    snapshot, artwork = await self._read_session(spotify_session)
                    self._publish(snapshot, artwork)
                    if (artwork is None and self._windows_api_artwork_due(snapshot, spotify_session)
                            and (self._windows_api_fallback_task is None or
                                 self._windows_api_fallback_task.done())):
                        self._windows_api_fallback_task = asyncio.create_task(
                            self._publish_windows_api_artwork(snapshot, spotify_session)
                        )
                elif (self._spotify and self._spotify.is_ready and
                      (self._spotify_api_retry_due() or self._manual_refresh is not None) and
                      (asyncio.get_running_loop().time() >= self._next_api_poll_at or
                       not self._commands.empty() or self._pending_spotify_command is not None or
                       self._confirmation_operation is not None or self._manual_refresh is not None or
                       self._activity_pending and self._activity_can_wake)):
                    self._current_source = "spotify_api"
                    self._activity_pending = False
                    manual = self._manual_refresh
                    diagnostic_read = False
                    try:
                        if manual is not None:
                            if not self._manual_refresh_valid(manual):
                                self._finish_manual_refresh(manual, phase="expired" if
                                    time.monotonic() >= manual.expires_at else "cancelled")
                                self._publish_api_waiting()
                                continue
                            if manual.operation is None:
                                manual.operation = self._spotify.begin_operation("control")
                            self._publish_api_waiting(busy=True)
                            def manual_guard():
                                if (not self._manual_refresh_valid(manual) or manual.attempts >= 2 or
                                        self._find_media_sources(manager)[0] is not None):
                                    return False
                                manual.attempts += 1
                                diagnostics.event("MEDIA_REFRESH", source="spotify_api",
                                                  read_origin="manual", phase="started",
                                                  attempt=manual.attempts)
                                return True
                            spotify_data, artwork_url = self._spotify.get_playback(
                                urgent=True, operation=manual.operation, start_guard=manual_guard,
                                retry_guard=lambda: manual.attempts < 2 and self._manual_refresh_valid(manual))
                            still_current = self._manual_refresh_valid(manual, check_ttl=False)
                            windows_now = self._find_media_sources(manager)[0] is not None
                            self._finish_manual_refresh(manual, phase="completed",
                                outcome="discarded" if not still_current or windows_now else
                                        "available" if spotify_data else "empty")
                            if not still_current or windows_now:
                                if windows_now:
                                    self._enter_source_mode("windows_spotify")
                                continue
                        else:
                            spotify_data = artwork_url = None
                        command_sent = self._handle_spotify_commands() if manual is None else False
                        if command_sent:
                            # Give Spotify Connect a brief moment to expose the new
                            # state before the confirming read. Controls and
                            # reads share the adaptive gate and Retry-After.
                            await asyncio.sleep(0.8)
                        operation = self._confirmation_operation
                        if manual is None:
                            if (operation is None and asyncio.get_running_loop().time() >= self._next_api_poll_at
                                    and self._devices_probe_pending() and self._devices_probe_can_start(manager)):
                                diagnostic_interval = self._spotify.poll_interval_seconds(idle=self._api_only_idle)
                                diagnostic_read = True
                                valid = self._spotify.diagnose_devices(
                                    start_guard=lambda: self._start_devices_probe(manager))
                                self._finish_devices_probe("completed", None if valid else "api_error")
                                # Devices only occupies this due slot; preserve A's state and age.
                                delay = self._api_only_poll_delay(idle=self._api_only_idle)
                                self._next_api_poll_at = asyncio.get_running_loop().time() + delay
                                await self._wait_for_spotify_work(delay)
                                continue
                            spotify_data, artwork_url = self._spotify.get_playback(
                                urgent=True, operation=operation
                            ) if operation is not None else self._spotify.get_playback()
                        self._observe_primary_playback(spotify_data, automatic=manual is None and operation is None)
                        if operation is not None:
                            self._spotify.finish_operation(operation)
                            self._confirmation_operation = None
                        diagnostics.event("MEDIA_API_SNAPSHOT", source="spotify_api",
                                          read_origin="manual" if manual is not None else
                                                      "confirmation" if operation is not None else "automatic",
                                          outcome="available" if spotify_data else "empty")
                        self._last_api_snapshot_at = time.monotonic()
                        self._api_snapshot_epoch = self._source_epoch
                        self._api_waiting = not bool(spotify_data and spotify_data.get("track_key"))
                        local = self._spotify.status().get("local_budget", {})
                        self._activity_can_wake = bool(local.get("activity_wake_allowed"))
                        self._spotify_retry_is_rate_limit = False
                        if spotify_data:
                            snapshot = MediaSnapshot(
                                available=True, **{**spotify_data, "source": "SPOTIFY API"}
                            )
                            self._api_only_idle = not snapshot.playing
                            # Publish metadata before downloading the cover.  The
                            # firmware switches to its built-in vinyl immediately.
                            self._publish(snapshot, None)
                            artwork = await self._try_api_artwork(
                                snapshot.track_key, artwork_url
                            )
                            if artwork:
                                self._publish(snapshot, artwork)
                            delay = self._api_only_poll_delay(idle=not snapshot.playing)
                            if manual is not None:
                                delay = max(delay, self._spotify.poll_interval_seconds(idle=not snapshot.playing))
                            self._next_api_poll_at = asyncio.get_running_loop().time() + delay
                            await self._wait_for_spotify_work(delay)
                            continue
                        self._publish_api_waiting()
                        self._api_only_idle = True
                        # Empty playback must never fall through to the 0.45s
                        # UI loop. Keep a low-cost API watch for Spotify while
                        # another player (for example YouTube) owns Windows.
                        delay = self._api_only_poll_delay(idle=True)
                        if manual is not None:
                            delay = max(delay, self._spotify.poll_interval_seconds(idle=True))
                        self._next_api_poll_at = asyncio.get_running_loop().time() + delay
                        await self._wait_for_spotify_work(delay)
                        continue
                    except SpotifyPacingError as exc:
                        if diagnostic_read:
                            if self._devices_probe_attempts:
                                self._finish_devices_probe("completed", "api_error")
                            elif isinstance(exc, SpotifyBudgetError) and exc.reason == "operation_expired":
                                self._finish_devices_probe(reason=exc.reason)
                            # Do not query failing durable storage or mutate/publish A here.
                            # A denied slot still waits a full normal interval; touch may interrupt.
                            delay = max(exc.wait_seconds, diagnostic_interval)
                            self._next_api_poll_at = asyncio.get_running_loop().time() + delay
                            await self._wait_for_spotify_work(delay)
                            continue
                        if manual is not None:
                            if (not self._manual_refresh_valid(manual) or
                                    isinstance(exc, SpotifyBudgetError) and
                                    exc.reason not in ("start_spacing", "profile")):
                                self._finish_manual_refresh(manual, phase="expired" if
                                    time.monotonic() >= manual.expires_at or
                                    getattr(exc, "reason", None) == "operation_expired" else "cancelled")
                        self._activity_can_wake = bool(self._spotify.status().get(
                            "local_budget", {}).get("activity_wake_allowed"))
                        self._next_api_poll_at = asyncio.get_running_loop().time() + exc.wait_seconds
                        if isinstance(exc, SpotifyBudgetError) and exc.reason in (
                                "operation_expired", "clock_guard", "history_corrupt", "history_io"):
                            self._clear_api_work(exc.reason)
                        self._publish_api_waiting()
                        if self._manual_refresh is not None:
                            await asyncio.sleep(min(POLL_INTERVAL_SECONDS, exc.wait_seconds))
                            continue
                        if self._commands.empty() and not self._pending_spotify_command:
                            await self._wait_for_spotify_work(exc.wait_seconds)
                        else:
                            # A queued explicit touch must not spin while the
                            # shared request guard is still active.
                            await asyncio.sleep(min(POLL_INTERVAL_SECONDS, exc.wait_seconds))
                        continue
                    except SpotifyRateLimitError as exc:
                        diagnostics.event("SPOTIFY_FALLBACK", reason=exc.reason,
                                          origin="saved_cooldown" if exc.cached else
                                                 "http_response",
                                          request_kind=exc.request_kind,
                                          wait_seconds=int(exc.retry_after_seconds))
                        self._spotify_retry_at = (
                            asyncio.get_running_loop().time() + exc.retry_after_seconds
                        )
                        self._spotify_retry_is_rate_limit = True
                        self._publish_no_windows_status()
                        message = "Spotify API paused until retry; no Windows media session"
                        if message != self._spotify_retry_message:
                            self._on_error(message)
                            self._spotify_retry_message = message
                    except SpotifyApiError as exc:
                        diagnostics.event("SPOTIFY_FALLBACK", reason="api_error")
                        # Do not preserve an old cover when Spotify is temporarily
                        # unavailable. Windows media (or the generic vinyl) becomes
                        # the source of truth until the next Web API attempt.
                        self._spotify_retry_at = asyncio.get_running_loop().time() + 60.0
                        self._spotify_retry_is_rate_limit = False
                        self._on_error(f"Spotify unavailable; using Windows media: {exc}")
                        self._publish_no_windows_status()
                    except Exception as exc:
                        if manual is None:
                            raise
                        # A strict parse/shape error or post-response metadata
                        # I/O must not replay this single-read operation.
                        self._finish_manual_refresh(manual)
                        delay = self._spotify.poll_interval_seconds(idle=True)
                        self._next_api_poll_at = asyncio.get_running_loop().time() + delay
                        diagnostics.event("MEDIA_REFRESH", result="failure", reason="refresh_error",
                                          stage="media_refresh", error_type=type(exc))
                        self._publish_api_waiting()
                        await self._wait_for_spotify_work(delay)
                        continue

                elif self._spotify and self._spotify.is_ready and self._spotify_api_retry_due():
                    # Local wait preserves last metadata, with its age exposed
                    # in status. Continue probing Windows sessions every 0.45s.
                    self._current_source = "spotify_api"
                    self._publish_api_waiting()
                else:
                    self._publish_no_windows_status()
            except Exception as exc:
                now = time.monotonic()
                if now - self._last_refresh_error_at >= 60.0:
                    diagnostics.event("MEDIA_REFRESH", result="failure", reason="refresh_error",
                                      stage="media_refresh", error_type=type(exc))
                    self._last_refresh_error_at = now
                self._on_error(f"Media refresh failed: {exc}")

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    def _spotify_api_retry_due(self) -> bool:
        if self._spotify_retry_is_rate_limit:
            # The persisted wall-clock deadline remains correct across a
            # Windows sleep/resume even if the loop's monotonic clock pauses.
            return self._spotify.status().get("state") != "rate_limited"
        return asyncio.get_running_loop().time() >= self._spotify_retry_at

    def _api_only_poll_delay(self, idle: bool) -> float:
        # The API bridge owns request-start deadlines. Waiting another whole
        # interval here would add HTTP/artwork latency to every active poll.
        # Legacy api_only_poll_interval_seconds is intentionally ignored.
        return self._spotify.poll_delay_seconds(idle=idle)

    def _spotify_waiting_snapshot(self) -> Optional[MediaSnapshot]:
        if not self._spotify:
            return None
        state = self._spotify.status()
        if state.get("state") != "rate_limited":
            return None
        try:
            retry_at = time.strftime("%d/%m %H:%M", time.localtime(
                float(state["retry_until"])))
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            retry_at = "later"
        return MediaSnapshot(source="SPOTIFY API", title="Spotify API paused",
                             artist=f"Retry {retry_at}")

    def _publish_no_windows_status(self) -> None:
        # Touch commands made during a long cooldown must not play back hours
        # later when the API becomes available again.
        self._clear_api_work("rate_limited")
        if self._source_mode == "spotify_api":
            self._api_waiting = True
            self._api_snapshot_epoch = -1
            self._last_api_snapshot_at = 0.0
        snapshot = self._spotify_waiting_snapshot()
        self._current_source = "spotify_api" if snapshot else "generic"
        self._publish(snapshot or MediaSnapshot(), None)

    async def _wait_for_spotify_work(self, delay_seconds: float) -> None:
        """Wait between API reads, but wake quickly when touch adds a command."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + min(POLL_INTERVAL_SECONDS, max(SPOTIFY_COMMAND_CHECK_SECONDS, delay_seconds))
        while not self._stop.is_set() and loop.time() < deadline:
            if self._pending_spotify_command or not self._commands.empty() or self._manual_refresh is not None:
                return
            if self._activity_pending and self._activity_can_wake:
                return
            await asyncio.sleep(
                min(SPOTIFY_COMMAND_CHECK_SECONDS, max(0.0, deadline - loop.time()))
            )

    def _handle_spotify_commands(self) -> bool:
        if self._confirmation_operation is not None:
            return False
        handled = False
        while True:
            if self._pending_spotify_command:
                action = self._pending_spotify_command
            else:
                try:
                    action = self._commands.get_nowait()
                except queue.Empty:
                    return handled

            try:
                if self._api_waiting:
                    self._finish_control(action, False, "no_playback")
                    self._pending_spotify_command = None
                    continue
                value = action.action if isinstance(action, MediaControlRequest) else action
                if isinstance(action, MediaControlRequest):
                    if action.source_epoch is not None and action.source_epoch != self._source_epoch:
                        self._finish_control(action, False, "source_mismatch")
                        self._pending_spotify_command = None
                        continue
                    if (time.monotonic() >= action.expires_at or
                            action.source is not None and action.source != self._current_source):
                        self._finish_control(action, False, "command_expired")
                        self._pending_spotify_command = None
                        continue
                    if action.operation is None:
                        action.operation = self._spotify.begin_operation("control")
                    operation = action.operation
                else:
                    if self._pending_control_operation is None:
                        self._pending_control_operation = self._spotify.begin_operation("control")
                    operation = self._pending_control_operation
                self._spotify.control(value, operation=operation)
            except SpotifyPacingError as exc:
                if isinstance(exc, SpotifyBudgetError) and exc.reason in (
                        "operation_expired", "clock_guard", "history_corrupt", "history_io"):
                    self._finish_control(action, False, exc.reason)
                    self._pending_spotify_command = None
                    raise
                self._pending_spotify_command = action
                raise
            except SpotifyRateLimitError:
                self._finish_control(action, False, "rate_limited")
                self._pending_spotify_command = None
                raise
            except Exception as exc:
                status = getattr(self._spotify, "last_control_http_status", None)
                self._finish_control(action, False, "api_error", type(exc), status)
                self._pending_spotify_command = None
                return handled
            self._pending_spotify_command = None
            self._finish_control(action, True)
            self._confirmation_operation = operation
            self._pending_control_operation = None
            # Make the play icon react immediately after Spotify accepts the
            # command. The confirming read remains authoritative.
            if value == "PLAY_PAUSE" and self._last_snapshot:
                optimistic = replace(
                    self._last_snapshot,
                    playing=not self._last_snapshot.playing,
                )
                self._publish(optimistic, None)
            handled = True
            return handled

    @staticmethod
    def _find_media_sources(manager):
        sessions = list(manager.get_sessions())
        for session in sessions:
            if "spotify" in session.source_app_user_model_id.lower():
                return session, False

        other_media_playing = False
        for session in sessions:
            try:
                if session.get_playback_info().playback_status == PlaybackStatus.PLAYING:
                    other_media_playing = True
                    break
            except Exception:
                pass
        return None, other_media_playing

    async def _handle_commands(self, session) -> bool:
        handled = False
        while True:
            try:
                action = self._commands.get_nowait()
            except queue.Empty:
                return handled

            try:
                command = action
                if isinstance(command, MediaControlRequest):
                    if (time.monotonic() >= command.expires_at or command.source is not None and
                            command.source != self._current_source):
                        self._finish_control(command, False, "command_expired")
                        continue
                    action = command.action
                if action == "PLAY_PAUSE":
                    accepted = await session.try_toggle_play_pause_async()
                elif action == "NEXT":
                    accepted = await session.try_skip_next_async()
                elif action == "PREVIOUS":
                    accepted = await session.try_skip_previous_async()
                else:
                    continue
            except Exception:
                self._finish_control(command, False, "api_error")
                diagnostics.event("MEDIA_CONTROL", action=action, result="failure")
                raise
            diagnostics.event("MEDIA_CONTROL", action=action,
                              result="failure" if accepted is False else "success")
            self._finish_control(command, accepted is not False)
            handled = handled or accepted is not False

    @staticmethod
    def _windows_track_key(session, props) -> str:
        return "|".join((session.source_app_user_model_id, props.title or "Unknown track",
            props.artist or props.album_artist or "Unknown artist", props.album_title or "",
            str(props.track_number)))


    def _artwork_attempt_limit(self) -> int:
        try:
            return min(
                5,
                max(1, int(self._spotify_settings.get(
                    "artwork_retry_attempts", DEFAULT_ARTWORK_RETRY_ATTEMPTS
                ))),
            )
        except (TypeError, ValueError):
            return DEFAULT_ARTWORK_RETRY_ATTEMPTS

    async def _try_api_artwork(self, track_key: str, artwork_url: Optional[str]) -> Optional[bytes]:
        source_epoch = self._source_epoch
        if track_key != self._api_artwork_key:
            self._api_artwork_key = track_key
            self._api_artwork_attempts = 0
            self._api_artwork_next_retry = 0.0
            self._api_artwork_complete_key = ""
            self._api_artwork_missing_reported = False
        if not artwork_url:
            if not self._api_artwork_missing_reported:
                diagnostics.event("ART_MISSING", source="spotify_api", reason="no_artwork_url")
                self._api_artwork_missing_reported = True
            return None
        if track_key == self._api_artwork_complete_key:
            return None
        now = time.monotonic()
        if now < self._api_artwork_next_retry:
            return None
        if self._api_artwork_attempts >= self._artwork_retry_attempts:
            self._api_artwork_attempts = 0
            diagnostics.event("ART_RETRY_RESUME", source="spotify_api")

        self._api_artwork_attempts += 1
        try:
            raw = await asyncio.to_thread(self._spotify.download_artwork, artwork_url)
        except Exception as exc:
            if source_epoch != self._source_epoch:
                return None
            return self._artwork_failed("spotify_api", "download_error", type(exc))
        if source_epoch != self._source_epoch:
            return None
        if not raw:
            return self._artwork_failed("spotify_api", "empty_artwork")
        try:
            artwork = self._to_vinyl_rgb888(raw)
        except Exception as exc:
            return self._artwork_failed("spotify_api", "convert_error", type(exc))
        self._api_artwork_complete_key = track_key
        diagnostics.event("ART_READY", source="spotify_api", bytes=len(artwork),
                          attempt=self._api_artwork_attempts)
        return artwork

    def _artwork_failed(self, source: str, reason: str, error_type=None) -> None:
        """Bound failed attempts, then try the same track once more after a quiet period."""
        if source == "spotify_api":
            attempts = self._api_artwork_attempts
            self._api_artwork_next_retry = time.monotonic() + (
                ARTWORK_EXHAUSTED_COOLDOWN_SECONDS if attempts >= self._artwork_retry_attempts
                else min(12.0, 1.5 * attempts)
            )
        else:
            attempts = self._windows_artwork_attempts
            self._windows_artwork_next_retry = time.monotonic() + (
                ARTWORK_EXHAUSTED_COOLDOWN_SECONDS if attempts >= self._artwork_retry_attempts
                else min(12.0, 1.5 * attempts)
            )
        diagnostics.event("ART_FETCH", source=source, result="failure", reason=reason,
                          attempt=attempts, retry_limit=self._artwork_retry_attempts,
                          stage="art_convert" if reason == "convert_error" else
                          "art_download" if source == "spotify_api" else "thumbnail_read",
                          error_type=error_type)
        if attempts >= self._artwork_retry_attempts:
            diagnostics.event("ART_RETRY_EXHAUSTED", source=source,
                              wait_seconds=int(ARTWORK_EXHAUSTED_COOLDOWN_SECONDS))
        return None

    def _windows_api_artwork_due(self, snapshot: MediaSnapshot, session) -> bool:
        return bool(self._spotify and self._spotify.is_ready and snapshot.available
                and "spotify" in session.source_app_user_model_id.lower()
                and snapshot.track_key != self._windows_artwork_complete_key
                and snapshot.track_key != self._api_fallback_complete_windows_key
                and (self._windows_artwork_missing_reported or
                     self._windows_artwork_attempts >= self._artwork_retry_attempts)
                and time.monotonic() >= self._windows_api_fallback_next_at)

    async def _publish_windows_api_artwork(self, snapshot: MediaSnapshot, session) -> None:
        """Fetch without holding up Windows media polling or touch commands."""
        try:
            source_epoch = self._source_epoch
            artwork = await self._try_windows_api_artwork(snapshot, session)
            current = self._last_snapshot
            if (artwork and source_epoch == self._source_epoch and not self._stop.is_set() and self._current_source == "windows_spotify"
                    and current and current.track_key == snapshot.track_key):
                self._publish(current, artwork)
        except Exception as exc:
            diagnostics.event("ART_API_FALLBACK", result="failure", reason="api_error",
                              stage="api_fallback", error_type=type(exc))

    async def _try_windows_api_artwork(self, snapshot: MediaSnapshot, session) -> Optional[bytes]:
        """Use a paced API read only when a Spotify Windows thumbnail is unavailable."""
        source_epoch = self._source_epoch
        if not self._windows_api_artwork_due(snapshot, session):
            return None
        now = time.monotonic()
        if now < self._windows_api_fallback_next_at:
            return None
        self._windows_api_fallback_next_at = now + WINDOWS_API_ART_FALLBACK_SECONDS
        try:
            playback, artwork_url = await asyncio.to_thread(
                self._spotify.get_playback, artwork_fallback=True)
        except SpotifyPacingError as exc:
            self._windows_api_fallback_next_at = now + max(
                WINDOWS_API_ART_FALLBACK_SECONDS, exc.wait_seconds)
            diagnostics.event("ART_API_FALLBACK", result="skipped", reason="pacing",
                              stage="api_fallback", wait_seconds=int(exc.wait_seconds))
            return None
        except SpotifyRateLimitError as exc:
            self._windows_api_fallback_next_at = now + max(
                WINDOWS_API_ART_FALLBACK_SECONDS, exc.retry_after_seconds)
            diagnostics.event("ART_API_FALLBACK", result="skipped", reason=exc.reason,
                              origin="saved_cooldown" if exc.cached else "http_response",
                              stage="api_fallback", request_kind="artwork_fallback",
                              wait_seconds=int(exc.retry_after_seconds))
            return None
        except Exception as exc:
            diagnostics.event("ART_API_FALLBACK", result="failure", reason="api_error",
                              stage="api_fallback", error_type=type(exc))
            return None
        if source_epoch != self._source_epoch:
            return None
        if not playback:
            diagnostics.event("ART_API_FALLBACK", result="skipped", reason="no_playback")
            return None
        if (str(playback.get("title", "")).strip().casefold() != snapshot.title.strip().casefold()
                or str(playback.get("artist", "")).strip().casefold() !=
                snapshot.artist.strip().casefold()):
            diagnostics.event("ART_API_FALLBACK", result="skipped", reason="track_mismatch")
            return None
        artwork = await self._try_api_artwork(playback.get("track_key", ""), artwork_url)
        if source_epoch != self._source_epoch:
            return None
        if artwork:
            self._api_fallback_complete_windows_key = snapshot.track_key
            diagnostics.event("ART_API_FALLBACK", result="success", bytes=len(artwork))
        return artwork

    async def _read_session(self, session):
        props = await session.try_get_media_properties_async()
        playback = session.get_playback_info()
        timeline = session.get_timeline_properties()

        source_id = session.source_app_user_model_id
        source = self._friendly_source(source_id)
        title = props.title or "Unknown track"
        artist = props.artist or props.album_artist or "Unknown artist"
        playing = playback.playback_status == PlaybackStatus.PLAYING

        position = max(0, int(timeline.position.total_seconds()))
        duration = max(0, int(timeline.end_time.total_seconds()))
        if playing:
            try:
                updated = timeline.last_updated_time
                now = dt.datetime.now(updated.tzinfo or dt.timezone.utc)
                position += max(0, int((now - updated).total_seconds()))
            except Exception:
                pass
        if duration:
            position = min(position, duration)

        track_key = self._windows_track_key(session, props)
        artwork = None
        if track_key != self._last_track_key:
            # Clear the previous cover before awaiting the new thumbnail.
            # The engine maps this metadata-only update to the generic vinyl,
            # so an old label never represents the newly selected song.
            self._last_track_key = track_key
            snapshot = MediaSnapshot(
                available=True,
                source=source,
                title=title,
                artist=artist,
                playing=playing,
                position_seconds=position,
                duration_seconds=duration,
                track_key=track_key,
            )
            self._publish(snapshot, None)

            self._windows_artwork_key = track_key
            self._windows_artwork_attempts = 0
            self._windows_artwork_next_retry = 0.0
            self._windows_artwork_complete_key = ""
            self._windows_artwork_missing_reported = False
            self._windows_api_fallback_next_at = 0.0
            self._api_fallback_complete_windows_key = ""
            # API artwork may have completed for an earlier play of this same
            # Spotify track. Returning after another Windows song needs a new
            # upload, even though its API track ID is unchanged.
            self._api_artwork_key = ""
            self._api_artwork_attempts = 0
            self._api_artwork_next_retry = 0.0
            self._api_artwork_complete_key = ""
            self._api_artwork_missing_reported = False

        if props.thumbnail:
            self._windows_artwork_missing_reported = False
        elif not self._windows_artwork_missing_reported:
            diagnostics.event("ART_MISSING", source="windows_spotify" if source == "SPOTIFY"
                              else "windows_other", reason="no_thumbnail")
            self._windows_artwork_missing_reported = True

        now = time.monotonic()
        if (props.thumbnail and self._windows_artwork_attempts >= self._artwork_retry_attempts
                and now >= self._windows_artwork_next_retry
                and track_key != self._windows_artwork_complete_key):
            self._windows_artwork_attempts = 0
            diagnostics.event("ART_RETRY_RESUME", source="windows_spotify" if source == "SPOTIFY"
                              else "windows_other")

        if (
            props.thumbnail
            and track_key != self._windows_artwork_complete_key
            and self._windows_artwork_attempts < self._artwork_retry_attempts
            and now >= self._windows_artwork_next_retry
        ):
            self._windows_artwork_attempts += 1
            art_source = "windows_spotify" if source == "SPOTIFY" else "windows_other"
            try:
                thumbnail = await self._read_thumbnail(props.thumbnail)
            except Exception as exc:
                self._artwork_failed(art_source, "thumbnail_error", type(exc))
            else:
                if not thumbnail:
                    self._artwork_failed(art_source, "empty_artwork")
                else:
                    try:
                        if art_source == "windows_spotify":
                            artwork = self._to_vinyl_rgb888(thumbnail, windows_spotify_thumbnail=True)
                        else:
                            artwork = self._to_vinyl_rgb888(thumbnail)
                    except Exception as exc:
                        self._artwork_failed(art_source, "convert_error", type(exc))
                    else:
                        self._windows_artwork_complete_key = track_key
                        diagnostics.event("ART_READY", source=art_source, bytes=len(artwork),
                                          attempt=self._windows_artwork_attempts)

        return (
            MediaSnapshot(
                available=True,
                source=source,
                title=title,
                artist=artist,
                playing=playing,
                position_seconds=position,
                duration_seconds=duration,
                track_key=track_key,
            ),
            artwork,
        )

    async def _read_thumbnail(self, thumbnail) -> bytes:
        stream = await thumbnail.open_read_async()
        size = int(stream.size)
        if size <= 0 or size > 8 * 1024 * 1024:
            return b""
        reader = DataReader(stream)
        await reader.load_async(size)
        payload = bytearray(size)
        reader.read_bytes(payload)
        return bytes(payload)

    @staticmethod
    def _to_vinyl_rgb888(image_bytes: bytes, *, windows_spotify_thumbnail: bool = False) -> bytes:
        """Build a colour-safe vinyl graphic with a full, clean cover label.

        RGB888 is deliberately used on the wire.  The ESP32 performs the final
        conversion with LVGL's own colour helper, avoiding controller-specific
        RGB565 byte-order differences.
        """
        if not image_bytes or len(image_bytes) > 8 * 1024 * 1024:
            raise ValueError("Artwork exceeds byte limit")
        # Restrict decoder selection before opening untrusted SMTC/API input.
        with Image.open(io.BytesIO(image_bytes), formats=("JPEG", "PNG")) as source:
            if (source.width <= 0 or source.height <= 0 or
                    max(source.size) > 4096 or source.width * source.height > 16 * 1024 * 1024 or
                    getattr(source, "is_animated", False)):
                raise ValueError("Unsupported artwork dimensions or animation")
            album_box = spotify_smtc_album_box(source) if windows_spotify_thumbnail else None
            source_rgb = (source.crop(album_box) if album_box is not None else source).convert("RGB")
            # Spotify's Windows thumbnail can include a tiny source badge at
            # the outer edge. A small centre crop removes that chrome before
            # filling the circular record label.
            inset = int(min(source_rgb.size) * 0.06)
            if album_box is None and inset > 0 and source_rgb.width > inset * 2 and source_rgb.height > inset * 2:
                source_rgb = source_rgb.crop((
                    inset, inset, source_rgb.width - inset, source_rgb.height - inset,
                ))
            label_size = int(round(ART_SIZE * 0.72))
            label = ImageOps.fit(
                source_rgb,
                (label_size, label_size),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )

        # Exact LVGL chroma-key green makes the square image corners
        # transparent after rotation, preventing the clipped/half-vinyl look.
        vinyl = Image.new("RGB", (ART_SIZE, ART_SIZE), (0, 255, 0))
        draw = ImageDraw.Draw(vinyl)
        edge = ART_SIZE - 3
        draw.ellipse((2, 2, edge, edge), fill=(16, 17, 20), outline=(61, 64, 70), width=2)

        # Subtle grooves plus two asymmetric highlights make rotation visible.
        for inset, shade in ((7, 35), (11, 24), (15, 39), (19, 27), (23, 43)):
            draw.ellipse(
                (inset, inset, ART_SIZE - 1 - inset, ART_SIZE - 1 - inset),
                outline=(shade, shade + 1, shade + 4),
                width=1,
            )
        draw.arc((6, 6, ART_SIZE - 7, ART_SIZE - 7), 202, 286, fill=(91, 94, 101), width=2)
        draw.arc((10, 10, ART_SIZE - 11, ART_SIZE - 11), 20, 66, fill=(41, 44, 50), width=2)
        center = ART_SIZE // 2
        draw.ellipse((center - 3, 4, center + 3, 10), fill=(30, 215, 96))

        label_mask = Image.new("L", label.size, 0)
        ImageDraw.Draw(label_mask).ellipse((0, 0, label_size - 1, label_size - 1), fill=255)
        label_xy = ((ART_SIZE - label_size) // 2,) * 2
        vinyl.paste(label, label_xy, label_mask)
        draw.ellipse((center - 4, center - 4, center + 4, center + 4), fill=(232, 235, 238))
        draw.ellipse((center - 1, center - 1, center + 1, center + 1), fill=(8, 10, 12))

        return vinyl.tobytes("raw", "RGB")

    def _publish(self, snapshot: MediaSnapshot, artwork: Optional[bytes]) -> None:
        if self._last_snapshot and self._last_snapshot.available and not snapshot.available:
            # The engine clears the displayed cover on MEDIA_STATE:NONE. A
            # return to the same Spotify track must upload its cover again.
            self._api_artwork_key = ""
            self._api_artwork_complete_key = ""
            self._api_artwork_attempts = 0
            self._api_artwork_next_retry = 0.0
        source = self._current_source if self._current_source in (
            "windows_spotify", "spotify_api", "generic") else "unknown"
        if source != self._last_reported_source:
            diagnostics.event("MEDIA_SOURCE", source=source)
            self._last_reported_source = source
        if snapshot.track_key and snapshot.track_key != self._last_reported_track:
            self._track_seq += 1
            self._last_reported_track = snapshot.track_key
            diagnostics.event("MEDIA_TRACK", source=source, track_seq=self._track_seq)
        changed = snapshot != self._last_snapshot
        if changed or artwork is not None:
            self._on_update(snapshot, artwork)
            self._last_snapshot = snapshot

    @staticmethod
    def _friendly_source(source_id: str) -> str:
        lowered = source_id.lower()
        if "spotify" in lowered:
            return "SPOTIFY"
        if "firefox" in lowered:
            return "FIREFOX"
        if "chrome" in lowered:
            return "CHROME"
        if "msedge" in lowered:
            return "EDGE"
        return source_id.split(".")[0][:12].upper() or "WINDOWS"
