"""Inspect historical source without restoring retired modules to the product."""
from pathlib import Path
import hashlib
import json
import sys
import types
import unittest
from unittest.mock import patch


def load_module(name, path, *, optional_archive=False):
    path = Path(path)
    if optional_archive and not path.exists():
        raise unittest.SkipTest('Historical source archive absent: '+str(path))
    if optional_archive:
        frozen=next(parent for parent in path.parents if parent.name=='source-frozen')
        manifest=json.loads((frozen.parent/'source-frozen.json').read_text(encoding='utf-8'))
        expected=manifest[path.relative_to(frozen).as_posix()]
        if hashlib.sha256(path.read_bytes()).hexdigest().upper()!=expected.upper():
            raise ValueError('Historical source archive hash mismatch: '+str(path))
    module = types.ModuleType(name)
    module.__file__ = str(path)
    aliases = {name: module}
    # Older snapshots own their own dependencies, including removed helpers.
    legacy_path = path.parent / 'media_seek.py'
    if legacy_path.exists():
        legacy_name = 'media_seek'
        legacy = types.ModuleType(legacy_name)
        legacy.__file__ = str(legacy_path)
        aliases[legacy_name] = legacy
        with patch.dict(sys.modules, aliases):
            exec(compile(legacy_path.read_bytes(), str(legacy_path), 'exec'), legacy.__dict__)
    with patch.dict(sys.modules, aliases):
        exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module
