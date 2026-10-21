"""Compile current firmware media functions with call-counting LVGL adapters.

This checks real command/refresh/helper flow, not actual LVGL animation time,
heap allocations, SPI frame pacing or rendered pixels.
"""
import ctypes
from functools import lru_cache
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    match = re.search(r"(?:static\s+)?(?:void|String)\s+" + name + r"\([^)]*\)\s*\{", source)
    if not match:
        raise RuntimeError("Missing firmware function: " + name)
    end, depth = match.end(), 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[match.start():end]


@lru_cache(maxsize=1)
def load_host():
    compilers = sorted(Path("C:/Program Files/Microsoft Visual Studio").glob(
        "*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe"))
    if not compilers:
        raise RuntimeError("Existing MSVC compiler required for media label host")
    parent = ROOT / "build/product-committee-2026-10-20/label-idempotence"
    parent.mkdir(parents=True, exist_ok=True)
    build = Path(tempfile.mkdtemp(prefix="host-", dir=parent))
    source = (ROOT / "src/bongo_cat_featured.inc").read_text(encoding="utf-8")
    names = ("formatMediaTime", "setMediaLabelTextIfChanged", "refreshMediaProgressUi", "refreshMediaUi")
    fixture = "\n\n".join(function(source, name) for name in names)
    start = source.index('} else if (command.startsWith("MEDIA_SOURCE:")) {')
    end = source.index('} else if (command.startsWith("MEDIA_ART_RGB:")) {', start)
    # Exact current metadata branches, with only the outer first `else` removed.
    commands = source[start + len("} else "):end] + "}"
    fixture += "\nvoid applyMediaCommand(const String &command, unsigned int current_time) {\n" + commands + "\n}\n"
    (build / "media_label_fixture.inc").write_text(fixture, encoding="utf-8")
    compiler = compilers[-1]
    dll = build / "media_label.dll"
    command = [str(compiler), "/nologo", "/std:c++14", "/utf-8", "/O2", "/GS-", "/Gs9999999",
               "/GR-", "/Zl", "/LD", "/I" + str(build), str(ROOT / "tests/media_label_host.cpp"),
               "/Fo" + str(build / "media_label.obj"), "/link", "/NODEFAULTLIB", "/NOENTRY", "/OUT:" + str(dll)]
    env = dict(os.environ, PATH=str(compiler.parent) + os.pathsep + os.environ.get("PATH", ""))
    result = subprocess.run(command, cwd=build, env=env, capture_output=True, text=True)
    (build / "compile.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    lib = ctypes.CDLL(str(dll))
    lib.mt_apply.argtypes = [ctypes.c_char_p, ctypes.c_uint]
    lib.mt_text.argtypes = [ctypes.c_int]
    lib.mt_text.restype = ctypes.c_char_p
    lib.mt_writes.argtypes = [ctypes.c_int]
    lib.mt_mode.argtypes = [ctypes.c_int, ctypes.c_int]
    lib.mt_anchor.restype = ctypes.c_uint
    return lib
