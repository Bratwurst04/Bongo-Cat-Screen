"""Inspect the correction archive and preserve the prior frozen candidate."""
import hashlib
import importlib.util
import io
import json
import marshal
from pathlib import Path
import types
from zoneinfo import ZoneInfo
from PyInstaller.archive.readers import CArchiveReader

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/api-control-fix-2026-10-15'
EXE=ROOT/'dist/companion-2026-10-15-api-control-fix-dev/BongoDeskSpotify.exe'
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest().upper()


def normalize(code):
    return code.replace(co_filename='<source>',co_consts=tuple(
        normalize(value) if isinstance(value,types.CodeType) else value for value in code.co_consts))


def verify():
    archive=CArchiveReader(str(EXE));pyz=archive.open_embedded_archive('PYZ.pyz')
    modules=['api_budget','config','diagnostics','engine','gui','media_bridge','media_seek',
             'spotify_api','tray','windows_integration','main']
    for name in modules:
        expected=compile((ROOT/'companion'/(name+'.py')).read_bytes(),name+'.py','exec')
        actual=marshal.loads(archive.extract('main')) if name=='main' else pyz.extract(name)
        assert normalize(actual)==normalize(expected),name
    names={name.replace('\\','/'):name for name in archive.toc}
    resources=['default_config.json','settings.ps1','settings-view.ps1','ui/bongo.png']
    for name in resources:assert archive.extract(names[name])==(ROOT/'companion'/name).read_bytes(),name
    zone=ZoneInfo.from_file(io.BytesIO(archive.extract(names['tzdata/zoneinfo/Europe/Stockholm'])))
    assert zone is not None and 'tzdata.zoneinfo.Europe' in pyz.toc
    baseline=json.loads((BUILD/'baseline/manifest.json').read_text())
    changed=[name for name,digest in baseline.items() if sha(ROOT/name)!=digest]
    allowed={'companion/spotify_api.py','companion/media_bridge.py','companion/diagnostics.py',
             'docs/api-budget-runtime-2026-10-15.md'}
    assert set(changed)<=allowed,changed
    preserved=json.loads((BUILD/'baseline/preserved-artifacts.json').read_text())
    for name,info in preserved.items():
        path=ROOT/name
        assert sha(path)==info['sha256'] and path.stat().st_size==info['bytes'],name
    assert sha(ROOT/'companion/api_budget.py')==baseline['companion/api_budget.py']
    result=dict(path=str(EXE),bytes=EXE.stat().st_size,sha256=sha(EXE),
                modules=modules,resources=resources,timezone='Europe/Stockholm',
                changed_baseline_files=changed,preserved_artifacts=len(preserved),
                api_budget_byte_identical=True,exe_started=False)
    (BUILD/'package-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


def metrics():
    spec=importlib.util.spec_from_file_location('control_worker_fixture',ROOT/'tests/test_api_control_confirmation.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    case=module.ControlConfirmationTests();rows=[]
    try:
        for label,client,gate,actions in [('frozen',module.frozen_client(),1.0,('NEXT',)),
                ('fixed',module.SpotifyApiBridge,.5,('NEXT','PLAY_PAUSE','PLAY_PAUSE')),
                ('fixed',module.SpotifyApiBridge,1.0,('NEXT','PLAY_PAUSE','PLAY_PAUSE'))]:
            result=case.worker(client=client,gate=gate,actions=actions,status=200,payload=b'accepted',
                               headers={'Content-Type':'text/plain'})
            rows.append(dict(client=label,gate=gate,actions=actions,
                queued_to_confirm_seconds=[round(b-a,3) for a,b in zip(result['queued_times'],result['confirm_times'])],
                ack_to_confirm_seconds=[round(b-a,3) for a,b in zip(result['control_times'],result['confirm_times'])],
                http_calls=len(result['calls']),auto_costs=result['view']['long_auto_used'],
                reserved=result['view']['reserved'],final_playing=result['snapshots'][-1].playing,
                errors=[dict(error_type=e.kwargs['error_type'].__name__,http_status=e.kwargs.get('http_status'))
                        for e in result['events'] if e.kwargs.get('reason')=='api_error']))
    finally:case.doCleanups()
    output=dict(classification='virtual clock/mock HTTP/full worker/real FileStore; not runtime evidence',results=rows)
    (BUILD/'worker-metrics.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))


if __name__=='__main__':
    verify()
    metrics()
