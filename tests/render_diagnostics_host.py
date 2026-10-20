"""Run the actual pure timing accumulator with existing freestanding MSVC."""
import ctypes
from functools import lru_cache
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def load_host():
    compilers = sorted(Path("C:/Program Files/Microsoft Visual Studio").glob(
        "*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe"))
    if not compilers:
        raise RuntimeError("Existing MSVC required for render diagnostics host")
    parent = ROOT / "build/product-committee-2026-10-20/render-timing-host"
    parent.mkdir(parents=True, exist_ok=True)
    build = Path(tempfile.mkdtemp(prefix="host-", dir=parent))
    source = (ROOT / "src/render_diagnostics.h").read_text(encoding="utf-8")
    (build / "render_diagnostics_fixture.inc").write_text("\n".join(
        line for line in source.splitlines() if not line.startswith(("#include", "#pragma"))), encoding="utf-8")
    compiler = compilers[-1]
    dll = build / "render_diagnostics.dll"
    command = [str(compiler), "/nologo", "/std:c++14", "/O2", "/GS-", "/GR-", "/Zl", "/LD",
               "/I" + str(build), str(ROOT / "tests/render_diagnostics_host.cpp"),
               "/Fo" + str(build / "render_diagnostics.obj"), "/link", "/NODEFAULTLIB", "/NOENTRY", "/OUT:" + str(dll)]
    result = subprocess.run(command, cwd=build, capture_output=True, text=True,
                            env=dict(os.environ, PATH=str(compiler.parent) + os.pathsep + os.environ.get("PATH", "")))
    (build / "compile.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    lib = ctypes.CDLL(str(dll))
    lib.rd_begin.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_int]
    lib.rd_end.argtypes = [ctypes.c_uint]
    lib.rd_flush.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_int, ctypes.c_int]
    lib.rd_value.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lib.rd_value.restype = ctypes.c_uint
    lib.rd_due.argtypes = [ctypes.c_uint]
    return lib
