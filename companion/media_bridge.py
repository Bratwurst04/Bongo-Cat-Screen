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
        self._last_track_key = ""
        self._spotify_retry_at = 0.0
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
        self._api_artwork_key = ""
        self._api_artwork_attempts = 0
        self._api_artwork_next_retry = 0.0
        self._api_artwork_complete_key = ""
        self._spotify_refresh_requested = False
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
        if action in ("NEXT", "PREVIOUS"):
            # Only explicit track changes from the display use an urgent API
            # confirmation. Normal playback remains adaptive and low-cost.
            self._spotify_refresh_requested = True
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
            "artwork_retry_attempts": self._artwork_retry_attempts,
            "checked_at": time.time(),
        }

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._run())
        except Exception as exc:
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
                    command_sent = await self._handle_commands(spotify_session)
                    if command_sent and self._spotify_refresh_requested:
                        self._spotify_refresh_requested = False
                        # Spotify Connect needs a short moment to commit the
                        # skip. Then one user-driven API read confirms the new
                        # metadata instead of waiting for the normal poll.
                        await asyncio.sleep(0.35)
                        await self._try_urgent_spotify_refresh()
                    snapshot, artwork = await self._read_session(spotify_session)
                    self._publish(snapshot, artwork)
                elif (self._spotify and self._spotify.is_ready and
                      asyncio.get_running_loop().time() >= self._spotify_retry_at):
                    self._current_source = "spotify_api"
                    try:
                        command_sent = self._handle_spotify_commands()
                        if command_sent:
                            # Give Spotify Connect a brief moment to expose the new
                            # state before the confirming read.
                            await asyncio.sleep(0.12)
                        spotify_data, artwork_url = self._spotify.get_playback()
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
                                self._spotify.poll_delay_seconds(idle=not snapshot.playing)
                            )
                            continue
                        self._publish(MediaSnapshot(source="SPOTIFY API"), None)
                        # Empty playback must never fall through to the 0.45s
                        # UI loop. Keep a low-cost API watch for Spotify while
                        # another player (for example YouTube) owns Windows.
                        await self._wait_for_spotify_work(
                            self._spotify.poll_delay_seconds(idle=True)
                        )
                        continue
                    except SpotifyPacingError as exc:
                        await self._wait_for_spotify_work(exc.wait_seconds)
                        continue
                    except SpotifyRateLimitError as exc:
                        self._spotify_retry_at = (
                            asyncio.get_running_loop().time() + exc.retry_after_seconds
                        )
                        message = f"Spotify rate limited; using Windows media until retry"
                        if message != self._spotify_retry_message:
                            self._on_error(message)
                            self._spotify_retry_message = message
                    except SpotifyApiError as exc:
                        # Do not preserve an old cover when Spotify is temporarily
                        # unavailable. Windows media (or the generic vinyl) becomes
                        # the source of truth until the next Web API attempt.
                        self._spotify_retry_at = asyncio.get_running_loop().time() + 60.0
                        self._on_error(f"Spotify unavailable; using Windows media: {exc}")

                else:
                    self._current_source = "generic"
                    snapshot = MediaSnapshot()
                    self._publish(snapshot, None)
            except Exception as exc:
                self._on_error(f"Media refresh failed: {exc}")

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

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

    async def _try_urgent_spotify_refresh(self) -> None:
        if not (self._spotify and self._spotify.is_ready):
            return
        try:
            spotify_data, artwork_url = await asyncio.to_thread(
                self._spotify.get_playback, True
            )
            if not spotify_data:
                return
            snapshot = MediaSnapshot(
                available=True, **{**spotify_data, "source": "SPOTIFY API"}
            )
            self._publish(snapshot, None)
            artwork = await self._try_api_artwork(snapshot.track_key, artwork_url)
            if artwork:
                self._publish(snapshot, artwork)
        except (SpotifyPacingError, SpotifyRateLimitError, SpotifyApiError):
            # The local Windows session still updates normally if Spotify is
            # unavailable or this one explicit request is paced.
            return

    async def _handle_commands(self, session) -> bool:
        handled = False
        while True:
            try:
                action = self._commands.get_nowait()
            except queue.Empty:
                return handled

            if action == "PLAY_PAUSE":
                await session.try_toggle_play_pause_async()
                handled = True
            elif action == "NEXT":
                await session.try_skip_next_async()
                handled = True
            elif action == "PREVIOUS":
                await session.try_skip_previous_async()
                handled = True

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
        if (
            not artwork_url
            or track_key == self._api_artwork_complete_key
            or self._api_artwork_attempts >= self._artwork_retry_attempts
            or time.monotonic() < self._api_artwork_next_retry
        ):
            return None

        self._api_artwork_attempts += 1
        try:
            raw = await asyncio.to_thread(self._spotify.download_artwork, artwork_url)
            if raw:
                self._api_artwork_complete_key = track_key
                return self._to_vinyl_rgb888(raw)
        except Exception:
            pass
        self._api_artwork_next_retry = time.monotonic() + min(
            12.0, 1.5 * self._api_artwork_attempts
        )
        return None

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

        if (
            props.thumbnail
            and track_key != self._windows_artwork_complete_key
            and self._windows_artwork_attempts < self._artwork_retry_attempts
            and time.monotonic() >= self._windows_artwork_next_retry
        ):
            self._windows_artwork_attempts += 1
            try:
                thumbnail = await self._read_thumbnail(props.thumbnail)
                if thumbnail:
                    artwork = self._to_vinyl_rgb888(thumbnail)
                    self._windows_artwork_complete_key = track_key
                else:
                    raise ValueError("empty thumbnail")
            except Exception:
                self._windows_artwork_next_retry = time.monotonic() + min(
                    12.0, 1.5 * self._windows_artwork_attempts
                )

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
