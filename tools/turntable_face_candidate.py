"""Isolated face-staging tests/build evidence; never starts runtime or flashes."""
import argparse
import contextlib
import hashlib
import json
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
BUILD=ROOT/'build/turntable-face-2026-10-18'
NEW={'tests/turntable_face_host.cpp','tests/turntable_face_host.py','tests/test_turntable_face.py',
     'tools/turntable_face_candidate.py','tools/turntable_face_visuals.py'}
CHANGED={'src/media_turntable.h','src/bongo_cat_featured.inc','00_PROJECT_CONTEXT.md','01_CURRENT_STATE.md','02_DECISIONS.md',
         'tests/compact_art_host.py','tests/turntable_paw_host.py','tests/test_turntable_paw.py',
         'tests/record_flip_host.py','tests/test_record_flip.py'}
CHANGED.add('tests/test_turntable_arm_tempo.py')
APP=ROOT/'dist/companion-2026-10-18-capability-startup-dev/BongoDeskSpotify.exe'
APP_SHA='FD9D811B0356818A56AA0787AD3041820DA8D45D6083D8E0E822D3B59426DB06'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools'),str(ROOT/'companion')]
def save(name,data):(BUILD/name).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')

def tests():
    import compact_art_host,artwork_fast_host,record_flip_host,turntable_paw_host,test_focus_countdown
    compact_art_host.BUILD=BUILD/'transport';artwork_fast_host.BUILD=BUILD/'queue-host'
    record_flip_host.BUILD=BUILD/'legacy-host';turntable_paw_host.BUILD=BUILD/'turntable-host'
    test_focus_countdown.BUILD=BUILD/'focus-fixtures'
    patterns=('test_turntable*.py','test_record_flip.py','test_artwork*.py','test_power_resume.py',
              'test_lifecycle.py','test_focus_countdown.py','test_media_text_utf8.py','test_capability_startup.py')
    loader=unittest.defaultTestLoader;suite=unittest.TestSuite([loader.discover(str(ROOT/'tests'),pattern=p) for p in patterns])
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
    started=time.perf_counter()
    with (BUILD/'tests.log').open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log),\
         patch.object(socket.socket,'connect',guarded),patch.object(socket.socket,'connect_ex',guarded_ex),patch.object(socket,'getaddrinfo',guarded_lookup):
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    data=dict(discovered=result.testsRun,passed=result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
        errors=len(result.errors),failures=len(result.failures),skipped=len(result.skipped),external_network_attempts=len(blocked),
        seconds=round(time.perf_counter()-started,3),patterns=patterns,
        skip_details=[dict(test=str(t),reason=r) for t,r in result.skipped])
    save('tests-summary.json',data);print(json.dumps(data));return 0 if result.wasSuccessful() and not blocked else 1

def capture():
    folder=BUILD/'pio-build/esp32-024r-spotify-compact80'
    for suffix in ('bin','elf'):shutil.copy2(folder/('firmware.'+suffix),BUILD/('firmware.'+suffix))
    binary=BUILD/'firmware.bin';h=sha(binary);candidate=ROOT/'.pio/candidates'/('turntable-face-2026-10-18-'+h[:8]+'.bin')
    assert not candidate.exists(),'Preserve prior candidates';shutil.copy2(binary,candidate)
    save('firmware-verification.json',dict(path=str(candidate),bytes=binary.stat().st_size,sha256=h,
        elf_sha256=sha(BUILD/'firmware.elf'),profile='esp32-024r-spotify-compact80',flashed=False))
    print((BUILD/'firmware-verification.json').read_text())

def freeze():
    import turntable_arm_tempo_candidate as prior
    prior.BUILD=BUILD;prior.NEW=NEW;prior.freeze()

def verify():
    sources=json.loads((BUILD/'source-frozen.json').read_text());compiled=0
    for n,h in sources.items():
        assert sha(ROOT/n)==sha(BUILD/'source-frozen'/n)==h,n
        if n.endswith('.py'):compile((ROOT/n).read_bytes(),n,'exec');compiled+=1
    base=json.loads((BUILD/'baseline-source.json').read_text())
    changed={n for n,h in base.items() if sha(ROOT/n)!=h};assert changed==CHANGED,changed
    preserved=json.loads((BUILD/'preserved-before.json').read_text())
    for n,v in preserved.items():assert (ROOT/n).stat().st_size==v['bytes'] and sha(ROOT/n)==v['sha256'],n
    assert sha(APP)==APP_SHA
    tests=json.loads((BUILD/'tests-summary.json').read_text());assert not any(tests[k] for k in ('errors','failures','external_network_attempts'))
    assert tests['skipped']==2 and all('complete MSVC setup/headers unavailable' in s['reason'] for s in tests['skip_details'])
    folder=ROOT/'visuals/turntable-face-2026-10-18/r1';preview=json.loads((folder/'manifest.json').read_text())
    for n,h in preview['source_sha256'].items():assert sha(ROOT/n)==h,n
    for n,h in preview['output_sha256'].items():assert sha(folder/n)==h,n
    review=json.loads((BUILD/'ui-review.json').read_text());assert review['preview_manifest_sha256']==sha(folder/'manifest.json')
    firmware=json.loads((BUILD/'firmware-verification.json').read_text());assert sha(Path(firmware['path']))==firmware['sha256']
    assert sha(BUILD/'firmware.bin')==firmware['sha256'] and sha(BUILD/'firmware.elf')==firmware['elf_sha256']
    image_info=(BUILD/'image-info.log').read_text(encoding='utf-8-sig')
    assert re.search(r'Checksum:.*\(valid\)',image_info) and re.search(r'Validation Hash:.*\(valid\)',image_info)
    log=(BUILD/'firmware-build.log').read_text(encoding='utf-8-sig');assert 'SUCCESS' in log
    firmware.update(ram_bytes=int(re.search(r'RAM:.*?used (\d+) bytes',log)[1]),program_bytes=int(re.search(r'Flash:.*?used (\d+) bytes',log)[1]))
    scope=dict(changed=sorted(changed),new_sources=sorted(NEW),source_count=len(sources),compiled_python=compiled,
        preserved_files=len(preserved),mismatches=[],companion_sha256=APP_SHA,companion_rebuilt=False,
        installed_pair='FD9D811B/C6EBAE4B',preview_manifest_sha256=sha(folder/'manifest.json'),review=review)
    save('scope-verification.json',scope)
    data=dict(status='firmware built, not flashed; physical face transition pending',firmware=firmware,scope=scope,tests=tests,
        manifest_sha256={n:sha(BUILD/n) for n in ('source-frozen.json','firmware-verification.json','scope-verification.json')})
    save('candidate.json',data);print(json.dumps({**data,'candidate_manifest_sha256':sha(BUILD/'candidate.json')}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['test','capture','freeze','verify']);mode=parser.parse_args().mode
    if mode=='test':sys.exit(tests())
    elif mode=='capture':capture()
    elif mode=='freeze':freeze()
    else:verify()
