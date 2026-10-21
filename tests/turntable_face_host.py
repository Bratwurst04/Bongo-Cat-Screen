"""Current production parser + actual event bodies + two-slot native renderer."""
import base64
import ctypes
from functools import lru_cache
import os
from pathlib import Path
import re
import subprocess
import zlib
import compact_art_host

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/turntable-face-2026-10-18/native'
Frame=ctypes.c_int*16
Pixels=compact_art_host.Pixels

def body(source,name):
    match=re.search(r'(?:void|bool) '+name+r'\([^)]*\)\s*\{.*?\n\}',source,re.S)
    if not match:raise RuntimeError('Missing production body '+name)
    return match[0]

def block(source,marker):
    start=source.index('{',source.index(marker));end=start+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start+1:end-1]

@lru_cache(maxsize=2)
def load_host(compact=True):
    compact_art_host.BUILD=BUILD/'parser'
    (compact_art_host.load_host() if compact else compact_art_host.load_host(False))
    folder=compact_art_host.BUILD/('compact-host' if compact else 'legacy-host')
    source=(ROOT/'src/bongo_cat_featured.inc').read_text(encoding='utf-8')
    raw=source[source.index('media_art_v2.abort();',source.index('} else if (command.startsWith("MEDIA_ART_RGB:"')):]
    raw=raw[:raw.index('media_art_receiving = true;')+len('media_art_receiving = true;')].replace('incoming_size','MEDIA_ART_RGB_BYTES').replace('current_time','millis()')
    default=block(source,'} else if (command == "MEDIA_ART_DEFAULT")').replace('current_time','millis()')
    none=block(source,'if (state == "NONE")')
    extra=[body(source,n) for n in ('loadGenericVinyl','finishMediaArtwork','consumeQueuedMediaArtwork')]
    extra+=['void fwRawBeginFromSource(){'+raw+'}', 'void fwDefaultFromSource(){'+default+'}', 'void fwNoneFromSource(){'+none+'}']
    (folder/'face_events_fixture.inc').write_text('\n'.join(extra),encoding='utf-8')
    compiler=sorted(Path('C:/Program Files/Microsoft Visual Studio').glob('*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe'))[-1]
    dll=folder/'turntable_face.dll'
    command=[str(compiler),'/nologo','/std:c++14','/O2','/GS-','/GR-','/Zl','/LD','/I'+str(folder)]
    if compact:command+=['/DBONGO_ART2_COMPACT80=1']
    command+=[str(ROOT/'tests/turntable_face_host.cpp'),'/Fo'+str(folder/'turntable_face.obj'),'/link','/NODEFAULTLIB','/NOENTRY','/OUT:'+str(dll)]
    env=dict(os.environ,PATH=str(compiler.parent)+os.pathsep+os.environ.get('PATH',''))
    result=subprocess.run(command,cwd=folder,env=env,capture_output=True,text=True)
    (folder/'face-compile.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    h=ctypes.CDLL(str(dll));words=ctypes.POINTER(ctypes.c_ushort);ints=ctypes.POINTER(ctypes.c_int)
    h.ca_line.argtypes=[ctypes.c_char_p,ctypes.c_uint];h.ca_context.argtypes=[ctypes.c_uint,ctypes.c_uint]
    h.ca_snapshot.argtypes=[ctypes.c_uint,words];h.ca_descriptor.argtypes=[ints]
    h.ca_reason.restype=ctypes.c_char_p
    h.ff_frame.argtypes=[ctypes.c_uint,ctypes.c_int,ints];h.ff_play.argtypes=[ctypes.c_int,ctypes.c_uint,ctypes.c_uint]
    h.ff_raw.argtypes=[ctypes.c_char_p,ctypes.c_uint]
    h.ff_generation.argtypes=[ctypes.c_char_p];h.ff_shown_challenge.restype=ctypes.c_char_p
    h.tt_render.argtypes=[words,ctypes.c_uint,words,ints,ctypes.c_int,ctypes.c_int,words]
    h.tt_geometry.argtypes=[ints,ctypes.c_int,ints];h.tt_primitives.argtypes=[ints,ctypes.c_int,ctypes.c_int,ints,words]
    return h

def transfer(h,rgb,identity,now,compact=True,finish=True,crc_delta=0):
    from artwork_codec import pack_compact_rgb565
    payload=pack_compact_rgb565(rgb) if compact else rgb
    crc=(zlib.crc32(payload)^crc_delta)&0xffffffff
    kind='BEGIN565' if compact else 'BEGIN';edge=80 if compact else 112
    h.ca_line(f'MEDIA_ART2_{kind}:{identity}:{edge}:{edge}:{len(payload)}:{crc:08X}'.encode(),now)
    for offset in range(0,len(payload),128):
        h.ca_line(f'MEDIA_ART2_CHUNK:{identity}:{offset}:'.encode()+base64.b64encode(payload[offset:offset+128]),now)
    if finish:h.ca_line(f'MEDIA_ART2_END:{identity}'.encode(),now)
    return payload

def frame(h,now,visible=True):
    f=Frame();h.ff_frame(now,visible,f);return f

def snapshot(h,slot=None):
    return compact_art_host.snapshot(h,slot)
