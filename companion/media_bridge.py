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

from PIL import Image, ImageDraw, ImageOps
from spotify_api import (
    SpotifyApiBridge,
    SpotifyApiError,
    SpotifyPacingError,
    SpotifyRateLimitError,
)
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager,
)
from winrt.windows.storage.streams import DataReader


ART_SIZE = 112
POLL_INTERVAL_SECONDS = 0.45
SPOTIFY_COMMAND_CHECK_SECONDS = 0.05
DEFAULT_ARTWORK_RETRY_ATTEMPTS = 5
ARTWORK_EXHAUSTED_COOLDOWN_SECONDS = 90.0
WINDOWS_API_ART_FALLBACK_SECONDS = 60.0
# API-only playback is usually on a phone or another Connect device. The
# display advances progress locally, so a slower poll avoids thousands of
# unnecessary /me/player requests per day.
SPOTIFY_API_ONLY_POLL_FLOOR_SECONDS = 15.0


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
        self._commands: queue.Queue[str] = queue.Queue()
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
        if spotify_client_id and spotify_token_path:
            self._spotify = SpotifyApiBridge(
                spotify_client_id, spotify_token_path, self._spotify_settings
            )

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

    def control(self, action: str) -> None:
        action = action.upper()
        self._commands.put(action)

    def configure_spotify(self, spotify_settings: dict) -> None:
        """Apply local API and artwork settings without network traffic."""
        self._spotify_settings = dict(spotify_settings or {})
        self._artwork_retry_attempts = self._artwork_attempt_limit()
        if self._spotify:
            self._spotify.configure_pacing(self._spotify_settings)

    def status(self) -> dict:
        """Return diagnostic state only; this never polls Spotify."""
        if self._spotify is None:
            spotify = {"state": "not_configured"}
        else:
            spotify = self._spotify.status()
        return {
            "spotify": spotify,
            "windows_spotify_available": self._windows_spotify_available,
            "other_windows_media_available": self._other_windows_media_available,
            "current_source": self._current_source,
            "api_only_poll_floor_seconds": SPOTIFY_API_ONLY_POLL_FLOOR_SECONDS,
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
                if spotify_session is not None:
                    self._current_source = "windows_spotify"
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
                      self._spotify_api_retry_due()):
                    self._current_source = "spotify_api"
                    try:
                        command_sent = self._handle_spotify_commands()
                        if command_sent:
                            # Give Spotify Connect a brief moment to expose the new
                            # state before the confirming read.
                            await asyncio.sleep(0.12)
                        spotify_data, artwork_url = self._spotify.get_playback()
                        self._spotify_retry_is_rate_limit = False
                        if spotify_data:
                            snapshot = MediaSnapshot(
                                available=True, **{**spotify_data, "source": "SPOTIFY API"}
                            )
                            # Publish metadata before downloading the cover.  The
                            # firmware switches to its built-in vinyl immediately.
                            self._publish(snapshot, None)
                            artwork = await self._try_api_artwork(
                                snapshot.track_key, artwork_url
                            )
                            if artwork:
                                self._publish(snapshot, artwork)
                            await self._wait_for_spotify_work(
                                self._api_only_poll_delay(idle=not snapshot.playing)
                            )
                            continue
                        self._publish(MediaSnapshot(source="SPOTIFY API"), None)
                        # Empty playback must never fall through to the 0.45s
                        # UI loop. Keep a low-cost API watch for Spotify while
                        # another player (for example YouTube) owns Windows.
                        await self._wait_for_spotify_work(
                            self._api_only_poll_delay(idle=True)
                        )
                        continue
                    except SpotifyPacingError as exc:
                        await self._wait_for_spotify_work(exc.wait_seconds)
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
        return max(SPOTIFY_API_ONLY_POLL_FLOOR_SECONDS,
                   self._spotify.poll_delay_seconds(idle=idle))

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
        while True:
            try:
                self._commands.get_nowait()
            except queue.Empty:
                break
        snapshot = self._spotify_waiting_snapshot()
        self._current_source = "spotify_api" if snapshot else "generic"
        self._publish(snapshot or MediaSnapshot(), None)

    async def _wait_for_spotify_work(self, delay_seconds: float) -> None:
        """Wait between API reads, but wake quickly when touch adds a command."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(SPOTIFY_COMMAND_CHECK_SECONDS, delay_seconds)
        while not self._stop.is_set() and loop.time() < deadline:
            if not self._commands.empty():
                return
            await asyncio.sleep(
                min(SPOTIFY_COMMAND_CHECK_SECONDS, max(0.0, deadline - loop.time()))
            )

    def _handle_spotify_commands(self) -> bool:
        handled = False
        while True:
            try:
                action = self._commands.get_nowait()
            except queue.Empty:
                return handled

            # Make the play icon react immediately. The next Web API read is
            # still authoritative and corrects it if another device changed
            # state at the same time.
            if action == "PLAY_PAUSE" and self._last_snapshot:
                optimistic = replace(
                    self._last_snapshot,
                    playing=not self._last_snapshot.playing,
                )
                self._publish(optimistic, None)
            self._spotify.control(action)
            handled = True

    @staticmethod
    def _find_media_sources(manager):
        sessions = list(manager.get_sessions())
        for session in sessions:
            if "spotify" in session.source_app_user_model_id.lower():
                return session, False

        other_media_playing = False
        for session in sessions:
            try:
                if str(session.get_playback_info().playback_status).endswith("PLAYING"):
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
                if action == "PLAY_PAUSE":
                    accepted = await session.try_toggle_play_pause_async()
                elif action == "NEXT":
                    accepted = await session.try_skip_next_async()
                elif action == "PREVIOUS":
                    accepted = await session.try_skip_previous_async()
                else:
                    continue
            except Exception:
                diagnostics.event("MEDIA_CONTROL", action=action, result="failure")
                raise
            diagnostics.event("MEDIA_CONTROL", action=action,
                              result="failure" if accepted is False else "success")
            handled = handled or accepted is not False

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
            return self._artwork_failed("spotify_api", "download_error", type(exc))
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
            artwork = await self._try_windows_api_artwork(snapshot, session)
            current = self._last_snapshot
            if (artwork and not self._stop.is_set() and self._current_source == "windows_spotify"
                    and current and current.track_key == snapshot.track_key):
                self._publish(current, artwork)
        except Exception as exc:
            diagnostics.event("ART_API_FALLBACK", result="failure", reason="api_error",
                              stage="api_fallback", error_type=type(exc))

    async def _try_windows_api_artwork(self, snapshot: MediaSnapshot, session) -> Optional[bytes]:
        """Use a paced API read only when a Spotify Windows thumbnail is unavailable."""
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
        if not playback:
            diagnostics.event("ART_API_FALLBACK", result="skipped", reason="no_playback")
            return None
        if (str(playback.get("title", "")).strip().casefold() != snapshot.title.strip().casefold()
                or str(playback.get("artist", "")).strip().casefold() !=
                snapshot.artist.strip().casefold()):
            diagnostics.event("ART_API_FALLBACK", result="skipped", reason="track_mismatch")
            return None
        artwork = await self._try_api_artwork(playback.get("track_key", ""), artwork_url)
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
        playing = str(playback.playback_status).endswith("PLAYING")

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

        track_key = "|".join(
            (source_id, title, artist, props.album_title or "", str(props.track_number))
        )
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
    def _to_vinyl_rgb888(image_bytes: bytes) -> bytes:
        """Build a colour-safe vinyl graphic with a full, clean cover label.

        RGB888 is deliberately used on the wire.  The ESP32 performs the final
        conversion with LVGL's own colour helper, avoiding controller-specific
        RGB565 byte-order differences.
        """
        with Image.open(io.BytesIO(image_bytes)) as source:
            source_rgb = source.convert("RGB")
            # Spotify's Windows thumbnail can include a tiny source badge at
            # the outer edge. A small centre crop removes that chrome before
            # filling the circular record label.
            inset = int(min(source_rgb.size) * 0.06)
            if inset > 0 and source_rgb.width > inset * 2 and source_rgb.height > inset * 2:
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
