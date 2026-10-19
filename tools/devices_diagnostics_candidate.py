"""Isolated tests, source freeze and package verification for the devices probe."""
import argparse
import ast
import contextlib
import hashlib
import io
import json
import marshal
import os
from pathlib import Path
import shutil
import socket
import sys
import time
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/devices-diagnostics-2026-10-17'
BASE = ROOT / 'build/playback-endpoint-diagnostics-2026-10-16'
DIST = ROOT / 'dist/companion-2026-10-17-devices-diagnostics-dev'
EXE = DIST / 'BongoDeskSpotify.exe'
SOURCE = BUILD / 'source-frozen'
NEW = {'tests/test_devices_diagnostics.py', 'tools/devices_diagnostics_candidate.py'}
CHANGED = {'companion/spotify_api.py', 'companion/media_bridge.py',
           'companion/diagnostics.py', 'tests/test_playback_endpoint_diagnostics.py'}
REPORT = 'docs/devices-diagnostics-2026-10-17.md'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def save(name, value):
    (BUILD / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def sources():
    return sorted(set(json.loads((BASE / 'source-frozen.json').read_text())) | NEW)


def tests(focused):
    sys.path[:0] = [str(ROOT / 'companion'), str(ROOT / 'tests')]
    import record_flip_host
    record_flip_host.BUILD = BUILD / ('native-focused' if focused else 'native-regression')
    pattern = 'test_devices_diagnostics.py' if focused else 'test_*.py'
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=pattern)
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_lookup = socket.getaddrinfo
    blocked = []

    def allow(host):
        if host not in ('localhost', '127.0.0.1', '::1', None):
            blocked.append('external_network_attempt')
            raise AssertionError('External network disabled in isolated candidate tests')

    def connect(sock, address):
        if isinstance(address, tuple): allow(address[0])
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if isinstance(address, tuple): allow(address[0])
        return original_connect_ex(sock, address)

    def lookup(host, *args, **kwargs):
        allow(host)
        return original_lookup(host, *args, **kwargs)

    label = 'focused' if focused else 'regression'
    started = time.perf_counter()
    from unittest.mock import patch
    with (BUILD / (label + '-tests.log')).open('w', encoding='utf-8') as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log), \
             patch.object(socket.socket, 'connect', connect), \
             patch.object(socket.socket, 'connect_ex', connect_ex), patch.object(socket, 'getaddrinfo', lookup):
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    summary = dict(discovered=result.testsRun,
                   passed=result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
                   skipped=len(result.skipped), failures=len(result.failures), errors=len(result.errors),
                   external_network_attempts=len(blocked), seconds=round(time.perf_counter()-started, 3),
                   skip_details=[dict(test=str(t), reason=reason) for t, reason in result.skipped])
    save(label + '-summary.json', summary)
    print(json.dumps(summary))
    return 0 if result.wasSuccessful() and not blocked else 1


def freeze():
    assert not SOURCE.exists(), 'Refusing to replace a frozen source tree'
    manifest = {}
    for name in sources():
        path = ROOT / name
        destination = SOURCE / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        manifest[name] = sha(path)
    save('source-frozen.json', manifest)
    print(json.dumps(dict(frozen_sources=len(manifest), source_manifest_sha256=sha(BUILD/'source-frozen.json'))))


def normalize(code):
    return code.replace(co_filename='<source>', co_consts=tuple(
        normalize(value) if isinstance(value, types.CodeType) else value for value in code.co_consts))


def methods(path, cls):
    tree = ast.parse(path.read_bytes())
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return {n.name: ast.dump(n, include_attributes=False) for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def request_guards(path):
    tree = ast.parse(path.read_bytes())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SpotifyApiBridge')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_api_request_locked')
    marker = next(i for i,n in enumerate(method.body) if isinstance(n, ast.Assign) and
                  any(isinstance(t, ast.Name) and t.id == 'resolved_endpoint' for t in n.targets))
    start = next(n for n in method.body if isinstance(n, ast.FunctionDef) and n.name == 'start_check')
    invoke = next(n for n in method.body if isinstance(n, ast.FunctionDef) and n.name == 'invoke')
    for node in ast.walk(invoke):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'event'
                and node.args and isinstance(node.args[0], ast.Call) and
                isinstance(node.args[0].func, ast.Name) and node.args[0].func.id == 'http_event'):
            node.args[0] = ast.Constant('SPOTIFY_PLAYBACK_HTTP')
    outer = next(n for n in method.body if isinstance(n, ast.Try))
    constants = [n for n in tree.body if isinstance(n, ast.Assign) and
                 any(isinstance(t, ast.Name) and t.id in {'SCOPES','API_URL','ACCOUNTS_URL'} for t in n.targets)]
    return ast.dump(ast.Module(body=method.body[:marker]+[start,invoke]+outer.handlers+constants,
                               type_ignores=[]), include_attributes=False)


def verify():
    from PyInstaller.archive.readers import CArchiveReader
    from zoneinfo import ZoneInfo
    manifest = json.loads((BUILD / 'source-frozen.json').read_text())
    compiled = 0
    for name, digest in manifest.items():
        assert sha(ROOT/name) == sha(SOURCE/name) == digest, name
        if name.endswith('.py'):
            compile((SOURCE/name).read_bytes(), name, 'exec')
            compiled += 1
    previous = json.loads((BASE/'source-frozen.json').read_text())
    changed = {name for name, digest in previous.items() if sha(ROOT/name) != digest}
    assert changed == CHANGED, changed
    assert request_guards(BASE/'source-frozen/companion/spotify_api.py') == request_guards(
        SOURCE/'companion/spotify_api.py'), 'Shared HTTP/auth/guard/retry path changed'
    for filename, cls, excluded in [
        ('spotify_api.py', 'SpotifyApiBridge', {'diagnose_playback', 'diagnose_devices', '_devices_summary', '_api_request_locked'}),
        ('media_bridge.py', 'WindowsMediaBridge', {'__init__', '_run', '_observe_primary_playback', '_clear_api_work',
             '_finish_endpoint_probe', '_endpoint_probe_pending', '_endpoint_probe_can_start', '_start_endpoint_probe',
             '_finish_devices_probe', '_devices_probe_pending', '_devices_probe_can_start', '_start_devices_probe'})]:
        old = methods(BASE/'source-frozen/companion'/filename, cls)
        current = methods(SOURCE/'companion'/filename, cls)
        assert {n:v for n,v in old.items() if n not in excluded} == {
            n:v for n,v in current.items() if n not in excluded}, filename
    preserved = json.loads((BUILD/'preserved-before.json').read_text())
    for name, info in preserved.items():
        assert (ROOT/name).stat().st_size == info['bytes'] and sha(ROOT/name) == info['sha256'], name
    allowed = set(preserved) | CHANGED | NEW | {REPORT}
    for base, dirs, files in os.walk(ROOT):
        if '.git' in dirs: dirs.remove('.git')
        for name in files:
            path = Path(base)/name
            if path.is_relative_to(BUILD) or path.is_relative_to(DIST): continue
            assert path.relative_to(ROOT).as_posix() in allowed, path
    scope = dict(changed_existing_sources=sorted(changed), new_sources=sorted(NEW), new_report=REPORT,
                 preserved_files=len(preserved), preservation_mismatches=[],
                 unchanged_other_client_and_bridge_methods_ast=True,
                 unchanged_shared_http_auth_retry_guards_ast=True,
                 firmware_budget_engine_authscope_ui_serial_run_release_unchanged=True)
    save('scope-verification.json', scope)
    archive = CArchiveReader(str(EXE)); pyz = archive.open_embedded_archive('PYZ.pyz')
    modules = ['api_budget', 'config', 'diagnostics', 'engine', 'gui', 'media_bridge', 'media_commands',
               'spotify_api', 'tray', 'windows_integration', 'main']
    for name in modules:
        expected = compile((SOURCE/'companion'/(name+'.py')).read_bytes(), name+'.py', 'exec')
        actual = marshal.loads(archive.extract('main')) if name == 'main' else pyz.extract(name)
        assert normalize(actual) == normalize(expected), name
    assert 'media_seek' not in pyz.toc
    names = {n.replace('\\','/'):n for n in archive.toc}
    resources = ['default_config.json', 'settings.ps1', 'settings-view.ps1', 'ui/bongo.png']
    for name in resources:
        assert archive.extract(names[name]) == (SOURCE/'companion'/name).read_bytes(), name
    assert ZoneInfo.from_file(io.BytesIO(archive.extract(names['tzdata/zoneinfo/Europe/Stockholm'])))
    assert 'tzdata.zoneinfo.Europe' in pyz.toc
    package = dict(companion=dict(path=str(EXE), bytes=EXE.stat().st_size, sha256=sha(EXE)),
                   modules=modules, resources=resources, timezone='Europe/Stockholm',
                   compiled_python_sources=compiled, current_and_frozen_sources_each=len(manifest),
                   exe_started=False, live_api_calls=0, retired_seek_module_absent=True)
    save('package-verification.json', package)
    summary = json.loads((BUILD/'regression-summary.json').read_text())
    focused = json.loads((BUILD/'focused-summary.json').read_text())
    assert all(not s[k] for s in (summary, focused) for k in ('errors','failures','external_network_attempts'))
    candidate = dict(status='frozen; isolated verification only; not installed; not a fix',
                     **package, regression=summary, focused=focused, preserved_files=len(preserved),
                     changed_files=sorted(CHANGED | NEW | {REPORT}),
                     installed_pair_unchanged='3EDD2187/55669C87',
                     diagnostic='one devices transport attempt at most; replaces due A; no HTTP retry including401;90sTTL',
                     manifest_sha256={n:sha(BUILD/n) for n in
                        ('source-frozen.json','package-verification.json','scope-verification.json')})
    save('candidate.json', candidate)
    print(json.dumps(dict(**package, manifest_sha256={**candidate['manifest_sha256'],
                                                   'candidate.json':sha(BUILD/'candidate.json')})))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['focused','regression','freeze','verify'])
    mode = parser.parse_args().mode
    if mode in ('focused','regression'): sys.exit(tests(mode == 'focused'))
    elif mode == 'freeze': freeze()
    else: verify()
