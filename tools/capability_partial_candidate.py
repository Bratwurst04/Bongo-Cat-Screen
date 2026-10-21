"""Isolated app-only partial CAPS recovery checks; never run/install a candidate."""
import argparse
import ast
import contextlib
import hashlib
import json
import marshal
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/capability-partial-2026-10-20'
DIST=ROOT/'dist/companion-2026-10-20-capability-partial-dev'
NEW={'tests/test_capability_partial.py','tools/capability_partial_candidate.py'}
CHANGED={'companion/engine.py','00_PROJECT_CONTEXT.md','01_CURRENT_STATE.md','02_DECISIONS.md'}
FIRMWARE=ROOT/'.pio/candidates/artwork-refinement-2026-10-19-EBB334A9.bin'
FIRMWARE_SHA='EBB334A926709E047DA1D930684C76D02DFA162332C508E775F062AE492E2FF3'
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools'),str(ROOT/'companion')]
os.environ['APPDATA']=str(BUILD/'profile/Roaming');os.environ['LOCALAPPDATA']=str(BUILD/'profile/Local')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()


def save(name,data):(BUILD/name).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')


def tests(focused):
    import compact_art_host,turntable_face_host,artwork_fast_host,record_flip_host,turntable_paw_host
    turntable_face_host.BUILD=BUILD/'native';compact_art_host.BUILD=BUILD/'native/parser'
    artwork_fast_host.BUILD=BUILD/'native/rx';record_flip_host.BUILD=BUILD/'native/record';turntable_paw_host.BUILD=BUILD/'native/paw'
    import test_artwork_crop
    # Only public synthetic fixtures are needed; do not read the earlier private photo.
    test_artwork_crop.FIXTURE=BUILD/'absent-photo.png'
    patterns=(('test_capability_partial.py',) if focused else ('test_capability*.py','test_artwork_v2.py',
        'test_artwork_compact.py','test_artwork_refinement.py','test_artwork_fast.py','test_artwork_crop.py',
        'test_lifecycle.py','test_power_resume.py','test_media_commands.py'))
    label='focused' if focused else 'tests';started=time.monotonic();blocked=[]
    connect=socket.socket.connect;connect_ex=socket.socket.connect_ex;lookup=socket.getaddrinfo
    def allow(host):
        if host not in ('localhost','127.0.0.1','::1',None):blocked.append('external');raise AssertionError('External network disabled')
    def guarded(sock,address):
        if isinstance(address,tuple):allow(address[0])
        return connect(sock,address)
    def guarded_ex(sock,address):
        if isinstance(address,tuple):allow(address[0])
        return connect_ex(sock,address)
    def resolve(host,*args,**kwargs):allow(host);return lookup(host,*args,**kwargs)
    with (BUILD/(label+'.log')).open('w',encoding='utf-8') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log),\
         patch.object(socket.socket,'connect',guarded),patch.object(socket.socket,'connect_ex',guarded_ex),patch.object(socket,'getaddrinfo',resolve):
        suite=unittest.TestSuite([unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=p) for p in patterns])
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    data=dict(discovered=result.testsRun,passed=result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
        errors=len(result.errors),failures=len(result.failures),skipped=len(result.skipped),external_network_attempts=len(blocked),
        seconds=round(time.monotonic()-started,3),patterns=patterns,profiles_isolated=True,
        skip_details=[dict(test=str(t),reason=r) for t,r in result.skipped])
    save(label+'-summary.json',data);print(json.dumps(data));return 0 if result.wasSuccessful() and not blocked else 1


def freeze():
    target=BUILD/'source-frozen';assert not target.exists(),'Preserve previous freeze'
    names=set(json.loads((BUILD/'baseline-source.json').read_text()))|NEW;manifest={}
    for name in sorted(names):
        dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest);manifest[name]=sha(ROOT/name)
    save('source-frozen.json',manifest);print(json.dumps(dict(sources=len(manifest),sha256=sha(BUILD/'source-frozen.json'))))


def package():
    from PyInstaller.archive.readers import CArchiveReader
    from devices_diagnostics_candidate import normalize
    exe=DIST/'BongoDeskSpotify.exe';archive=CArchiveReader(str(exe));pyz=archive.open_embedded_archive('PYZ.pyz')
    modules=['artwork_crop','artwork_codec','api_budget','config','diagnostics','engine','gui','media_bridge',
        'media_commands','spotify_api','tray','windows_integration','main']
    for name in modules:
        actual=marshal.loads(archive.extract('main')) if name=='main' else pyz.extract(name)
        assert normalize(actual)==normalize(compile((ROOT/'companion'/(name+'.py')).read_bytes(),name+'.py','exec')),name
    resources=['default_config.json','settings.ps1','settings-view.ps1','ui/bongo.png']
    entries={n.replace('\\','/'):n for n in archive.toc}
    for name in resources:assert archive.extract(entries[name])==(ROOT/'companion'/name).read_bytes(),name
    assert 'media_seek' not in pyz.toc
    info=dict(path=str(exe),bytes=exe.stat().st_size,sha256=sha(exe),modules=modules,resources=resources,started=False)
    save('package-verification.json',info);print(json.dumps(info));return info


def engine_methods(data):
    tree=ast.parse(data);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='BongoCatEngine')
    return {n.name:ast.dump(n,include_attributes=False) for n in cls.body if isinstance(n,ast.FunctionDef)}


def verify():
    sources=json.loads((BUILD/'source-frozen.json').read_text());compiled=0
    for name,digest in sources.items():
        assert sha(ROOT/name)==sha(BUILD/'source-frozen'/name)==digest,name
        if name.endswith('.py'):compile((ROOT/name).read_bytes(),name,'exec');compiled+=1
    base=json.loads((BUILD/'baseline-source.json').read_text());changed={n for n,h in base.items() if sha(ROOT/n)!=h}
    assert changed==CHANGED,changed
    old=engine_methods(subprocess.check_output(['git','show','45a0be8:companion/engine.py'],cwd=ROOT))
    now=engine_methods((ROOT/'companion/engine.py').read_bytes())
    assert set(now)-set(old)=={'_confirm_compact_from_refine'}
    assert {n for n in old if old[n]!=now[n]}=={'__init__','send_initial_sync','_serial_reader_loop'}
    protected=json.loads((BUILD/'preserved-before.json').read_text())
    for name,info in protected.items():
        if name in CHANGED:continue
        p=ROOT/name;assert p.stat().st_size==info['bytes'] and sha(p)==info['sha256'],name
    for name in ('00_PROJECT_CONTEXT.md','01_CURRENT_STATE.md','02_DECISIONS.md'):
        old=(BUILD/'baseline-status'/name).read_bytes()
        title,tail=old.split(b'\n',1);now=(ROOT/name).read_bytes();assert now.startswith(title+b'\n') and now.endswith(tail),name
    before=json.loads((BUILD/'before-repro.json').read_text());assert before['bytes_selected']==37632 and not before['compact']
    results={label:json.loads((BUILD/(label+'-summary.json')).read_text()) for label in ('focused','tests')}
    for result in results.values():assert not any(result[k] for k in ('errors','failures','external_network_attempts'))
    assert results['focused']['skipped']==0 and results['tests']['skipped']==1
    assert 'test_real_square_wrapper' in results['tests']['skip_details'][0]['test']
    assert sha(FIRMWARE)==FIRMWARE_SHA
    firmware=dict(path=str(FIRMWARE),bytes=FIRMWARE.stat().st_size,sha256=FIRMWARE_SHA,rebuilt=False,flashed=False)
    save('firmware-reference.json',firmware);app=package()
    assert sha(BUILD/'root-review.json')=='A9DFD4921C594BDE3B779DD54A6AA2E3211129E64965D5FA2635CCB78120D9AE'
    review=json.loads((BUILD/'root-review.json').read_text())
    assert review['result']=='pass' and review['app_sha256']==app['sha256'] and review['app_bytes']==app['bytes']
    assert review['modules_match']==app['modules'] and review['resources_match']==app['resources']
    assert review['firmware_sha256']==FIRMWARE_SHA and not review['candidate_executed']
    scope=dict(changed=sorted(changed),new_sources=sorted(NEW),frozen_sources=len(sources),compiled_python=compiled,
        protected_files=len(protected),mismatches=[],other_engine_methods_ast_unchanged=True,installed_pair='94145746/EBB334A9',
        firmware_unchanged=True,root_package_review='pass',root_review_sha256=sha(BUILD/'root-review.json'),physical_recovery='pending')
    save('scope-verification.json',scope)
    info=dict(status='separate app built, not started/installed; physical recovery pending',app=app,unchanged_firmware=firmware,
        scope=scope,tests=results,manifest_sha256={n:sha(BUILD/n) for n in
            ('source-frozen.json','package-verification.json','firmware-reference.json','scope-verification.json')})
    save('candidate.json',info);print(json.dumps({**info,'candidate_manifest_sha256':sha(BUILD/'candidate.json')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['focused','test','freeze','package','verify']);mode=parser.parse_args().mode
    if mode in ('focused','test'):sys.exit(tests(mode=='focused'))
    elif mode=='freeze':freeze()
    elif mode=='package':package()
    else:verify()
