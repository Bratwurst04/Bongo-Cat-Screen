"""Isolated verification/freeze for turntable firmware. Never opens a device."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sys
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/turntable-paw-2026-10-18'
CHANGED={'src/bongo_cat_featured.inc','tests/test_record_flip.py','tests/test_focus_countdown.py',
         '00_PROJECT_CONTEXT.md','01_CURRENT_STATE.md','02_DECISIONS.md'}
NEW={'src/media_turntable.h','tests/turntable_paw_host.cpp','tests/turntable_paw_host.py',
     'tests/test_turntable_paw.py','tools/turntable_paw_visuals.py','tools/turntable_paw_candidate.py'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()

def save(name,data):
    (BUILD/name).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')

def run_tests(focused):
    sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'companion')]
    import record_flip_host
    record_flip_host.BUILD=BUILD/('legacy-focused' if focused else 'legacy-regression')
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_turntable_paw.py' if focused else 'test_*.py')
    original_connect=socket.socket.connect;original_ex=socket.socket.connect_ex;original_lookup=socket.getaddrinfo
    blocked=[]
    def allow(host):
        if host not in ('localhost','127.0.0.1','::1',None):
            blocked.append('external_network_attempt');raise AssertionError('External network disabled')
    def connect(sock,address):
        if isinstance(address,tuple):allow(address[0])
        return original_connect(sock,address)
    def connect_ex(sock,address):
        if isinstance(address,tuple):allow(address[0])
        return original_ex(sock,address)
    def lookup(host,*args,**kwargs):
        allow(host);return original_lookup(host,*args,**kwargs)
    label='focused' if focused else 'regression';started=time.perf_counter()
    with (BUILD/(label+'-tests.log')).open('w',encoding='utf-8') as log:
        with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log),patch.object(socket.socket,'connect',connect),\
             patch.object(socket.socket,'connect_ex',connect_ex),patch.object(socket,'getaddrinfo',lookup):
            result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    data=dict(discovered=result.testsRun,passed=result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
              errors=len(result.errors),failures=len(result.failures),skipped=len(result.skipped),
              external_network_attempts=len(blocked),seconds=round(time.perf_counter()-started,3),
              skip_details=[dict(test=str(t),reason=reason) for t,reason in result.skipped])
    save(label+'-summary.json',data);print(json.dumps(data))
    return 0 if result.wasSuccessful() and not blocked else 1

def freeze():
    frozen=BUILD/'source-frozen';assert not frozen.exists(),'Do not replace frozen sources'
    names=set(json.loads((BUILD/'baseline-source.json').read_text()))|NEW
    manifest={}
    for name in sorted(names):
        target=frozen/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,target);manifest[name]=sha(ROOT/name)
    save('source-frozen.json',manifest)
    print(json.dumps(dict(frozen_sources=len(manifest),manifest_sha256=sha(BUILD/'source-frozen.json'))))

def verify():
    manifest=json.loads((BUILD/'source-frozen.json').read_text());compiled=0
    for n,h in manifest.items():
        assert sha(ROOT/n)==sha(BUILD/'source-frozen'/n)==h,n
        if n.endswith('.py'):compile((ROOT/n).read_bytes(),n,'exec');compiled+=1
    base=json.loads((BUILD/'baseline-source.json').read_text())
    changed={n for n,h in base.items() if sha(ROOT/n)!=h};assert changed==CHANGED,changed
    preserved=json.loads((BUILD/'preserved-before.json').read_text())
    for n,info in preserved.items():
        assert (ROOT/n).stat().st_size==info['bytes'] and sha(ROOT/n)==info['sha256'],n
    focused=json.loads((BUILD/'focused-summary.json').read_text());regression=json.loads((BUILD/'regression-summary.json').read_text())
    for result in (focused,regression):assert not result['failures'] and not result['errors'] and not result['external_network_attempts']
    # Every current preview input must match the actual final source.
    preview=json.loads((ROOT/'visuals/turntable-paw-2026-10-18'/args.preview/'manifest.json').read_text())
    for n,h in preview['source_sha256'].items():assert sha(ROOT/n)==h,n
    output=ROOT/'visuals/turntable-paw-2026-10-18'/args.preview
    for n,h in preview['output_sha256'].items():assert sha(output/n)==h,n
    reviewed=ROOT/'visuals/turntable-paw-2026-10-18/r4/manifest.json'
    assert sha(reviewed)=='CD817958DFD850CFD61D49D0369EB964F465056C9F65B08CCABC7E82B2723F83'
    binary=BUILD/'pio-build/esp32-024r-spotify-fastserial/firmware.bin'
    build_log=(BUILD/'firmware-build.log').read_text(encoding='utf-8-sig')
    ram=int(re.search(r'RAM:.*?used (\d+) bytes',build_log)[1])
    flash=int(re.search(r'Flash:.*?used (\d+) bytes',build_log)[1])
    image_info=(BUILD/'image-info-final.log').read_text(encoding='utf-8-sig')
    assert re.search(r'Checksum:.*\(valid\)',image_info)
    digest=sha(binary);candidate=ROOT/'.pio/candidates'/('turntable-paw-2026-10-18-'+digest[:8]+'.bin')
    if candidate.exists():assert sha(candidate)==digest
    else:shutil.copy2(binary,candidate)
    scope=dict(changed_existing=sorted(changed),new_sources=sorted(NEW),preserved_files=len(preserved),
               preservation_mismatches=[],companion_unchanged=True,firmware_profile='esp32-024r-spotify-fastserial',
               preview=str(output.relative_to(ROOT)),preview_manifest_sha256=sha(output/'manifest.json'),
               ui_review=dict(revision='r4',manifest_sha256=sha(reviewed),result='approved for V1 via Lead',
                 final_revision=args.preview,difference='C++ truncation toward zero for negative compositor offsets; up to1px; no pose/timing change'))
    save('scope-verification.json',scope)
    firmware=dict(path=str(candidate),sha256=digest,bytes=binary.stat().st_size,
                  elf_sha256=sha(binary.with_suffix('.elf')),flashed=False,
                  sources_each=len(manifest),compiled_python_sources=compiled,
                  profile='esp32-024r-spotify-fastserial',runtime_baud=230400,app_address='0x10000',
                  static_ram_bytes=ram,program_flash_bytes=flash,
                  state_bytes=preview['states']['paw-flip'][0]['frame'][15],projection_bytes_reused=112*112*2,
                  build_log_sha256=sha(BUILD/'firmware-build.log'),
                  image_info_sha256=sha(BUILD/'image-info-final.log'))
    save('firmware-verification.json',firmware)
    data=dict(status='built and isolated verified; not flashed; physical/UI runtime acceptance pending',
              firmware=firmware,focused=focused,regression=regression,**scope,
              installed_companion='687211432857B34424EDA3D203F645C7324C0639D2F2308367D185987BBB5A50',
              installed_firmware='55669C87CF8459996F173154691C6002B02D4DA193BAF13C3CBA801E18B40577',
              manifest_sha256={n:sha(BUILD/n) for n in ('source-frozen.json','scope-verification.json','firmware-verification.json')})
    save('candidate.json',data)
    print(json.dumps(dict(firmware=firmware,manifest_sha256={**data['manifest_sha256'],'candidate.json':sha(BUILD/'candidate.json')})))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['focused','regression','freeze','verify'])
    parser.add_argument('--preview',default='r5');args=parser.parse_args()
    if args.mode in ('focused','regression'):sys.exit(run_tests(args.mode=='focused'))
    elif args.mode=='freeze':freeze()
    else:verify()
