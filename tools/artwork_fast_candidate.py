"""Isolated experimental serial pair. Never starts EXE, COM, HTTP or user profile."""
import argparse
import contextlib
import hashlib
import json
import marshal
from pathlib import Path
import re
import shutil
import socket
import sys
import time
import unittest
from unittest.mock import patch

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/artwork-fast921600-2026-10-18'
DIST=ROOT/'dist/companion-2026-10-18-artwork-fast921600-dev'
NEW={'tools/artwork_fast_candidate.py','tests/test_artwork_fast.py','tests/artwork_fast_host.cpp','tests/artwork_fast_host.py'}
CHANGED={'src/bongo_cat_featured.inc','platformio.ini','companion/config.py','companion/engine.py','companion/gui.py',
    '00_PROJECT_CONTEXT.md','01_CURRENT_STATE.md','02_DECISIONS.md','README.md','companion/README.md'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'companion'),str(ROOT/'tools')]


def save(name,data):
    (BUILD/name).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')


def tests(focused):
    import record_flip_host,turntable_paw_host,test_focus_countdown
    record_flip_host.BUILD=BUILD/'legacy-host';turntable_paw_host.BUILD=BUILD/'turntable-host'
    test_focus_countdown.BUILD=BUILD/'focus-fixtures'
    loader=unittest.defaultTestLoader
    suite=(unittest.TestSuite([loader.discover(str(ROOT/'tests'),pattern=p) for p in
        ('test_artwork*.py','test_turntable*.py')]) if focused else loader.discover(str(ROOT/'tests'),pattern='test_*.py'))
    connect=socket.socket.connect;connect_ex=socket.socket.connect_ex;lookup=socket.getaddrinfo;blocked=[]
    def allow(host):
        if host not in ('localhost','127.0.0.1','::1',None):blocked.append('external');raise AssertionError('External network disabled')
    def guarded(sock,address):
        if isinstance(address,tuple):allow(address[0])
        return connect(sock,address)
    def guarded_ex(sock,address):
        if isinstance(address,tuple):allow(address[0])
        return connect_ex(sock,address)
    def guarded_lookup(host,*args,**kwargs):allow(host);return lookup(host,*args,**kwargs)
    label='focused' if focused else 'regression';started=time.perf_counter()
    with (BUILD/(label+'-tests.log')).open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log),\
         contextlib.redirect_stderr(log),patch.object(socket.socket,'connect',guarded),\
         patch.object(socket.socket,'connect_ex',guarded_ex),patch.object(socket,'getaddrinfo',guarded_lookup):
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    data=dict(discovered=result.testsRun,passed=result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
        errors=len(result.errors),failures=len(result.failures),skipped=len(result.skipped),external_network_attempts=len(blocked),
        seconds=round(time.perf_counter()-started,3),skip_details=[dict(test=str(t),reason=r) for t,r in result.skipped])
    import test_artwork_fast
    save(label+'-models.json',dict(classification='MODEL, NOT ESP32/CH340 benchmark',
        limits=test_artwork_fast.firmware_limits(),results=test_artwork_fast.MODEL_RESULTS,
        assumptions=['CPU parse 80us/line; specified render/blackout/flush cost; core0 framing keeps pace until queue backpressure.',
            'No OS scheduling, USB latency, measured TFT rate or physical UART-capacity guarantee inferred.']))
    save(label+'-summary.json',data);print(json.dumps(data))
    return 0 if result.wasSuccessful() and not blocked else 1


def freeze():
    import turntable_arm_tempo_candidate as prior
    prior.BUILD=BUILD;prior.NEW=NEW;prior.freeze()


def capture():
    folder=ROOT/'.pio/build/esp32-024r-spotify-artfast921600'
    for suffix in ('bin','elf'):shutil.copy2(folder/('firmware.'+suffix),BUILD/('firmware.'+suffix))
    print(json.dumps(dict(bytes=(BUILD/'firmware.bin').stat().st_size,sha256=sha(BUILD/'firmware.bin'))))


def verify():
    from PyInstaller.archive.readers import CArchiveReader
    from devices_diagnostics_candidate import normalize
    manifest=json.loads((BUILD/'source-frozen.json').read_text());compiled=0
    for name,digest in manifest.items():
        assert sha(ROOT/name)==sha(BUILD/'source-frozen'/name)==digest,name
        if name.endswith('.py'):compile((ROOT/name).read_bytes(),name,'exec');compiled+=1
    base=json.loads((BUILD/'baseline-source.json').read_text())
    changed={n for n,h in base.items() if sha(ROOT/n)!=h};assert changed==CHANGED,changed
    preserved=json.loads((BUILD/'preserved-before.json').read_text())
    for name,v in preserved.items():assert (ROOT/name).stat().st_size==v['bytes'] and sha(ROOT/name)==v['sha256'],name
    for label in ('focused','regression'):
        data=json.loads((BUILD/(label+'-summary.json')).read_text())
        assert not any(data[k] for k in ('errors','failures','external_network_attempts')),label
    exe=DIST/'BongoDeskSpotify.exe';archive=CArchiveReader(str(exe));pyz=archive.open_embedded_archive('PYZ.pyz')
    modules=['api_budget','config','diagnostics','engine','gui','media_bridge','media_commands','spotify_api','tray','windows_integration','main']
    for name in modules:
        expected=compile((ROOT/'companion'/(name+'.py')).read_bytes(),name+'.py','exec')
        actual=marshal.loads(archive.extract('main')) if name=='main' else pyz.extract(name)
        assert normalize(actual)==normalize(expected),name
    resources=['default_config.json','settings.ps1','settings-view.ps1','ui/bongo.png']
    names={n.replace('\\','/'):n for n in archive.toc}
    for n in resources:assert archive.extract(names[n])==(ROOT/'companion'/n).read_bytes(),n
    assert 'media_seek' not in pyz.toc
    binary=BUILD/'firmware.bin';digest=sha(binary)
    candidate=ROOT/'.pio/candidates'/('artwork-fast921600-2026-10-18-'+digest[:8]+'.bin')
    if candidate.exists():assert sha(candidate)==digest
    else:shutil.copy2(binary,candidate)
    log=(BUILD/'firmware-build.log').read_text(encoding='utf-8-sig');assert 'SUCCESS' in log
    info=(BUILD/'image-info.log').read_text(encoding='utf-8-sig');assert re.search(r'Checksum:.*\(valid\)',info)
    package=dict(path=str(exe),bytes=exe.stat().st_size,sha256=sha(exe),modules=modules,resources=resources,started=False)
    firmware=dict(path=str(candidate),bytes=binary.stat().st_size,sha256=digest,elf_sha256=sha(BUILD/'firmware.elf'),
        profile='esp32-024r-spotify-artfast921600',runtime_baud=921600,flash_baud=115200,app_address='0x10000',flashed=False,
        ram_bytes=int(re.search(r'RAM:.*?used (\d+) bytes',log)[1]),program_bytes=int(re.search(r'Flash:.*?used (\d+) bytes',log)[1]))
    save('package-verification.json',package)
    scope=dict(changed=sorted(changed),new_sources=sorted(NEW),preserved_files=len(preserved),mismatches=[],
        source_count=len(manifest),compiled_python=compiled,installed_pair='68721143/627E6B93',
        profile_untouched=True,default_baud_230400_untouched=True,wire_codec_unchanged=True)
    save('scope-verification.json',scope)
    data=dict(status='built and isolated tested; not installed/flashed; one-second target and CH340921600 physically pending',
        firmware=firmware,companion=package,scope=scope,
        tests={n:json.loads((BUILD/(n+'-summary.json')).read_text()) for n in ('focused','regression')},
        manifest_sha256={n:sha(BUILD/n) for n in ('source-frozen.json','package-verification.json','scope-verification.json')})
    save('candidate.json',data)
    print(json.dumps(dict(firmware=firmware,companion=package,scope=scope,
        manifest_sha256={**data['manifest_sha256'],'candidate.json':sha(BUILD/'candidate.json')})))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['focused','regression','freeze','capture','verify']);args=parser.parse_args()
    if args.mode in ('focused','regression'):sys.exit(tests(args.mode=='focused'))
    elif args.mode=='freeze':freeze()
    elif args.mode=='capture':capture()
    else:verify()
