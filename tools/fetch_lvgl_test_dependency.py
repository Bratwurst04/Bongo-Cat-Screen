"""Fetch or verify pinned public LVGL sources before running offline raster tests.

python -B tools/fetch_lvgl_test_dependency.py --output-dir build/testdeps/lvgl
The output must be new. --archive PATH reuses an already downloaded exact archive.
Only C sources/headers and four public metadata files are extracted; nothing runs.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import urllib.request


VERSION = '8.3.11'
COMMIT = '74d0a816a440eea53e030c4f1af842a94f7ce3d3'
ARCHIVE_URL = 'https://codeload.github.com/lvgl/lvgl/tar.gz/' + COMMIT
ARCHIVE_SHA256 = '9a28236db180e5634c32acaef10ffaf242f2b52c71ad63db82f238b8b76a1936'
ARCHIVE_BYTES = 25643756
ARCHIVE_NAME = 'lvgl-8.3.11.tar.gz'
MANIFEST_NAME = 'dependency-manifest.json'
ROOT_FILES = {'lvgl.h', 'lv_conf_template.h', 'library.json', 'LICENCE.txt'}
SOURCE_FILES = 359
SOURCE_BYTES = 11424755


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def archive_sources(data):
    """Derive canonical content from pinned bytes, never a caller's manifest."""
    if len(data) != ARCHIVE_BYTES or sha256(data) != ARCHIVE_SHA256:
        raise ValueError('LVGL archive size/SHA-256 does not match the reviewed pin')
    files, seen, unpacked = {}, set(), 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for count, member in enumerate(archive, 1):
            if count > 2000 or member.size < 0:
                raise ValueError('LVGL archive member bound exceeded')
            unpacked += member.size
            if unpacked > 128 * 1024 * 1024:
                raise ValueError('LVGL archive unpacked-size bound exceeded')
            name = member.name.rstrip('/')
            parts = name.split('/')
            if (not parts or parts[0] != 'lvgl-' + COMMIT or
                    any(p in ('', '.', '..') or ':' in p or '\\' in p for p in parts) or
                    name.casefold() in seen or not (member.isfile() or member.isdir())):
                raise ValueError('Unsafe or duplicate LVGL archive member: ' + name)
            seen.add(name.casefold())
            if member.isdir():
                continue
            relative = PurePosixPath(*parts[1:])
            selected = (relative.parts[:1] == ('src',) and relative.suffix in ('.c', '.h') or
                        len(relative.parts) == 1 and relative.name in ROOT_FILES)
            if not selected:
                continue
            if member.size > 2 * 1024 * 1024:
                raise ValueError('LVGL source-file size bound exceeded')
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError('Missing LVGL archive file data')
            content = stream.read(member.size + 1)
            if len(content) != member.size:
                raise ValueError('Truncated LVGL archive member')
            files[relative.as_posix()] = content
    if len(files) != SOURCE_FILES or sum(map(len, files.values())) != SOURCE_BYTES:
        raise ValueError('LVGL selected source set does not match the reviewed pin')
    header = files['lvgl.h'].decode('utf-8')
    for name, expected in (('MAJOR', '8'), ('MINOR', '3'), ('PATCH', '11')):
        if not re.search(r'^#define LVGL_VERSION_' + name + r'\s+' + expected + r'\s*$', header, re.M):
            raise ValueError('LVGL header version does not match 8.3.11')
    if json.loads(files['library.json'])['version'] != VERSION:
        raise ValueError('LVGL package version does not match 8.3.11')
    manifest = dict(name='lvgl', version=VERSION, commit=COMMIT,
                    archive_url=ARCHIVE_URL, archive_sha256=ARCHIVE_SHA256,
                    archive_bytes=ARCHIVE_BYTES,
                    selection='src/**/*.c, src/**/*.h, ' + ', '.join(sorted(ROOT_FILES)),
                    files={name: sha256(content) for name, content in sorted(files.items())})
    return files, manifest


def is_link(path):
    return path.is_symlink() or path.is_junction()


def regular_file(path):
    if is_link(path) or not path.is_file():
        raise ValueError('Expected a regular dependency file: ' + str(path))


def read_archive(path):
    regular_file(path)
    if path.stat().st_size != ARCHIVE_BYTES:
        raise ValueError('LVGL archive size does not match the reviewed pin')
    return path.read_bytes()


def verify_dependency(root):
    """Check every retained file against content derived from the pinned archive."""
    root = Path(root)
    if any(is_link(path) for path in (root, *root.parents)) or not root.is_dir():
        raise ValueError('LVGL test dependency must be a regular directory')
    data = read_archive(root / ARCHIVE_NAME)
    files, manifest = archive_sources(data)
    actual = set()
    directories = {parent.as_posix() for name in files for parent in PurePosixPath(name).parents
                   if parent != PurePosixPath('.')}
    for path in root.rglob('*'):
        if is_link(path) or not (path.is_dir() or path.is_file()):
            raise ValueError('LVGL dependency contains a symlink or special file')
        if path.is_file():
            name = path.relative_to(root).as_posix()
            if name not in files and name not in (ARCHIVE_NAME, MANIFEST_NAME):
                raise ValueError('LVGL dependency tree contains an extra file')
            actual.add(name)
        elif path.relative_to(root).as_posix() not in directories:
            raise ValueError('LVGL dependency tree contains an extra directory')
    if actual != set(files) | {ARCHIVE_NAME, MANIFEST_NAME}:
        raise ValueError('LVGL dependency tree contains missing or extra files')
    for name, content in files.items():
        if (root / name).read_bytes() != content:
            raise ValueError('LVGL dependency file differs from pinned archive: ' + name)
    if json.loads((root / MANIFEST_NAME).read_text(encoding='utf-8')) != manifest:
        raise ValueError('LVGL dependency manifest differs from pinned archive')
    return data, files, manifest


def write_dependency(destination, data, files, manifest):
    destination = Path(destination)
    if any(is_link(path) for path in (destination, *destination.parents)):
        raise ValueError('LVGL dependency output cannot traverse a symlink or junction')
    destination.mkdir(parents=True, exist_ok=False)
    for name, content in sorted(files.items()):
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as output:
            output.write(content)
    with (destination / ARCHIVE_NAME).open('xb') as output:
        output.write(data)
    with (destination / MANIFEST_NAME).open('x', encoding='utf-8') as output:
        output.write(json.dumps(manifest, indent=2) + '\n')
    verify_dependency(destination)
    return manifest


def copy_verified_dependency(source, destination):
    data, files, manifest = verify_dependency(source)
    return write_dependency(destination, data, files, manifest)


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        raise ValueError('Unexpected LVGL archive redirect')


def fetch_archive():
    request = urllib.request.Request(ARCHIVE_URL, headers={'User-Agent': 'Bongo-Cat-LVGL-test-dependency'})
    chunks, size = [], 0
    opener = urllib.request.build_opener(RejectRedirects())
    with opener.open(request, timeout=30) as response:
        if response.geturl() != ARCHIVE_URL:
            raise ValueError('Unexpected LVGL archive redirect')
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > ARCHIVE_BYTES:
                raise ValueError('LVGL download exceeds the pinned size')
            chunks.append(chunk)
    return b''.join(chunks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--output-dir', type=Path)
    target.add_argument('--verify', type=Path)
    parser.add_argument('--archive', type=Path, help='Reuse the exact pinned archive without network')
    args = parser.parse_args()
    try:
        if args.verify:
            if args.archive:
                parser.error('--archive is only used with --output-dir')
            _, _, manifest = verify_dependency(args.verify)
            destination = args.verify
        else:
            data = read_archive(args.archive) if args.archive else fetch_archive()
            files, manifest = archive_sources(data)
            destination = args.output_dir
            write_dependency(destination, data, files, manifest)
    except (OSError, ValueError, tarfile.TarError) as error:
        parser.exit(1, 'LVGL test dependency rejected: ' + str(error) + '\n')
    print(f"Verified LVGL {manifest['version']} ({len(manifest['files'])} source files): {destination.resolve()}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
