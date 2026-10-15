"""Read-only EXE comparison and checks that only approved policy floors changed."""
import ast
import hashlib
import io
import json
import marshal
from pathlib import Path
import types
from zoneinfo import ZoneInfo
from PyInstaller.archive.readers import CArchiveReader

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/active-api-recovery-2026-10-15'
EXE=ROOT/'dist/companion-2026-10-15-active-api-recovery-dev/BongoDeskSpotify.exe'
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest().upper()


def normalize(code):
    return code.replace(co_filename='<source>',co_consts=tuple(
        normalize(v) if isinstance(v,types.CodeType) else v for v in code.co_consts))


def policy_ast(path,client=False):
    tree=ast.parse(path.read_bytes())
    for node in tree.body:
        if isinstance(node,ast.ClassDef):
            if client and node.name=='SpotifyApiBridge':
                node.body=[item for item in node.body if not isinstance(item,ast.FunctionDef) or
                           item.name not in ('_quota_poll_floor','poll_delay_seconds','poll_interval_seconds')]
            if not client and node.name=='ApiBudget':
                for item in node.body:
                    if isinstance(item,ast.FunctionDef) and item.name=='_profile':
                        item.body=[statement for statement in item.body if not (
                            isinstance(statement,ast.If) and any(isinstance(v,ast.Constant) and
                                v.value in ('warm_until','quota_strong') for v in ast.walk(statement.test)))]
    return ast.dump(tree,include_attributes=False)


def verify():
    archive=CArchiveReader(str(EXE));pyz=archive.open_embedded_archive('PYZ.pyz')
    modules=['api_budget','config','diagnostics','engine','gui','media_bridge','media_seek',
             'spotify_api','tray','windows_integration','main']
    for name in modules:
        expected=compile((ROOT/'companion'/(name+'.py')).read_bytes(),name+'.py','exec')
        actual=marshal.loads(archive.extract('main')) if name=='main' else pyz.extract(name)
        assert normalize(actual)==normalize(expected),name
    names={n.replace('\\','/'):n for n in archive.toc}
    resources=['default_config.json','settings.ps1','settings-view.ps1','ui/bongo.png']
    for name in resources:assert archive.extract(names[name])==(ROOT/'companion'/name).read_bytes(),name
    assert ZoneInfo.from_file(io.BytesIO(archive.extract(names['tzdata/zoneinfo/Europe/Stockholm'])))
    assert 'tzdata.zoneinfo.Europe' in pyz.toc
    baseline=json.loads((BUILD/'baseline/manifest.json').read_text())
    changed=[n for n,d in baseline.items() if sha(ROOT/n)!=d]
    allowed={'companion/api_budget.py','companion/spotify_api.py','docs/api-budget-runtime-2026-10-15.md',
             'tests/test_api_budget.py','tests/test_api_control_confirmation.py','tests/test_manual_api_refresh.py',
             'tests/test_adaptive_connect.py','tests/test_spotify_cooldown.py','tests/test_api_budget_integration.py'}
    assert set(changed)<=allowed,changed
    for name,client in [('api_budget.py',False),('spotify_api.py',True)]:
        assert policy_ast(ROOT/'companion'/name,client)==policy_ast(BUILD/'baseline/companion'/name,client),name
    preserved=json.loads((BUILD/'baseline/preserved-artifacts.json').read_text())
    for name,info in preserved.items():
        assert sha(ROOT/name)==info['sha256'] and (ROOT/name).stat().st_size==info['bytes'],name
    result=dict(path=str(EXE),bytes=EXE.stat().st_size,sha256=sha(EXE),modules=modules,resources=resources,
        timezone='Europe/Stockholm',changed_baseline_files=changed,preserved_artifacts=len(preserved),
        guards_schema_caps_other_policy_and_client_methods_ast_identical=True,exe_started=False)
    (BUILD/'package-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':verify()
