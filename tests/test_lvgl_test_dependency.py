"""Small synthetic archives exercise LVGL test-source integrity without network."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fetch_lvgl_test_dependency as dependency
import check_clean_checkout as checks


def synthetic_archive(changes=None, extra=()):
    files = {'lvgl.h': b'#define LVGL_VERSION_MAJOR 8\n#define LVGL_VERSION_MINOR 3\n#define LVGL_VERSION_PATCH 11\n',
             'library.json': b'{"version":"8.3.11"}', 'LICENCE.txt': b'MIT test fixture',
             'lv_conf_template.h': b'/* test configuration */',
             'src/test.c': b'void lv_test(void) {}', 'src/test.h': b'void lv_test(void);'}
    files.update(changes or {})
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name, content in files.items():
            member = tarfile.TarInfo('lvgl-' + dependency.COMMIT + '/' + name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
        for member, content in extra:
            archive.addfile(member, io.BytesIO(content))
    return stream.getvalue(), files


@contextlib.contextmanager
def synthetic_pin(data, files):
    with patch.multiple(dependency, ARCHIVE_BYTES=len(data),
                        ARCHIVE_SHA256=hashlib.sha256(data).hexdigest(),
                        SOURCE_FILES=len(files), SOURCE_BYTES=sum(map(len, files.values()))):
        yield


class LvglTestDependencyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='lvgl-dependency-test-')
        self.root = Path(self.temporary.name)
        temporary_parent = Path(tempfile.gettempdir()).resolve()
        def cleanup():
            if not self.root.resolve().is_relative_to(temporary_parent):
                raise AssertionError('Temporary dependency cleanup escaped its test directory')
            self.temporary.cleanup()
        self.addCleanup(cleanup)

    def create(self, destination, data, files):
        content, manifest = dependency.archive_sources(data)
        return dependency.write_dependency(destination, data, content, manifest)

    def test_unknown_hash_rejected_before_archive_parser(self):
        data, files = synthetic_archive()
        with synthetic_pin(data, files), patch.object(dependency.tarfile, 'open') as parser:
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                dependency.archive_sources(data[:-1] + bytes([data[-1] ^ 1]))
            parser.assert_not_called()

    def test_oversized_archive_rejected(self):
        data, files = synthetic_archive()
        with synthetic_pin(data, files), self.assertRaisesRegex(ValueError, 'size/SHA-256'):
            dependency.archive_sources(data + b'x')

    def test_path_traversal_rejected(self):
        member = tarfile.TarInfo('lvgl-' + dependency.COMMIT + '/src/../../escape.h')
        member.size = 1
        data, files = synthetic_archive(extra=[(member, b'x')])
        with synthetic_pin(data, files), self.assertRaisesRegex(ValueError, 'Unsafe'):
            dependency.archive_sources(data)

    def test_archive_symlink_rejected(self):
        member = tarfile.TarInfo('lvgl-' + dependency.COMMIT + '/src/link.h')
        member.type, member.linkname = tarfile.SYMTYPE, '../../outside.h'
        data, files = synthetic_archive(extra=[(member, b'')])
        with synthetic_pin(data, files), self.assertRaisesRegex(ValueError, 'Unsafe'):
            dependency.archive_sources(data)

    def test_duplicate_case_path_rejected(self):
        member = tarfile.TarInfo('lvgl-' + dependency.COMMIT + '/src/TEST.h')
        member.size = 1
        data, files = synthetic_archive(extra=[(member, b'x')])
        with synthetic_pin(data, files), self.assertRaisesRegex(ValueError, 'duplicate'):
            dependency.archive_sources(data)

    def test_oversized_selected_member_rejected(self):
        member = tarfile.TarInfo('lvgl-' + dependency.COMMIT + '/src/large.h')
        content = b'x' * (2 * 1024 * 1024 + 1)
        member.size = len(content)
        data, files = synthetic_archive(extra=[(member, content)])
        with synthetic_pin(data, files), self.assertRaisesRegex(ValueError, 'source-file size'):
            dependency.archive_sources(data)

    def test_wrong_header_or_package_version_rejected(self):
        for changes, expected in (({'lvgl.h': b'#define LVGL_VERSION_MAJOR 9\n'}, 'header version'),
                                  ({'library.json': b'{"version":"9.0.0"}'}, 'package version')):
            with self.subTest(expected=expected):
                data, files = synthetic_archive(changes)
                with synthetic_pin(data, files), self.assertRaisesRegex(ValueError, expected):
                    dependency.archive_sources(data)

    def test_mutated_source_and_self_authored_manifest_rejected(self):
        data, files = synthetic_archive()
        source = self.root / 'source'
        with synthetic_pin(data, files):
            manifest = self.create(source, data, files)
            changed = b'changed C source'
            (source / 'src/test.c').write_bytes(changed)
            manifest['files']['src/test.c'] = hashlib.sha256(changed).hexdigest()
            (source / dependency.MANIFEST_NAME).write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'differs from pinned archive'):
                dependency.verify_dependency(source)

    def test_extra_file_or_directory_rejected(self):
        data, files = synthetic_archive()
        with synthetic_pin(data, files):
            for name, directory in (('unexpected.exe', False), ('unexpected', True)):
                source = self.root / name.replace('.', '-')
                self.create(source, data, files)
                extra = source / name
                extra.mkdir() if directory else extra.write_bytes(b'not executable')
                with self.assertRaisesRegex(ValueError, 'extra'):
                    dependency.verify_dependency(source)

    def test_copy_is_rechecked_against_pinned_content(self):
        data, files = synthetic_archive()
        source, target = self.root / 'source', self.root / 'target'
        original_read = Path.read_bytes
        def corrupted_read(path):
            return b'copy fault' if path == target / 'src/test.c' else original_read(path)
        with synthetic_pin(data, files):
            self.create(source, data, files)
            with patch.object(Path, 'read_bytes', corrupted_read), self.assertRaisesRegex(ValueError, 'differs'):
                dependency.copy_verified_dependency(source, target)

    def test_tree_junction_rejected_without_following_it(self):
        data, files = synthetic_archive()
        source = self.root / 'source'
        with synthetic_pin(data, files):
            self.create(source, data, files)
            with patch.object(Path, 'is_junction', lambda path: path == source / 'src'), \
                 self.assertRaisesRegex(ValueError, 'symlink or special file'):
                dependency.verify_dependency(source)

    def test_worker_dependency_verification_and_copy_never_fetch(self):
        data, files = synthetic_archive()
        source, output = self.root / 'source', self.root / 'check'
        with synthetic_pin(data, files), patch.dict(os.environ, {}, clear=False), \
             patch.object(dependency.urllib.request, 'build_opener', side_effect=AssertionError('network forbidden')):
            self.create(source, data, files)
            manifest = dependency.copy_verified_dependency(source, output / 'testdeps/lvgl')
            (output / 'test-dependency-manifest.json').write_text(json.dumps(manifest))
            self.assertEqual(checks.worker_test_dependency(output), manifest)
            self.assertEqual(Path(os.environ['BONGO_TEST_LVGL_ROOT']), (output / 'testdeps/lvgl').resolve())
            manifest['commit'] = 'untrusted'
            (output / 'test-dependency-manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'frozen manifest'):
                checks.worker_test_dependency(output)

    def test_redirect_refused_before_followup_request(self):
        handler = dependency.RejectRedirects()
        with self.assertRaisesRegex(ValueError, 'redirect'):
            handler.redirect_request(None, None, 302, 'Found', {}, 'https://untrusted.invalid/')

    def test_download_size_bound_with_mock_response(self):
        data, files = synthetic_archive()
        response = io.BytesIO(data + b'x')
        response.geturl = lambda: dependency.ARCHIVE_URL
        with synthetic_pin(data, files), patch.object(dependency.urllib.request, 'build_opener') as opener:
            opener.return_value.open.return_value = response
            with self.assertRaisesRegex(ValueError, 'exceeds the pinned size'):
                dependency.fetch_archive()


if __name__ == '__main__':
    unittest.main()
