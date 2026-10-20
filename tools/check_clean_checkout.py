"""Run offline checks on a fresh tracked-source snapshot, without old build files.

Usage: python -B tools/check_clean_checkout.py [--output-root NEW_PARENT]
Use --include-file tests/new_test.py for a reviewed new source/test before commit.
Needs the companion requirements and an existing MSVC compiler on Windows.
For raster tests, first fetch verified LVGL with fetch_lvgl_test_dependency.py,
then pass --testdeps-root build/testdeps/lvgl. The worker stays offline.
Each run retains a new output directory, source hashes, log and JSON summary.
These guards prevent accidental runtime I/O; they are not an OS security sandbox.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import ipaddress
import json
import os
from pathlib import Path
import shutil
import shlex
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_REASONS = (
    'Historical source archive absent:',
    'Historical seek preview font archive absent',
    'Historical player presentation source archive absent',
    'Historical record preview source archive absent',
)
HISTORICAL_TESTS = {
    'test_api_control_confirmation.ControlConfirmationTests.test_frozen_whitespace_204_reproduces_sent_control_lost_confirmation',
    'test_focus_countdown.CountdownTests.test_historical_seek_preview_matches_83cc460_sources_and_pinned_fonts',
    'test_focus_countdown.CountdownTests.test_player_presentation_preserved_from_08a',
    'test_playback_diagnostics.PlaybackDiagnosticsTests.test_request_trace_and_budget_match_installed_source_without_diagnostics',
    'unittest.loader.ModuleSkipped.test_playback_endpoint_diagnostics',
    'test_record_flip.RecordFlipTests.test_historical_preview_matches_frozen_sources_and_outputs',
}
PHOTO_TEST = 'test_artwork_crop.CropTests.test_real_square_wrapper_exact_album_without_second_inset'
PLATFORM_TESTS = {
    'test_focus_countdown.CountdownTests.test_cpp_actual_touch_handler_and_media_dispatch',
    'test_focus_countdown.CountdownTests.test_cpp_state_cache_and_ui_calls',
}


def classify_skip(test, reason):
    if test.id() in HISTORICAL_TESTS and reason.startswith(HISTORICAL_REASONS):
        return 'historical'
    if test.id() == PHOTO_TEST and reason.startswith('Authorized local SMTC fixture absent;'):
        return 'private_photo'
    if test.id() in PLATFORM_TESTS and reason.startswith('Host C++ runtime test NOT RUN:'):
        return 'platform'
    return 'unexpected'


def source_path(name):
    relative = Path(name)
    if relative.is_absolute() or relative.drive or '..' in relative.parts:
        raise ValueError('Source paths must be relative files inside this checkout')
    path = ROOT / relative
    if not relative.parts or not path.is_file():
        raise ValueError('Source file does not exist: ' + name)
    components = [path, *list(path.parents)[:len(relative.parts)-1]]
    if any(part.is_symlink() for part in components):
        raise ValueError('Source symlinks are not copied: ' + name)
    if not path.resolve().is_relative_to(ROOT):
        raise ValueError('Source path leaves the checkout: ' + name)
    return path


def worker_test_dependency(output):
    manifest_path = output / 'test-dependency-manifest.json'
    expected = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    if not expected:
        os.environ.pop('BONGO_TEST_LVGL_ROOT', None)
        return {}
    from fetch_lvgl_test_dependency import verify_dependency
    root = output / 'testdeps/lvgl'
    _, _, actual = verify_dependency(root)
    if actual != expected:
        raise ValueError('Snapshot LVGL dependency differs from its frozen manifest')
    os.environ['BONGO_TEST_LVGL_ROOT'] = str(root.resolve())
    return actual


def worker(output):
    snapshot = output / 'source'
    profile = output / 'profile'
    original_home = Path.home()
    protected = [original_home / 'AppData/Roaming/BongoCat']
    for variable, suffix in (('APPDATA', 'BongoCat'), ('LOCALAPPDATA', 'BongoDesk')):
        if os.environ.get(variable):
            protected.append(Path(os.environ[variable]) / suffix)
    for relative in ('AppData/Roaming', 'AppData/Local', 'temp'):
        (profile / relative).mkdir(parents=True)
    os.environ.update(APPDATA=str(profile / 'AppData/Roaming'),
                      LOCALAPPDATA=str(profile / 'AppData/Local'),
                      USERPROFILE=str(profile), HOMEDRIVE=profile.drive,
                      HOMEPATH=str(profile)[len(profile.drive):],
                      TEMP=str(profile / 'temp'), TMP=str(profile / 'temp'))
    tempfile.tempdir = str(profile / 'temp')
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(snapshot / name) for name in ('companion', 'tests', 'tools')]
    os.chdir(snapshot)
    test_dependency = worker_test_dependency(output)
    blocked = []

    def deny(operation):
        blocked.append(operation)
        raise AssertionError('Offline checks forbid ' + operation)

    def inside(path, folder):
        return Path(path).resolve().is_relative_to(folder.resolve())

    def guard_path(path, write=False):
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        path = os.fsdecode(path)
        if path.lower() in (os.devnull.lower(), 'nul'):
            return
        if any(inside(path, folder) for folder in protected):
            deny('real profile access')
        if write and not inside(path, output):
            deny('writes outside the new check directory')

    def audit(event, args):
        if event == 'open':
            mode, flags = args[1:3]
            write = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC))
            guard_path(args[0], write or isinstance(mode, str) and any(c in mode for c in 'wax+'))
        elif event in ('os.remove', 'os.rmdir', 'os.mkdir'):
            guard_path(args[0], True)
        elif event in ('os.rename', 'os.link', 'os.symlink'):
            guard_path(args[0], True)
            guard_path(args[1], True)
        elif event in ('winreg.SetValue', 'winreg.DeleteValue', 'winreg.CreateKey', 'winreg.DeleteKey'):
            deny('registry changes')
        elif event in ('socket.connect', 'socket.sendto'):
            if isinstance(args[-1], tuple):
                allow(args[-1][0])
        elif event == 'socket.getaddrinfo':
            allow(args[0])
        elif event == 'subprocess.Popen':
            executable, argv, cwd, _ = args
            # Windows reports a command-line string and often executable=None;
            # POSIX reports argv. Our commands use list2cmdline-style quoting.
            parts = ([word.strip('"') for word in shlex.split(argv, posix=False)]
                     if isinstance(argv, str) else list(argv))
            if not parts:
                deny('empty subprocess')
            program = executable or parts[0]
            name = Path(program).name.lower()
            compiler = name in ('cl.exe', 'g++', 'g++.exe', 'clang++', 'clang++.exe')
            compile_batch = (name == 'cmd.exe' and len(parts) == 4 and parts[1:3] == ['/d', '/c']
                             and Path(parts[3]).name == 'compile.cmd' and inside(parts[3], output))
            native_test = inside(program, output) and name in ('focus_countdown_test.exe', 'focus_status_touch_test.exe')
            if not (compiler or compile_batch or native_test) or not inside(cwd or os.getcwd(), output):
                deny('non-test subprocess')

    sys.addaudithook(audit)
    connect, connect_ex, lookup = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo

    def allow(host):
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host in ('localhost', None)
        if not loopback:
            deny('external network')

    def guarded_connect(sock, address):
        if isinstance(address, tuple):
            allow(address[0])
        return connect(sock, address)

    def guarded_connect_ex(sock, address):
        if isinstance(address, tuple):
            allow(address[0])
        return connect_ex(sock, address)

    def guarded_lookup(host, *args, **kwargs):
        allow(host)
        return lookup(host, *args, **kwargs)

    started = time.monotonic()
    with patch.object(Path, 'home', return_value=profile), \
         patch.object(socket.socket, 'connect', guarded_connect), \
         patch.object(socket.socket, 'connect_ex', guarded_connect_ex), \
         patch.object(socket, 'getaddrinfo', guarded_lookup):
        import serial
        import serial.tools.list_ports
        with patch.object(serial, 'Serial', side_effect=lambda *a, **k: deny('real COM access')), \
             patch.object(serial.tools.list_ports, 'comports', side_effect=lambda *a, **k: deny('COM enumeration')):
            import compact_art_host, turntable_face_host, artwork_fast_host, record_flip_host, turntable_paw_host
            native = output / 'native'
            compact_art_host.BUILD = native / 'compact'
            turntable_face_host.BUILD = native / 'face'
            artwork_fast_host.BUILD = native / 'rx'
            record_flip_host.BUILD = native / 'record'
            turntable_paw_host.BUILD = native / 'paw'
            if (snapshot / 'tests/lvgl_viewport_host.py').is_file():
                import lvgl_viewport_host
                lvgl_viewport_host.BUILD = native / 'lvgl'
            suite = unittest.defaultTestLoader.discover(str(snapshot / 'tests'), pattern='test_*.py')
            with (output / 'tests.log').open('w', encoding='utf-8') as log, \
                 contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    if worker_test_dependency(output) != test_dependency:
        raise ValueError('LVGL dependency changed during the offline tests')
    skips = [dict(test=t.id(), reason=r, category=classify_skip(t, r)) for t, r in result.skipped]
    summary = dict(classification='Offline source checks; no app runtime, firmware build or hardware acceptance',
                   python=sys.version, tests=result.testsRun,
                   explicit_includes=json.loads((output / 'inputs.json').read_text(encoding='utf-8'))['explicit_includes'],
                   passed=result.testsRun-len(result.errors)-len(result.failures)-len(skips),
                   errors=[dict(test=t.id(), detail=tb) for t, tb in result.errors],
                   failures=[dict(test=t.id(), detail=tb) for t, tb in result.failures],
                   skips=skips, blocked_operations=blocked, seconds=round(time.monotonic()-started, 3),
                   test_dependencies=test_dependency,
                   dependencies={d: importlib.metadata.version(d) for d in
                                 ('Pillow', 'psutil', 'pynput', 'pyserial', 'pystray', 'winrt-runtime', 'pyinstaller', 'tzdata')})
    summary['success'] = bool(result.testsRun and result.wasSuccessful() and not blocked and
                              all(s['category'] != 'unexpected' for s in skips))
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(f"{summary['passed']}/{summary['tests']} passed; {len(skips)} classified skips; "
          f"{len(result.errors)} errors; {len(result.failures)} failures. Evidence: {output}")
    for skip in skips:
        print(f"SKIP [{skip['category']}] {skip['test']}: {skip['reason']}")
    if not summary['success']:
        print((output / 'tests.log').read_text(encoding='utf-8')[-20000:])
    return 0 if summary['success'] else 1


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=ROOT / 'build/clean-checkout')
    parser.add_argument('--include-file', action='append', default=[], metavar='PATH',
                        help='Also snapshot a reviewed new source/test file before commit')
    parser.add_argument('--testdeps-root', type=Path, default=os.environ.get('BONGO_TEST_LVGL_ROOT'),
                        help='Verified fetch_lvgl_test_dependency.py output; copied into this check')
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return worker(args.worker.resolve())
    args.output_root.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='check-', dir=args.output_root)).resolve()
    source = output / 'source'
    source.mkdir()
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    included = []
    for name in args.include_file:
        try:
            path = source_path(name)
        except ValueError as error:
            parser.error(str(error))
        if path.relative_to(ROOT).parts[0] not in ('companion', 'src', 'tests', 'tools') or path.suffix not in ('.py', '.c', '.cpp', '.h', '.inc', '.ps1'):
            parser.error('--include-file is limited to source/test files in companion, src, tests or tools')
        ignored = subprocess.run(['git', 'check-ignore', '--quiet', '--', name], cwd=ROOT)
        if ignored.returncode != 1:
            parser.error('--include-file cannot include ignored/private paths: ' + name)
        canonical = path.relative_to(ROOT).as_posix()
        included.append(canonical)
        names.append(canonical)
    manifest = {}
    for name in sorted(set(filter(None, names))):
        path = source_path(name)
        # Tests need source and public fixtures, never a prebuilt application.
        if path.suffix.lower() in ('.exe', '.bin'):
            continue
        destination = source / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        manifest[name] = hashlib.sha256(destination.read_bytes()).hexdigest()
    (output / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    dependency = {}
    if args.testdeps_root:
        if 'tools/fetch_lvgl_test_dependency.py' not in manifest:
            parser.error('Review and --include-file tools/fetch_lvgl_test_dependency.py before using test dependencies')
        from fetch_lvgl_test_dependency import copy_verified_dependency
        try:
            dependency = copy_verified_dependency(args.testdeps_root, output / 'testdeps/lvgl')
        except (OSError, ValueError) as error:
            parser.error('LVGL test dependency rejected: ' + str(error))
    dependency_path = output / 'test-dependency-manifest.json'
    dependency_path.write_text(json.dumps(dependency, indent=2) + '\n', encoding='utf-8')
    inputs = dict(explicit_includes=sorted(set(included)), source_files=len(manifest),
                  omitted_prebuilt_extensions=['.exe', '.bin'],
                  test_dependency_manifest_sha256=hashlib.sha256(dependency_path.read_bytes()).hexdigest(),
                  runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (output / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n', encoding='utf-8')
    command = [sys.executable, '-B', str(source / 'tools/check_clean_checkout.py'), '--worker', str(output)]
    try:
        return subprocess.run(command, cwd=source, timeout=600).returncode
    except subprocess.TimeoutExpired:
        print(f'Checks exceeded 600 seconds. Evidence: {output}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
