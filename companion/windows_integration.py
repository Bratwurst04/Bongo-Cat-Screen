"""Small Windows integrations used by BongoDesk.

No background service or scheduled task is installed.  Autostart is a single
per-user Run entry and foreground-app detection is a lightweight Win32 query.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from pathlib import Path

import psutil


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "BongoDeskSpotify"
MUTEX_NAME = "Local\\BongoDeskSpotify.SingleInstance.V7"
ERROR_ALREADY_EXISTS = 183


def _startup_command() -> str:
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        return subprocess.list2cmdline([str(executable), "--startup"])
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = pythonw if pythonw.exists() else Path(sys.executable)
    script = Path(__file__).with_name("main.py").resolve()
    return subprocess.list2cmdline([str(executable), str(script), "--startup"])


def set_start_with_windows(enabled: bool) -> None:
    if os.name != "nt":
        return
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, _startup_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass


class SingleInstanceLock:
    def __init__(self) -> None:
        self._handle = None

    def acquire(self) -> bool:
        if os.name != "nt":
            return True
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        self._handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        return bool(self._handle) and kernel32.GetLastError() != ERROR_ALREADY_EXISTS

    def close(self) -> None:
        if self._handle and os.name == "nt":
            ctypes.windll.kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None


def get_foreground_app() -> tuple[str, str]:
    """Return the foreground process name and window title."""
    if os.name != "nt":
        return "", ""
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "", ""
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        process_name = psutil.Process(pid.value).name().lower()
    except (psutil.Error, OSError):
        process_name = ""
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return process_name, buffer.value.lower()
