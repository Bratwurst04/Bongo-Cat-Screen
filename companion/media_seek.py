"""Bounded relative seek commands; no network or display side effects."""
from dataclasses import dataclass
from typing import Optional
import zlib

MEDIA_ACTIONS = frozenset(("PLAY_PAUSE", "NEXT", "PREVIOUS", "SEEK:+15", "SEEK:-15"))
SEEK_LIFETIME_SECONDS = 5.0


def media_context_id(source: str, track_key: str) -> int:
    return (zlib.crc32((source + "\0" + track_key).encode("utf-8")) or 1) if track_key else 0


def parse_media_command(line: str) -> Optional[tuple]:
    prefix = "MEDIA_CMD:"
    action = line[len(prefix):] if line.startswith(prefix) else ""
    if action in ("PLAY_PAUSE", "NEXT", "PREVIOUS"):
        return action, None
    parts = action.split(":")
    if len(parts) != 3 or ":".join(parts[:2]) not in ("SEEK:+15", "SEEK:-15"):
        return None
    value = parts[2]
    if (not value.isascii() or not value.isdecimal() or len(value) > 10 or
            not 1 <= int(value) <= 0xFFFFFFFF or str(int(value)) != value):
        return None
    return ":".join(parts[:2]), int(value)


def clamp_seek(position: int, delta: int, lower: int, upper: int) -> Optional[int]:
    if lower < 0 or upper < lower:
        return None
    return min(upper, max(lower, position + delta))


@dataclass(frozen=True)
class SpotifySeekContext:
    track_key: str
    device_id: str
    position_ms: int
    duration_ms: int
    playing: bool
    received_at: float
    operation: object = None


@dataclass
class RelativeSeek:
    action: str
    source: str
    track_key: str
    device_id: str
    expires_at: float
    context: Optional[SpotifySeekContext] = None
    operation: object = None

    @property
    def delta_seconds(self) -> int:
        return 15 if self.action == "SEEK:+15" else -15


@dataclass
class MediaControlRequest:
    action: str
    source: Optional[str]
    expires_at: float
    operation: object = None
    source_epoch: Optional[int] = None


@dataclass
class MediaRefreshRequest:
    source_epoch: int
    expires_at: float
    operation: object = None
    attempts: int = 0
