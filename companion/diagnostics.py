"""Small, privacy-limited diagnostic log and manual ZIP export.

Callers supply event names and a fixed set of non-content fields. In
particular, raw exception messages, track metadata, URLs and artwork are never
accepted by this module.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import zipfile
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_BYTES = 256 * 1024
LOG_BACKUPS = 3
_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,47}$")
_ENUMS = {
    "source": {"windows_spotify", "spotify_api", "generic", "windows_other", "unknown"},
    "reason": {
        "no_port", "open_error", "read_error", "write_error", "stale_reply",
        "download_error", "empty_artwork", "convert_error", "thumbnail_error",
        "ack_timeout", "queue_full", "connection_lost", "retry_exhausted",
        "refresh_error", "rate_limited", "quota_exceeded", "unspecified_429",
        "api_error", "pacing", "startup_error",
        "no_artwork_url", "no_thumbnail",
        "device_error", "track_mismatch", "no_playback",
    },
    "result": {"success", "failure", "skipped", "retry", "ready"},
    "state": {"playing", "paused", "none"},
    "stage": {"app_start", "app_run", "serial_open", "serial_read", "serial_write",
              "media_refresh", "media_bridge", "art_download", "art_convert",
              "thumbnail_read", "api_fallback", "export"},
    "request_kind": {"playback_poll", "playback_urgent", "artwork_fallback",
                     "control", "other"},
    "action": {"PLAY_PAUSE", "NEXT", "PREVIOUS"},
    "origin": {"http_response", "saved_cooldown"},
}
_NUMBER_FIELDS = {"attempt", "bytes", "track_seq", "wait_seconds", "retry_limit",
                  "window_seconds", "interval_ms", "next_interval_ms",
                  "request_total", "calls_30s",
                  "playback_poll", "playback_urgent", "artwork_fallback",
                  "control", "other"}
_ERROR_TYPES = {
    "OSError", "PermissionError", "FileNotFoundError", "TimeoutError",
    "ConnectionError", "RuntimeError", "ValueError", "TypeError", "KeyError",
    "AttributeError", "SerialException", "SerialTimeoutException",
    "SpotifyApiError", "SpotifyPacingError", "SpotifyRateLimitError",
    "HTTPError", "URLError", "COMError", "UnidentifiedImageError",
}


class Diagnostics:
    def __init__(self, log_dir: Path | None = None):
        local = os.environ.get("LOCALAPPDATA")
        self.log_dir = Path(log_dir) if log_dir else (
            Path(local) if local else Path.home() / "AppData" / "Local"
        ) / "BongoDesk" / "logs"
        self._logger = logging.getLogger(f"bongodesk.diagnostics.{id(self)}")
        self._logger.propagate = False
        self._logger.setLevel(logging.INFO)
        self._handler = None

    def start(self) -> None:
        if self._handler:
            return
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                self.log_dir / "events.log", maxBytes=LOG_BYTES,
                backupCount=LOG_BACKUPS, encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            self._logger.addHandler(handler)
            self._handler = handler
        except OSError:
            # Diagnostics must never prevent the companion from starting.
            pass

    def event(self, name: str, **fields) -> None:
        if not self._handler or not isinstance(name, str) or not _NAME.fullmatch(name):
            return
        safe = []
        for key, value in fields.items():
            if key in _NUMBER_FIELDS and type(value) in (int, float):
                safe.append(f"{key}={value}")
            elif key in _ENUMS and isinstance(value, str) and value in _ENUMS[key]:
                safe.append(f"{key}={value}")
            elif key == "error_type" and isinstance(value, type) and issubclass(value, BaseException):
                safe.append(f"error_type={value.__name__ if value.__name__ in _ERROR_TYPES else 'OtherError'}")
        try:
            self._logger.info("%s%s", name, " " + " ".join(safe) if safe else "")
        except Exception:
            pass

    def export(self, destination: Path | None = None) -> Path:
        """Create a fresh ZIP containing only the rotating logs and generic metadata."""
        if not self._handler:
            self.start()
        if not self._handler:
            raise OSError("diagnostic log is unavailable")
        if destination is None:
            home = Path.home()
            folder = next((home / name for name in ("Desktop", "Downloads", "Documents")
                          if (home / name).is_dir()), home)
        else:
            folder = Path(destination)
        folder.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        path = folder / f"BongoDesk-diagnostics-{stamp}.zip"
        suffix = 1
        while path.exists():
            path = folder / f"BongoDesk-diagnostics-{stamp}-{suffix}.zip"
            suffix += 1
        metadata = {"format": 1, "created_local": stamp,
                    "contents": "bounded companion events; no settings or OAuth data"}
        handler = self._handler
        if handler:
            handler.acquire()
        try:
            if handler:
                handler.flush()
            with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("metadata.json", json.dumps(metadata, indent=2))
                for name in ["events.log"] + [f"events.log.{n}" for n in range(1, LOG_BACKUPS + 1)]:
                    source = self.log_dir / name
                    if source.is_file():
                        archive.write(source, f"logs/{name}")
        finally:
            if handler:
                handler.release()
        self.event("DIAGNOSTICS_EXPORTED", result="success")
        return path


diagnostics = Diagnostics()
