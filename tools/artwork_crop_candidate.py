"""Isolated app-only crop evidence; no runtime, profile, COM, API or firmware build."""
import argparse
import ast
import contextlib
import hashlib
import json
import marshal
from pathlib import Path
import shutil
import socket
import sys
import time
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT/'build/artwork-crop-2026-10-19'
DIST = ROOT/'dist/companion-2026-10-19-artwork-crop-dev'
NEW = {'companion/artwork_crop.py', 'tests/test_artwork_crop.py',
       'tools/artwork_crop_candidate.py', 'tools/artwork_crop_visuals.py',
       'tests/fixtures/spotify-smtc-footer-alpha.png', 'tests/fixtures/vinyl59fc.py'}
CHANGED = {'companion/media_bridge.py', '00_PROJECT_CONTEXT.md', '01_CURRENT_STATE.md', '02_DECISIONS.md'}
FIRMWARE = ROOT/'.pio/candidates/artwork-refinement-2026-10-19-EBB334A9.bin'
FIRMWARE_SHA = 'EBB334A926709E047DA1D930684C76D02DFA162332C508E775F062AE492E2FF3'
sys.path[:0] = [str(ROOT/'tests'), str(ROOT/'tools'), str(ROOT/'companion')]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest().upper()


def save(name, data):
    (BUILD/name).write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')


def tests(focused):
    import compact_art_host, turntable_face_host, artwork_fast_host, record_flip_host, turntable_paw_host, test_focus_countdown
    compact_art_host.BUILD = BUILD/'native/parser'; turntable_face_host.BUILD = BUILD/'native'
    artwork_fast_host.BUILD = BUILD/'queue-host'; record_flip_host.BUILD = BUILD/'legacy-host'
    turntable_paw_host.BUILD = BUILD/'turntable-host'; test_focus_countdown.BUILD = BUILD/'focus-fixtures'
    from test_artwork_crop import FIXTURE, FIXTURE_SHA
    assert sha(FIXTURE) == FIXTURE_SHA, 'Authorized real example is mandatory for candidate verification'
    patterns = (('test_artwork_crop.py',) if focused else
        ('test_artwork*.py', 'test_turntable*.py', 'test_record_flip.py', 'test_media_text_utf8.py',
         'test_capability_startup.py', 'test_diagnostics.py', 'test_manual_api_refresh.py', 'test_local_media_control.py'))
    loader=unittest.defaultTestLoader
    suite=unittest.TestSuite([loader.discover(str(ROOT/'tests'), pattern=p) for p in patterns])
    original=socket.socket.connect; original_ex=socket.socket.connect_ex; lookup=socket.getaddrinfo; blocked=[]
    def allow(host):
        if host not in ('localhost','127.0.0.1','::1',None):
            blocked.append('external'); raise AssertionError('External network disabled')
    def connect(sock,address):
        if isinstance(address,tuple): allow(address[0])
        return original(sock,address)
    def connect_ex(sock,address):
        if isinstance(address,tuple): allow(address[0])
        return original_ex(sock,address)
    def resolve(host,*args,**kwargs): allow(host); return lookup(host,*args,**kwargs)
    label='focused' if focused else 'tests'; started=time.perf_counter()
    with (BUILD/(label+'.log')).open('w',encoding='utf-8') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log), \
         patch.object(socket.socket,'connect',connect), patch.object(socket.socket,'connect_ex',connect_ex), patch.object(socket,'getaddrinfo',resolve):
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    data=dict(discovered=result.testsRun, passed=result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
        errors=len(result.errors), failures=len(result.failures), skipped=len(result.skipped), external_network_attempts=len(blocked),
        seconds=round(time.perf_counter()-started,3), patterns=patterns,
        skip_details=[dict(test=str(t),reason=r) for t,r in result.skipped])
    save(label+'-summary.json',data); print(json.dumps(data))
    return 0 if result.wasSuccessful() and not blocked else 1


def freeze():
    frozen=BUILD/'source-frozen'; assert not frozen.exists(), 'Preserve previous freeze'
    names=set(json.loads((BUILD/'baseline-source.json').read_text()))|NEW
    manifest={}
    for name in sorted(names):
        destination=frozen/name; destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,destination); manifest[name]=sha(ROOT/name)
    save('source-frozen.json',manifest)
    print(json.dumps(dict(frozen_sources=len(manifest),manifest_sha256=sha(BUILD/'source-frozen.json'))))


def package():
    from PyInstaller.archive.readers import CArchiveReader
    from devices_diagnostics_candidate import normalize
    exe=DIST/'BongoDeskSpotify.exe'; archive=CArchiveReader(str(exe)); pyz=archive.open_embedded_archive('PYZ.pyz')
    modules=['artwork_crop','artwork_codec','api_budget','config','diagnostics','engine','gui','media_bridge',
             'media_commands','spotify_api','tray','windows_integration','main']
    for name in modules:
        code=marshal.loads(archive.extract('main')) if name=='main' else pyz.extract(name)
        assert normalize(code)==normalize(compile((ROOT/'companion'/(name+'.py')).read_bytes(), name+'.py','exec')), name
    resources=['default_config.json','settings.ps1','settings-view.ps1','ui/bongo.png']
    names={name.replace('\\','/'):name for name in archive.toc}
    for name in resources: assert archive.extract(names[name])==(ROOT/'companion'/name).read_bytes(), name
    assert 'media_seek' not in pyz.toc
    data=dict(path=str(exe),bytes=exe.stat().st_size,sha256=sha(exe),modules=modules,resources=resources,started=False)
    save('package-verification.json',data); print(json.dumps(data)); return data


def bridge_ast(path):
    tree=ast.parse(path.read_bytes())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='WindowsMediaBridge')
    methods={n.name:ast.dump(n,include_attributes=False) for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    return tree,methods


def verify():
    frozen=json.loads((BUILD/'source-frozen.json').read_text()); compiled=0
    for name,digest in frozen.items():
        assert sha(ROOT/name)==sha(BUILD/'source-frozen'/name)==digest, name
        if name.endswith('.py'): compile((ROOT/name).read_bytes(),name,'exec'); compiled+=1
    base=json.loads((BUILD/'baseline-source.json').read_text())
    changed={name for name,digest in base.items() if sha(ROOT/name)!=digest}; assert changed==CHANGED,changed
    old_tree,old=bridge_ast(ROOT/'build/artwork-refinement-2026-10-19/source-frozen/companion/media_bridge.py')
    now_tree,now=bridge_ast(ROOT/'companion/media_bridge.py')
    assert set(old)==set(now)
    assert {name for name in old if old[name]!=now[name]}=={'_read_session','_to_vinyl_rgb888'}
    reference_tree=ast.parse((ROOT/'tests/fixtures/vinyl59fc.py').read_bytes())
    reference_cls=next(n for n in reference_tree.body if isinstance(n,ast.ClassDef))
    reference=next(n for n in reference_cls.body if isinstance(n,ast.FunctionDef))
    assert ast.dump(reference,include_attributes=False)==old['_to_vinyl_rgb888']
    def outside(tree):
        result=[]
        for node in tree.body:
            if isinstance(node,ast.ImportFrom) and node.module=='artwork_crop': continue
            if isinstance(node,ast.ClassDef) and node.name=='WindowsMediaBridge':
                node.body=[n for n in node.body if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
            result.append(ast.dump(node,include_attributes=False))
        return result
    assert outside(old_tree)==outside(now_tree)
    preserved=json.loads((BUILD/'preserved-before.json').read_text())
    for name,info in preserved.items():
        assert (ROOT/name).stat().st_size==info['bytes'] and sha(ROOT/name)==info['sha256'],name
    # All old status text must survive beneath the new dated heading.
    for name in ('00_PROJECT_CONTEXT.md','01_CURRENT_STATE.md','02_DECISIONS.md'):
        old=(ROOT/name).read_bytes(); previous=(BUILD/'baseline-status'/name).read_bytes()
        title,tail=previous.split(b'\n',1); assert old.startswith(title+b'\n') and old.endswith(tail),name
    results={name:json.loads((BUILD/(name+'-summary.json')).read_text()) for name in ('focused','tests')}
    for result in results.values(): assert not any(result[k] for k in ('errors','failures','skipped','external_network_attempts'))
    portable=json.loads((BUILD/'portable-summary.json').read_text())
    assert (portable['passed'],portable['skipped'],portable['errors'],portable['failures'])==(7,1,0,0)
    assert 'test_real_square_wrapper' in portable['skip_details'][0]['test']
    preview_folder=BUILD/'preview/r2'; preview=json.loads((preview_folder/'manifest.json').read_text())
    for name,digest in preview['source_sha256'].items(): assert sha(ROOT/name)==digest,name
    for name,digest in preview['output_sha256'].items(): assert sha(preview_folder/name)==digest,name
    review=json.loads((BUILD/'ui-review.json').read_text()); assert review['preview_manifest_sha256']==sha(preview_folder/'manifest.json')
    previous=json.loads((BUILD/'preview/r1/manifest.json').read_text())
    for name,digest in previous['source_sha256'].items():assert sha(BUILD/'preview-r1-source-frozen'/name)==digest,name
    for name,digest in previous['output_sha256'].items():assert sha(BUILD/'preview/r1'/name)==digest,name
    assert sha(FIRMWARE)==FIRMWARE_SHA
    firmware=dict(path=str(FIRMWARE),sha256=FIRMWARE_SHA,bytes=FIRMWARE.stat().st_size,rebuilt=False,flashed=False)
    save('firmware-reference.json',firmware)
    app=package()
    scope=dict(changed=sorted(changed),new_sources=sorted(NEW),frozen_sources=len(frozen),compiled_python=compiled,
        preserved_files=len(preserved),mismatches=[],other_bridge_ast_unchanged=True,installed_pair='59FC2E33/EBB334A9',
        preview_manifest_sha256=sha(preview_folder/'manifest.json'),review=review)
    save('scope-verification.json',scope)
    data=dict(status='separate app built; not started or installed; physical crop acceptance pending',companion=app,
        unchanged_firmware=firmware,scope=scope,tests=results,without_private_photo=portable,manifest_sha256={name:sha(BUILD/name) for name in
            ('source-frozen.json','package-verification.json','firmware-reference.json','scope-verification.json')})
    save('candidate.json',data); print(json.dumps({**data,'candidate_manifest_sha256':sha(BUILD/'candidate.json')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('mode',choices=['focused','test','freeze','package','verify']); mode=parser.parse_args().mode
    if mode in ('focused','test'): sys.exit(tests(mode=='focused'))
    elif mode=='freeze': freeze()
    elif mode=='package': package()
    else: verify()
