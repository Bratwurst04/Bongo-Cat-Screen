"""Execute the actual compact parser, CRC, slot activation and in-place expand."""
import ctypes
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/artwork-compact80-2026-10-18'
Pixels=ctypes.c_ushort*(112*112)


def load_host(compact=True):
    # Other native adapters select their own output directory. A cached DLL
    # from a previous directory cannot provide that directory's fixture files.
    return _load_host(compact, str(BUILD.resolve()))


@lru_cache(maxsize=8)
def _load_host(compact, build_directory):
    folder=Path(build_directory)/('compact-host' if compact else 'legacy-host');folder.mkdir(parents=True,exist_ok=True)
    header=(ROOT/'src/media_art_v2.h').read_text(encoding='utf-8')
    types=re.sub(r'^#(?:include[^\n]*|pragma once)\n','',header,flags=re.M)
    color=(ROOT/'tests/fixtures/lvgl8311-color16.inc').read_bytes()
    assert hashlib.sha256(color).hexdigest().upper()=='B3B96C036E3238ED6A11040703150C5414E993026EE149C28F68960C2905C5A1'
    types+='\n'+color.decode('utf-8')
    (folder/'compact_types_fixture.inc').write_text(types,encoding='utf-8')
    source=(ROOT/'src/bongo_cat_featured.inc').read_text(encoding='utf-8');bodies=[]
    for name in ('parseMediaArt2Number','failMediaArt2','syncMediaArtworkDescriptor','setMediaArtRefinementGeneration',
                 'serviceMediaArtShown','activateMediaArtwork','updateMediaTrackContext','handleMediaArt2Command'):
        match=re.search(r'(?:bool|void) '+name+r'\([^)]*\)\s*\{.*?\n\}',source,re.S)
        if not match:raise RuntimeError('Actual production body missing: '+name)
        bodies.append(match[0])
    (folder/'compact_parser_fixture.inc').write_text('\n'.join(bodies),encoding='utf-8')
    compiler=sorted(Path('C:/Program Files/Microsoft Visual Studio').glob('*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe'))[-1]
    dll=folder/'compact_art.dll'
    command=[str(compiler),'/nologo','/std:c++14','/O2','/GS-','/GR-','/Zl','/LD','/I'+str(folder)]
    if compact:command+=['/DBONGO_ART2_COMPACT80=1']
    command+=[str(ROOT/'tests/compact_art_host.cpp'),'/Fo'+str(folder/'compact_art.obj'),
        '/link','/NODEFAULTLIB','/NOENTRY','/OUT:'+str(dll)]
    env=dict(os.environ,PATH=str(compiler.parent)+os.pathsep+os.environ.get('PATH',''))
    result=subprocess.run(command,cwd=folder,env=env,capture_output=True,text=True)
    (folder/'compile.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    h=ctypes.CDLL(str(dll));words=ctypes.POINTER(ctypes.c_ushort)
    h.ca_line.argtypes=[ctypes.c_char_p,ctypes.c_uint];h.ca_snapshot.argtypes=[ctypes.c_uint,words]
    h.ca_context.argtypes=[ctypes.c_uint,ctypes.c_uint]
    h.ca_expand.argtypes=[words,ctypes.c_uint];h.ca_color.argtypes=[ctypes.c_uint]*3
    h.ca_legacy_pixels.argtypes=[ctypes.c_char_p,words];h.ca_reason.restype=ctypes.c_char_p
    h.ca_descriptor.argtypes=[ctypes.POINTER(ctypes.c_int)]
    return h


def snapshot(host,slot=None):
    out=Pixels();host.ca_snapshot(host.ca_active() if slot is None else slot,out);return out
