"""C3 app-only tests/freeze/package verification; never opens a port or EXE."""
import argparse
import ast
import contextlib
import hashlib
import json
import marshal
from pathlib import Path
import socket
import sys
import time
import unittest
from unittest.mock import patch

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/capability-startup-2026-10-18'
DIST=ROOT/'dist/companion-2026-10-18-capability-startup-dev'
NEW={'tests/test_capability_startup.py','tools/capability_startup_candidate.py'}
CHANGED={'companion/engine.py','00_PROJECT_CONTEXT.md','01_CURRENT_STATE.md','02_DECISIONS.md'}
FIRMWARE=ROOT/'.pio/candidates/artwork-compact80-2026-10-18-C6EBAE4B.bin'
FIRMWARE_SHA='C6EBAE4B13DE934449E2F32738D2CBFAEEC2693C5ECF8EE8A3A71FDB6254D275'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'companion'),str(ROOT/'tools')]


def save(name,data):
    (BUILD/name).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')


def tests():
    import compact_art_host,artwork_fast_host,record_flip_host,test_focus_countdown
    compact_art_host.BUILD=BUILD/'native';artwork_fast_host.BUILD=BUILD/'queue-host'
    record_flip_host.BUILD=BUILD/'legacy-host';test_focus_countdown.BUILD=BUILD/'focus-fixtures'
    loader=unittest.defaultTestLoader
    suite=unittest.TestSuite([loader.discover(str(ROOT/'tests'),pattern=p) for p in
        ('test_capability_startup.py','test_artwork*.py','test_power_resume.py','test_lifecycle.py')])
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
         patch.object(socket.socket,'connect',guarded),patch.object(socket.socket,'connect_ex',guarded_ex),\
         patch.object(socket,'getaddrinfo',guarded_lookup):
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    data=dict(discovered=result.testsRun,passed=result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
        errors=len(result.errors),failures=len(result.failures),skipped=len(result.skipped),external_network_attempts=len(blocked),
        seconds=round(time.perf_counter()-started,3),scope='9 new recovery cases plus existing artwork/power-resume/lifecycle; no full suite')
    save('tests-summary.json',data);print(json.dumps(data))
    return 0 if result.wasSuccessful() and not blocked else 1


def freeze():
    import turntable_arm_tempo_candidate as prior
    prior.BUILD=BUILD;prior.NEW=NEW;prior.freeze()


def engine_methods(path):
    tree=ast.parse(path.read_bytes());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='BongoCatEngine')
    return {n.name:ast.dump(n,include_attributes=False) for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}


def verify():
    from PyInstaller.archive.readers import CArchiveReader
    from devices_diagnostics_candidate import normalize
    manifest=json.loads((BUILD/'source-frozen.json').read_text());compiled=0
    for name,h in manifest.items():
        assert sha(ROOT/name)==sha(BUILD/'source-frozen'/name)==h,name
        if name.endswith('.py'):compile((ROOT/name).read_bytes(),name,'exec');compiled+=1
    base=json.loads((BUILD/'baseline-source.json').read_text())
    changed={n for n,h in base.items() if sha(ROOT/n)!=h};assert changed==CHANGED,changed
    old=engine_methods(ROOT/'build/artwork-compact80-2026-10-18/source-frozen/companion/engine.py')
    current=engine_methods(ROOT/'companion/engine.py');allowed={'__init__','send_initial_sync','_serial_reader_loop'}
    assert set(current)-set(old)=={'_retry_capability_after_status'} and set(old)<=set(current)
    assert all(current[n]==body for n,body in old.items() if n not in allowed)
    preserved=json.loads((BUILD/'preserved-before.json').read_text())
    for name,v in preserved.items():assert (ROOT/name).stat().st_size==v['bytes'] and sha(ROOT/name)==v['sha256'],name
    assert sha(FIRMWARE)==FIRMWARE_SHA and FIRMWARE.stat().st_size==936704
    result=json.loads((BUILD/'tests-summary.json').read_text())
    assert not any(result[k] for k in ('errors','failures','skipped','external_network_attempts'))
    exe=DIST/'BongoDeskSpotify.exe';archive=CArchiveReader(str(exe));pyz=archive.open_embedded_archive('PYZ.pyz')
    modules=['artwork_codec','api_budget','config','diagnostics','engine','gui','media_bridge','media_commands','spotify_api','tray','windows_integration','main']
    for name in modules:
        expected=compile((ROOT/'companion'/(name+'.py')).read_bytes(),name+'.py','exec')
        actual=marshal.loads(archive.extract('main')) if name=='main' else pyz.extract(name)
        assert normalize(actual)==normalize(expected),name
    resources=['default_config.json','settings.ps1','settings-view.ps1','ui/bongo.png'];names={n.replace('\\','/'):n for n in archive.toc}
    for n in resources:assert archive.extract(names[n])==(ROOT/'companion'/n).read_bytes(),n
    assert 'media_seek' not in pyz.toc
    package=dict(path=str(exe),bytes=exe.stat().st_size,sha256=sha(exe),modules=modules,resources=resources,started=False)
    save('package-verification.json',package)
    scope=dict(changed=sorted(changed),new_sources=sorted(NEW),source_count=len(manifest),compiled_python=compiled,
        preserved_files=len(preserved),mismatches=[],other_engine_methods_ast_unchanged=True,
        firmware=dict(path=str(FIRMWARE),sha256=FIRMWARE_SHA,bytes=936704,rebuilt=False,flashed=False),
        installed_pair='356A5EC0/C6EBAE4B',runtime_profile_api_ui_codec_unchanged=True,
        runtime_report_sha256=sha(ROOT/'docs/artwork-compact80-runtime-2026-10-18.md'))
    save('scope-verification.json',scope)
    data=dict(status='built app only; not run/installed; physical recovery and C2 speed pending',
        companion=package,scope=scope,tests=result,
        manifest_sha256={n:sha(BUILD/n) for n in ('source-frozen.json','package-verification.json','scope-verification.json')})
    save('candidate.json',data)
    print(json.dumps(dict(companion=package,scope=scope,manifest_sha256={**data['manifest_sha256'],'candidate.json':sha(BUILD/'candidate.json')})))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['test','freeze','verify']);args=parser.parse_args()
    if args.mode=='test':sys.exit(tests())
    elif args.mode=='freeze':freeze()
    else:verify()
