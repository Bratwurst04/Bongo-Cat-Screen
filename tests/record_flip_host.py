"""Execute the actual integer helper with existing MSVC, no CRT/SDK repair."""
import ctypes
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/record-flip-2026-10-15/host'


@lru_cache(maxsize=1)
def load_host():
    compilers = sorted(Path('C:/Program Files/Microsoft Visual Studio').glob(
        '*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe'))
    if not compilers:
        raise RuntimeError('No existing freestanding MSVC compiler; helper not executed')
    BUILD.mkdir(parents=True, exist_ok=True)
    # Compile the actual unchanged firmware byte framer without SDK headers;
    # only its standard integer typedefs are supplied by this fixture.
    header = (ROOT / 'src/serial_line_receiver.h').read_text(encoding='utf-8')
    (BUILD / 'serial_receiver_fixture.inc').write_text('\n'.join(
        line for line in header.splitlines() if not line.startswith(('#include', '#pragma'))), encoding='utf-8')
    context_header = (ROOT / 'src/media_track_context.h').read_text(encoding='utf-8')
    (BUILD / 'track_context_fixture.inc').write_text('\n'.join(
        line for line in context_header.splitlines() if not line.startswith(('#include', '#pragma'))), encoding='utf-8')
    # Small historical C3 blocks, not a second firmware implementation.
    # Current two-slot staging/CRC/visibility still uses turntable_face_host.
    fixture=(ROOT/'tests/fixtures/record-c3-legacy.inc').read_bytes()
    assert hashlib.sha256(fixture).hexdigest().upper()=='210508FA44A05BD18CBA2D2B96FE4B8DF991D7781396AB435C21591CE8894DE3'
    (BUILD / 'record_firmware_fixture.inc').write_bytes(fixture)
    compiler = compilers[-1]
    dll = BUILD / 'record_flip.dll'
    command = [str(compiler), '/nologo', '/std:c++14', '/O2', '/GS-', '/GR-', '/Zl', '/LD', '/I' + str(BUILD),
               str(ROOT / 'tests/record_flip_host.cpp'), '/Fo' + str(BUILD / 'record_flip.obj'),
               '/link', '/NODEFAULTLIB', '/NOENTRY', '/OUT:' + str(dll)]
    env = dict(os.environ, PATH=str(compiler.parent) + os.pathsep + os.environ.get('PATH', ''))
    result = subprocess.run(command, cwd=BUILD, env=env, capture_output=True, text=True)
    (BUILD / 'compile.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    lib = ctypes.CDLL(str(dll))
    lib.rf_reset.argtypes = []
    lib.rf_event.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_int]
    lib.rf_frame.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
    lib.rf_render.argtypes = [ctypes.POINTER(ctypes.c_ushort), ctypes.POINTER(ctypes.c_ushort),
                             ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             ctypes.POINTER(ctypes.c_ushort)]
    lib.rf_serial_push.argtypes = [ctypes.c_ubyte, ctypes.c_uint]
    lib.rf_serial_line.restype = ctypes.c_char_p
    lib.rf_reduced.argtypes = [ctypes.POINTER(ctypes.c_ushort), ctypes.c_uint,
                              ctypes.POINTER(ctypes.c_ushort)]
    lib.rf_fw_draw.argtypes = [ctypes.POINTER(ctypes.c_ushort), ctypes.c_uint]
    lib.rf_fw_frame.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_int)]
    lib.rf_fw_track_context.argtypes = [ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint]
    lib.rf_touch.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lib.rf_taps.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
    return lib
