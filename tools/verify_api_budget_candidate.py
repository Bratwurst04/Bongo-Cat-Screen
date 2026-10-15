"""Read-only package/source/preservation checks; never starts the companion."""
import datetime as dt
import hashlib
import io
import json
import marshal
from pathlib import Path
import sys
import types
from zoneinfo import ZoneInfo

from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/api-budget-2026-10-14'
EXE = ROOT / 'dist/companion-2026-10-14-api-budget-dev/BongoDeskSpotify.exe'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def normalize(code):
    return code.replace(co_filename='<source>', co_consts=tuple(
        normalize(value) if isinstance(value, types.CodeType) else value
        for value in code.co_consts))


def verify():
    archive = CArchiveReader(str(EXE))
    pyz = archive.open_embedded_archive('PYZ.pyz')
    modules = ['api_budget', 'config', 'diagnostics', 'engine', 'gui',
               'media_bridge', 'media_seek', 'spotify_api', 'tray', 'windows_integration']
    verified = []
    for name in modules + ['main']:
        expected = compile((ROOT / 'companion' / (name + '.py')).read_bytes(), name + '.py', 'exec')
        actual = marshal.loads(archive.extract('main')) if name == 'main' else pyz.extract(name)
        assert normalize(actual) == normalize(expected), 'Compiled module differs: ' + name
        verified.append(name)
    names = {name.replace('\\', '/'): name for name in archive.toc}
    resources = ['default_config.json', 'settings.ps1', 'settings-view.ps1', 'ui/bongo.png']
    for name in resources:
        assert archive.extract(names[name]) == (ROOT / 'companion' / name).read_bytes(), name
    zone_name = 'tzdata/zoneinfo/Europe/Stockholm'
    zone = ZoneInfo.from_file(io.BytesIO(archive.extract(names[zone_name])), key='Europe/Stockholm')
    offsets = [int(dt.datetime(2026, month, 14, tzinfo=zone).utcoffset().total_seconds())
               for month in (1, 7)]
    assert offsets == [3600, 7200]
    assert all(name in pyz.toc for name in ('tzdata', 'tzdata.zoneinfo', 'tzdata.zoneinfo.Europe'))
    preserved = json.loads((BUILD / 'baseline/preserved-artifacts.json').read_text())
    for name, info in preserved.items():
        path = ROOT / name
        assert path.stat().st_size == info['bytes'] and sha(path) == info['sha256'], name
    baseline = json.loads((BUILD / 'baseline/manifest.json').read_text())
    allowed = {'companion/' + name for name in [
        'BongoDeskSpotify.spec', 'README.md', 'config.py', 'default_config.json',
        'diagnostics.py', 'engine.py', 'media_bridge.py', 'media_seek.py',
        'requirements_app.txt', 'spotify_api.py']}
    allowed |= {'tests/' + name for name in [
        'test_adaptive_connect.py', 'test_media_seek.py', 'test_spotify_cooldown.py']}
    changed = [name for name, digest in baseline.items() if sha(ROOT / name) != digest]
    assert set(changed) <= allowed, 'Out of scope baseline change: ' + str(set(changed) - allowed)
    result = dict(exe=str(EXE), bytes=EXE.stat().st_size, sha256=sha(EXE),
                  compiled_modules=verified, byte_identical_resources=resources,
                  timezone='Europe/Stockholm', winter_summer_offsets_seconds=offsets,
                  preserved_artifacts=len(preserved), baseline_files=len(baseline),
                  changed_baseline_files=changed,
                  classification='archive inspection; EXE never started; no runtime or hardware proof')
    (BUILD / 'package-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    verify()
