"""Isolated progressive artwork evidence; no runtime, port, API or flash."""
import argparse
import ast
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
BUILD=ROOT/'build/artwork-refinement-2026-10-19'
DIST=ROOT/'dist/companion-2026-10-19-artwork-refinement-dev'
NEW={'src/media_art_refinement.h','tests/test_artwork_refinement.py',
     'tools/artwork_refinement_candidate.py','tools/artwork_refinement_visuals.py'}
CHANGED={'companion/engine.py','src/bongo_cat_featured.inc','00_PROJECT_CONTEXT.md','01_CURRENT_STATE.md','02_DECISIONS.md',
    'companion/artwork_codec.py',
    'tests/compact_art_host.py','tests/compact_art_host.cpp','tests/turntable_paw_host.cpp',
    'tests/turntable_face_host.cpp','tests/turntable_face_host.py','tests/test_capability_startup.py'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools'),str(ROOT/'companion')]
def save(name,data):(BUILD/name).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')

def tests(focused):
    import compact_art_host,turntable_face_host,artwork_fast_host,record_flip_host,turntable_paw_host,test_focus_countdown
    compact_art_host.BUILD=BUILD/'native/parser';turntable_face_host.BUILD=BUILD/'native'
    artwork_fast_host.BUILD=BUILD/'queue-host';record_flip_host.BUILD=BUILD/'legacy-host'
    turntable_paw_host.BUILD=BUILD/'turntable-host';test_focus_countdown.BUILD=BUILD/'focus-fixtures'
    patterns=(('test_artwork_refinement.py',) if focused else
        ('test_turntable*.py','test_record_flip.py','test_artwork*.py','test_power_resume.py',
         'test_lifecycle.py','test_focus_countdown.py','test_media_text_utf8.py','test_capability_startup.py'))
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
    label='focused' if focused else 'tests';started=time.perf_counter()
    with (BUILD/(label+'.log')).open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log),\
         patch.object(socket.socket,'connect',guarded),patch.object(socket.socket,'connect_ex',guarded_ex),patch.object(socket,'getaddrinfo',guarded_lookup):
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    data=dict(discovered=result.testsRun,passed=result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
        errors=len(result.errors),failures=len(result.failures),skipped=len(result.skipped),external_network_attempts=len(blocked),
        seconds=round(time.perf_counter()-started,3),patterns=patterns,skip_details=[dict(test=str(t),reason=r) for t,r in result.skipped])
    save(label+'-summary.json',data);print(json.dumps(data));return 0 if result.wasSuccessful() and not blocked else 1

def capture():
    folder=BUILD/'pio-build/esp32-024r-spotify-compact80'
    for suffix in ('bin','elf'):shutil.copy2(folder/('firmware.'+suffix),BUILD/('firmware.'+suffix))
    binary=BUILD/'firmware.bin';h=sha(binary);candidate=ROOT/'.pio/candidates'/('artwork-refinement-2026-10-19-'+h[:8]+'.bin')
    assert not candidate.exists(),'Preserve previous candidates';shutil.copy2(binary,candidate)
    save('firmware-verification.json',dict(path=str(candidate),bytes=binary.stat().st_size,sha256=h,
        elf_sha256=sha(BUILD/'firmware.elf'),profile='esp32-024r-spotify-compact80',flashed=False))
    print((BUILD/'firmware-verification.json').read_text())

def freeze():
    import turntable_arm_tempo_candidate as prior
    prior.BUILD=BUILD;prior.NEW=NEW;prior.freeze()

def methods(path):
    tree=ast.parse(path.read_bytes());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='BongoCatEngine')
    return {n.name:ast.dump(n,include_attributes=False) for n in cls.body if isinstance(n,ast.FunctionDef)}

def verify():
    from PyInstaller.archive.readers import CArchiveReader
    from devices_diagnostics_candidate import normalize
    sources=json.loads((BUILD/'source-frozen.json').read_text());compiled=0
    for n,h in sources.items():
        assert sha(ROOT/n)==sha(BUILD/'source-frozen'/n)==h,n
        if n.endswith('.py'):compile((ROOT/n).read_bytes(),n,'exec');compiled+=1
    base=json.loads((BUILD/'baseline-source.json').read_text());changed={n for n,h in base.items() if sha(ROOT/n)!=h}
    assert changed==CHANGED,changed
    old=methods(ROOT/'build/turntable-face-2026-10-18/source-frozen/companion/engine.py');now=methods(ROOT/'companion/engine.py')
    allowed={'__init__','send_initial_sync','_send_media_update_locked','_send_artwork_v2','_artwork_sender_loop',
        '_serial_reader_loop','_retry_capability_after_status','stop_monitoring'}
    assert set(now)-set(old)=={'_artwork_refinement_current','_record_artwork_shown','_take_artwork_refinement'}
    assert all(now[n]==body for n,body in old.items() if n not in allowed)
    preserved=json.loads((BUILD/'preserved-before.json').read_text())
    for n,v in preserved.items():assert (ROOT/n).stat().st_size==v['bytes'] and sha(ROOT/n)==v['sha256'],n
    for revision in ('r1','r2','r3'):
        prior_folder=ROOT/'visuals/artwork-refinement-2026-10-19'/revision
        prior=json.loads((prior_folder/'manifest.json').read_text())
        for n,h in prior['source_sha256'].items():assert sha(BUILD/('preview-'+revision+'-source-frozen')/n)==h,n
        for n,h in prior['output_sha256'].items():assert sha(prior_folder/n)==h,n
    for file,metadata in [('pre-mask-companion.exe','pre-mask-intermediate.json'),
                          ('pre-key-mask-companion.exe','pre-key-mask-intermediate.json')]:
        saved=json.loads((BUILD/metadata).read_text());assert sha(BUILD/file)==saved['app_sha256']
    results={n:json.loads((BUILD/(n+'-summary.json')).read_text()) for n in ('focused','tests')}
    for data in results.values():assert not any(data[k] for k in ('errors','failures','external_network_attempts'))
    assert results['tests']['skipped']==2 and all('complete MSVC setup/headers unavailable' in s['reason'] for s in results['tests']['skip_details'])
    folder=ROOT/'visuals/artwork-refinement-2026-10-19/r4';preview=json.loads((folder/'manifest.json').read_text())
    for n,h in preview['source_sha256'].items():assert sha(ROOT/n)==h,n
    for n,h in preview['output_sha256'].items():assert sha(folder/n)==h,n
    review=json.loads((BUILD/'ui-review.json').read_text());assert review['preview_manifest_sha256']==sha(folder/'manifest.json')
    firmware=json.loads((BUILD/'firmware-verification.json').read_text())
    assert sha(Path(firmware['path']))==sha(BUILD/'firmware.bin')==firmware['sha256']
    assert sha(BUILD/'firmware.elf')==firmware['elf_sha256']
    info=(BUILD/'image-info.log').read_text(encoding='utf-8-sig')
    assert re.search(r'Checksum:.*\(valid\)',info) and re.search(r'Validation Hash:.*\(valid\)',info)
    log=(BUILD/'firmware-build.log').read_text(encoding='utf-8-sig');assert 'SUCCESS' in log
    firmware.update(ram_bytes=int(re.search(r'RAM:.*?used (\d+) bytes',log)[1]),program_bytes=int(re.search(r'Flash:.*?used (\d+) bytes',log)[1]))
    exe=DIST/'BongoDeskSpotify.exe';archive=CArchiveReader(str(exe));pyz=archive.open_embedded_archive('PYZ.pyz')
    modules=['artwork_codec','api_budget','config','diagnostics','engine','gui','media_bridge','media_commands','spotify_api','tray','windows_integration','main']
    for n in modules:
        actual=marshal.loads(archive.extract('main')) if n=='main' else pyz.extract(n)
        assert normalize(actual)==normalize(compile((ROOT/'companion'/(n+'.py')).read_bytes(),n+'.py','exec')),n
    resources=['default_config.json','settings.ps1','settings-view.ps1','ui/bongo.png'];names={n.replace('\\','/'):n for n in archive.toc}
    for n in resources:assert archive.extract(names[n])==(ROOT/'companion'/n).read_bytes(),n
    assert 'media_seek' not in pyz.toc
    package=dict(path=str(exe),bytes=exe.stat().st_size,sha256=sha(exe),modules=modules,resources=resources,started=False)
    save('package-verification.json',package)
    scope=dict(changed=sorted(changed),new_sources=sorted(NEW),source_count=len(sources),compiled_python=compiled,
        preserved_files=len(preserved),mismatches=[],other_engine_methods_ast_unchanged=True,
        intermediate_previews_and_apps_preserved=True,
        installed_pair='FD9D811B/C6EBAE4B',preview_manifest_sha256=sha(folder/'manifest.json'),review=review)
    save('scope-verification.json',scope)
    data=dict(status='built separate app/firmware; not installed/flashed; physical latency/quality pending',firmware=firmware,
        companion=package,scope=scope,tests=results,manifest_sha256={n:sha(BUILD/n) for n in
            ('source-frozen.json','firmware-verification.json','package-verification.json','scope-verification.json')})
    save('candidate.json',data);print(json.dumps({**data,'candidate_manifest_sha256':sha(BUILD/'candidate.json')}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['focused','test','capture','freeze','verify']);mode=parser.parse_args().mode
    if mode in ('focused','test'):sys.exit(tests(mode=='focused'))
    elif mode=='capture':capture()
    elif mode=='freeze':freeze()
    else:verify()
