"""Build actual pinned LVGL and extracted firmware adapters, never a renderer stub.

The optional Windows headers are declarations for the existing x64 C runtime.
They let the installed compiler run without installing a missing SDK/header pack.
Linux uses its normal system headers. No hardware, serial, download or profile I/O.
"""
from __future__ import annotations

import ctypes
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/lvgl-viewport-tests'
FUNCTIONS = (
    'mediaRecordVisible', 'createMediaArtViewport', 'syncMediaArtViewport',
    'drawMediaTurntableLayer', 'updateMediaTurntableLayers',
    'syncMediaArtworkDescriptor', 'updateMediaRecordFlip', 'updateMediaVinyl',
    'refreshFocusMediaLayout',
)


def extract(source, name):
    match = re.search(r'^(?:static )?(?:void|bool) ' + name + r'\([^)]*\) \{', source, re.M)
    if not match:
        raise AssertionError('Firmware adapter missing: ' + name)
    depth = 1
    at = match.end()
    while depth:
        depth += (source[at] == '{') - (source[at] == '}')
        at += 1
    return source[match.start():at]


def run(command, cwd, log):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, errors='replace')
    with log.open('a', encoding='utf-8') as stream:
        stream.write(result.stdout + result.stderr)
    if result.returncode:
        raise AssertionError(f'Host compile failed ({result.returncode}):\n' +
                             (result.stdout + result.stderr)[-6500:])


def library():
    dependency = os.environ.get('BONGO_TEST_LVGL_ROOT')
    if not dependency:
        raise AssertionError('BONGO_TEST_LVGL_ROOT must name verified LVGL 8.3.11; no download/skip')
    lvgl = Path(dependency).resolve()
    files = [ROOT / 'lv_conf.h', ROOT / 'src/bongo_cat_featured.inc',
             ROOT / 'tests/lvgl_viewport_host.py', ROOT / 'tests/lvgl_viewport_test.cpp',
             ROOT / 'tests/lvgl_viewport_support.c', *sorted((ROOT / 'src').glob('*.h')),
             *sorted((ROOT / 'tests/lvgl_test_abi').glob('*')), lvgl / 'lvgl.h',
             *sorted((lvgl / 'src').rglob('*.c')), *sorted((lvgl / 'src').rglob('*.h'))]
    digest = hashlib.sha256()
    for file in files:
        digest.update(str(file).encode('utf-8'))
        digest.update(file.read_bytes())
    return _library(str(BUILD.resolve()), str(lvgl), digest.hexdigest())


@lru_cache(maxsize=4)
def _library(build_root, dependency, input_sha256):
    # Cache and DLL path both include BUILD + actual inputs. A different fresh
    # checkout/output or edited source can never reuse the first DLL by mistake.
    BUILD = Path(build_root) / input_sha256[:16]
    lvgl = Path(dependency)
    header = (lvgl / 'lvgl.h').read_text(encoding='utf-8')
    for name, value in (('MAJOR', 8), ('MINOR', 3), ('PATCH', 11)):
        if not re.search(r'#define LVGL_VERSION_' + name + r'\s+' + str(value) + r'\b', header):
            raise AssertionError('Expected LVGL 8.3.11: ' + name)
    # The fresh offline runner verifies the whole dependency against its pinned
    # archive. Keep a separate actual-input hash receipt for local focused runs.
    sources = sorted((lvgl / 'src').rglob('*.c'))
    if not sources:
        raise AssertionError('LVGL C sources missing')
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / 'objects').mkdir(exist_ok=True)
    (BUILD / 'dependency-inputs.json').write_text(json.dumps({
        str(p.relative_to(lvgl)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted([lvgl / 'lvgl.h', *(lvgl / 'src').rglob('*.h'), *sources])
    }, indent=2), encoding='utf-8')
    config = (ROOT / 'lv_conf.h').read_text(encoding='utf-8')
    assert config.count('#define LV_TICK_CUSTOM 1') == 1
    config = config.replace('#define LV_TICK_CUSTOM 1', '#define LV_TICK_CUSTOM 0')
    config = config.replace('#define LV_ASSERT_HANDLER_INCLUDE <stdint.h>',
                            '#define LV_ASSERT_HANDLER_INCLUDE "host_assert.h"')
    config = config.replace('#define LV_ASSERT_HANDLER while(1);',
                            '#define LV_ASSERT_HANDLER vp_assert_fail(__FILE__, __LINE__);')
    (BUILD / 'lv_conf.h').write_text(config, encoding='utf-8')
    (BUILD / 'host_assert.h').write_text(
        '#ifdef __cplusplus\nextern "C" {\n#endif\n'
        'void vp_assert_fail(const char *, int);\n'
        '#ifdef __cplusplus\n}\n#endif\n', encoding='utf-8')
    source = (ROOT / 'src/bongo_cat_featured.inc').read_text(encoding='utf-8')
    (BUILD / 'viewport_fixture.inc').write_text('\n\n'.join(extract(source, n) for n in FUNCTIONS), encoding='utf-8')
    scene = extract(source, 'createMediaScreen')
    scene = scene[scene.index('    media_art_box = lv_obj_create(media_screen);'):
                  scene.index('    loadGenericVinyl();')]
    scene = scene.replace('for (lv_obj_t *layer : {media_arm_layer, media_paw_layer})',
                          'lv_obj_t *layers[] = {media_arm_layer, media_paw_layer};\n    for (lv_obj_t *layer : layers)')
    scene = scene.replace('for (lv_obj_t *time_label_item : {media_elapsed_label, media_duration_label})',
                          'lv_obj_t *times[] = {media_elapsed_label, media_duration_label};\n    for (lv_obj_t *time_label_item : times)')
    (BUILD / 'viewport_scene.inc').write_text(scene, encoding='utf-8')
    # Exact production glyphs/metrics/cache data; spell C++ nullptr as C NULL.
    font = (ROOT / 'src/media_swedish_font.h').read_text(encoding='utf-8')
    (BUILD / 'viewport_font_data.h').write_text(
        font[:font.index('inline lv_font_t mediaSwedishFont')].replace('nullptr', 'NULL'), encoding='utf-8')
    log = BUILD / 'compile.log'
    log.write_text('', encoding='utf-8')
    support = ROOT / 'tests/lvgl_viewport_support.c'
    fixture = ROOT / 'tests/lvgl_viewport_test.cpp'
    if os.name == 'nt':
        choices = sorted(Path('C:/Program Files/Microsoft Visual Studio').glob(
            '*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe'))
        if not choices:
            raise AssertionError('Existing x64 compiler is required for real LVGL raster tests')
        compiler = choices[-1]
        vc = compiler.parents[3]
        kits = sorted(Path('C:/Program Files (x86)/Windows Kits/10/Lib').glob('*/ucrt/x64/ucrt.lib'))
        runtime = next((p for p in (vc / 'lib/x64', vc / 'lib/onecore/x64')
                        if (p / 'vcruntime.lib').is_file()), None)
        if not kits or runtime is None:
            raise AssertionError('Existing Windows x64 CRT libraries are required')
        common = [str(compiler), '/nologo', '/utf-8', '/O2', '/GS-', '/Gs9999999', '/Zl',
                  '/DLV_CONF_INCLUDE_SIMPLE=1', '/I' + str(ROOT / 'tests/lvgl_test_abi'),
                  '/I' + str(BUILD), '/I' + str(lvgl)]
        objects = []
        # Unique outputs avoid collisions between e.g. fonts/widgets of the same name.
        for index, unit in enumerate([*sources, support, fixture]):
            output = BUILD / 'objects' / f'{index:03}.obj'
            run([*common, '/TP' if unit == fixture else '/TC',
                 '/std:c++14' if unit == fixture else '/std:c11', '/we4013', '/c',
                 str(unit), '/Fo' + str(output)], BUILD, log)
            objects.append(output)
        dll = BUILD / 'viewport.dll'
        # Use cl's existing linker driver; the offline runner need not allow a
        # second arbitrary executable. UCRT supplies the real malloc/string/math.
        args = ['/DLL', '/NOENTRY', '/NODEFAULTLIB',
                '/OUT:' + str(dll), '/IMPLIB:' + str(BUILD / 'viewport.lib'),
                str(kits[-1]), str(runtime / 'vcruntime.lib'), str(runtime / 'oldnames.lib'),
                str(kits[-1].parents[2] / 'um/x64/kernel32.lib')]
        response = BUILD / 'link.rsp'
        response.write_text('\n'.join('"' + str(obj) + '"' for obj in objects), encoding='utf-8')
        run([str(compiler), '/nologo', '@' + str(response), '/link', *args], BUILD, log)
    else:
        cc, cxx = shutil.which('gcc'), shutil.which('g++')
        if not cc or not cxx:
            raise AssertionError('Existing gcc/g++ are required for real LVGL raster tests')
        common = ['-fPIC', '-O2', '-DLV_CONF_INCLUDE_SIMPLE=1', '-I', str(BUILD), '-I', str(lvgl)]
        objects = []
        for index, unit in enumerate([*sources, support, fixture]):
            output = BUILD / 'objects' / f'{index:03}.o'
            run([cxx if unit == fixture else cc, *common,
                 '-std=c++14' if unit == fixture else '-std=c99', '-c', str(unit), '-o', str(output)], BUILD, log)
            objects.append(output)
        dll = BUILD / 'viewport.so'
        run([cxx, '-shared', *map(str, objects), '-lm', '-o', str(dll)], BUILD, log)
    result = ctypes.CDLL(str(dll))
    result.vp_run.argtypes = [ctypes.c_int]
    result.vp_run.restype = ctypes.c_int
    result.vp_error.restype = ctypes.c_char_p
    result.vp_measure.argtypes = [ctypes.c_int]
    result.vp_measure.restype = ctypes.c_uint64
    return result
