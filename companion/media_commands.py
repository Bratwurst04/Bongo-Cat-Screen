"""Bounded media controls and neutral display track identity."""
from dataclasses import dataclass
from typing import Optional
import zlib

MEDIA_ACTIONS = frozenset(("PLAY_PAUSE", "NEXT", "PREVIOUS"))


def media_track_context_id(source: str, track_key: str) -> int:
    return (zlib.crc32((source + "\0" + track_key).encode("utf-8")) or 1) if track_key else 0


def parse_media_command(line: str) -> Optional[str]:
    prefix = "MEDIA_CMD:"
    action = line[len(prefix):] if line.startswith(prefix) else ""
    return action if action in MEDIA_ACTIONS else None


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
