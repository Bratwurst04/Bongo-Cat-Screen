"""Compile actual pure turntable helper + selected firmware bodies, no SDK repair."""
import ctypes
from functools import lru_cache
import os
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/turntable-arm-tempo-2026-10-18/host'
Frame=ctypes.c_int*16
Pixels=ctypes.c_ushort*(112*112)
TIMING_KEYS=('frame_ms','clear_end','reach_end','grip_end','lift_end','flip_end','full_out_end',
             'full_in_end','lower_end','full_lower_end','settle_end','full_settle_end',
             'withdraw_end','full_withdraw_end','normal_ms','full_ms','reveal_ms','lift_pixels')

def timings(host):
    values=(ctypes.c_int*len(TIMING_KEYS))();host.tt_times(values)
    return dict(zip(TIMING_KEYS,values))

@lru_cache(maxsize=1)
def load_host():
    compilers=sorted(Path('C:/Program Files/Microsoft Visual Studio').glob('*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe'))
    if not compilers:raise RuntimeError('Existing freestanding MSVC compiler unavailable')
    BUILD.mkdir(parents=True,exist_ok=True)
    source=(ROOT/'src/bongo_cat_featured.inc').read_text(encoding='utf-8');bodies=[]
    for name in ('syncMediaArtworkDescriptor','activateMediaArtwork','loadGenericVinyl','allocateMediaRecordPixels','updateMediaTrackContext'):
        match=re.search(r'void '+name+r'\([^)]*\)\s*\{.*?\n\}',source,re.S)
        if not match:raise RuntimeError('Actual firmware body missing: '+name)
        bodies.append(match[0])
    begin=re.search(r'media_art_v2.begin\([^;]+;\s*(media_art_receiving_buffer = [^;]+;)',source)
    if not begin:raise RuntimeError('Actual BEGIN slot selection missing')
    bodies.append('void fwBeginFromSource(){'+begin[1]+'}')
    (BUILD/'turntable_firmware_fixture.inc').write_text('\n'.join(bodies),encoding='utf-8')
    compiler=compilers[-1];dll=BUILD/'turntable_paw.dll'
    command=[str(compiler),'/nologo','/std:c++14','/O2','/GS-','/GR-','/Zl','/LD','/I'+str(BUILD),
             str(ROOT/'tests/turntable_paw_host.cpp'),'/Fo'+str(BUILD/'turntable_paw.obj'),
             '/link','/NODEFAULTLIB','/NOENTRY','/OUT:'+str(dll)]
    env=dict(os.environ,PATH=str(compiler.parent)+os.pathsep+os.environ.get('PATH',''))
    result=subprocess.run(command,cwd=BUILD,env=env,capture_output=True,text=True)
    (BUILD/'compile.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    lib=ctypes.CDLL(str(dll));ptr=ctypes.POINTER(ctypes.c_int);words=ctypes.POINTER(ctypes.c_ushort)
    lib.tt_times.argtypes=[ptr]
    lib.tt_event.argtypes=[ctypes.c_int,ctypes.c_uint,ctypes.c_uint,ctypes.c_int]
    lib.tt_playback.argtypes=[ctypes.c_int,ctypes.c_uint,ctypes.c_uint]
    lib.tt_frame.argtypes=[ctypes.c_uint,ctypes.c_int,ptr]
    lib.tt_render.argtypes=[words,ctypes.c_uint,words,ptr,ctypes.c_int,ctypes.c_int,words]
    lib.tt_reduced.argtypes=[words,ctypes.c_uint,words]
    lib.tt_geometry.argtypes=[ptr,ctypes.c_int,ptr]
    lib.tt_primitives.argtypes=[ptr,ctypes.c_int,ctypes.c_int,ptr,words]
    lib.tt_fw_context.argtypes=[ctypes.c_uint,ctypes.c_uint]
    lib.tt_fw_art.argtypes=[ctypes.c_uint]
    lib.tt_fw_frame.argtypes=[ctypes.c_uint,ptr]
    lib.tt_fw_draw.argtypes=[words,ctypes.c_uint]
    return lib
