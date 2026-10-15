"""Inspect the manual-refresh candidate without starting the EXE."""
import hashlib
import io
import json
import marshal
from pathlib import Path
import sys
import types
from zoneinfo import ZoneInfo
from PyInstaller.archive.readers import CArchiveReader

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/manual-api-refresh-2026-10-15'
EXE=ROOT/'dist/companion-2026-10-15-manual-api-refresh-dev/BongoDeskSpotify.exe'
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
    allowed={'companion/spotify_api.py','companion/media_bridge.py','companion/media_seek.py',
             'tests/test_api_budget_integration.py','tests/test_media_seek.py','tests/test_spotify_cooldown.py',
             'docs/api-budget-runtime-2026-10-15.md'}
    assert set(changed)<=allowed,changed
    preserved=json.loads((BUILD/'baseline/preserved-artifacts.json').read_text())
    for name,info in preserved.items():
        assert sha(ROOT/name)==info['sha256'] and (ROOT/name).stat().st_size==info['bytes'],name
    assert sha(ROOT/'companion/api_budget.py')==baseline['companion/api_budget.py']
    result=dict(path=str(EXE),bytes=EXE.stat().st_size,sha256=sha(EXE),modules=modules,
        resources=resources,timezone='Europe/Stockholm',changed_baseline_files=changed,
        api_budget_byte_identical=True,preserved_artifacts=len(preserved),exe_started=False)
    (BUILD/'package-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


def metrics():
    sys.path.insert(0,str(ROOT/'tests'))
    from test_manual_api_refresh import ManualRefreshTests
    case=ManualRefreshTests();rows=[]
    try:
        for label,settings in [('automatic',{'tap':False}),('manual',{}),('persistent401',{'persistent401':True})]:
            r=case.scenario(**settings)
            rows.append(dict(scenario=label,http_calls=len(r['calls']),manual_get_attempts=len(r['manual_times']),
                first_get_after_wait_cue_seconds=round(r['calls'][1][2]-r['wait_seen'],3),
                next_auto_after_manual_seconds=round(r['api_gets'][-1]-r['api_gets'][0],3),
                total_costs=r['view']['long_used'],automatic_costs=r['view']['long_auto_used'],
                reserved=r['view']['reserved'],fast_active=r['view']['fast_active'],local_activity=r['activity']))
    finally:case.doCleanups()
    output=dict(classification='virtual clock/mock HTTP/full worker/real FileStore; not hardware evidence',results=rows)
    (BUILD/'worker-metrics.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))


if __name__=='__main__':
    verify()
    metrics()
