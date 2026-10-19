"""Run real C++ countdown/cache/UI-adapter checks and firmware font/layout checks."""
import json
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build/turntable-arm-tempo-2026-10-18/focus-fixtures'
sys.path.insert(0, str(ROOT / "tools"))
import export_ui_visuals as visuals


class CountdownTests(unittest.TestCase):
    def _run_cpp_case(self, stem, names):
        build = BUILD
        build.mkdir(parents=True, exist_ok=True)
        source = visuals.FIRMWARE.read_text(encoding="utf-8")
        functions = []
        for name in names:
            start = re.search(r"(?:lv_obj_t\s*\*|void)\s*" + name + r"\([^)]*\)\s*\{", source)
            self.assertIsNotNone(start)
            functions.append(start[0] + visuals.section(source, name) + "}\n")
        constants = "\n".join(line for line in source.splitlines() if re.match(
            r"#define (?:TOUCH_PRESSURE_THRESHOLD|MEDIA_MULTI_TAP_WINDOW_MS|MEDIA_SWIPE_THRESHOLD|FOCUS_TAP_MOVE_MAX_RAW) ", line))
        (build / (stem + "_fixture.inc")).write_text(constants + "\n" + "\n".join(functions), encoding="utf-8")
        compiler = shutil.which("g++") or shutil.which("clang++")
        executable = build / (stem + ".exe")
        if compiler:
            command = [compiler, "-std=c++14", "-Wall", "-Wextra", "-Werror", "-I", str(build),
                       str(ROOT / "tests" / (stem + ".cpp")), "-o", str(executable)]
        else:
            choices = sorted(Path("C:/Program Files/Microsoft Visual Studio").glob("*/*/VC/Auxiliary/Build/vcvars64.bat"))
            if not choices or not (choices[-1].parent / "vcvarsall.bat").exists():
                self.skipTest("Host C++ runtime test NOT RUN: complete MSVC setup/headers unavailable")
            batch = build / "compile.cmd"
            batch.write_text(f'@echo off\ncall "{choices[-1]}" >nul\n'
                             'if errorlevel 1 exit /b 1\n'
                             f'cl /nologo /std:c++14 /EHsc /W4 /WX /I"{build}" '
                             f'/Fo"{build / "focus_countdown_test.obj"}" /Fe"{executable}" '
                             f'"{ROOT / "tests" / (stem + ".cpp")}"\n', encoding="utf-8")
            command = ["cmd.exe", "/d", "/c", str(batch)]
        compiled = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        run = subprocess.run([str(executable)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        print(run.stdout.strip())

    def test_cpp_state_cache_and_ui_calls(self):
        self._run_cpp_case("focus_countdown_test", ("createFocusCountdownLabel", "setFocusCountdownVisible",
            "refreshFocusMediaLayout", "refreshFocusCountdownTheme", "activateMediaArtwork", "toggleMediaCatMode",
            "refreshFocusCountdownPresentation", "refreshFocusCountdown"))

    def test_cpp_actual_touch_handler_and_media_dispatch(self):
        self._run_cpp_case("focus_status_touch_test", ("hideFeatureOverlay", "toggleFeatureOverlay", "queueMediaTap",
            "serviceMediaTaps", "setFocusState", "serviceFocusTimer", "handleFocusStatusTap", "handleTouchFeature"))

    def test_actual_fonts_and_all_countdown_widths(self):
        layout = visuals.focus_countdown_layout(visuals.FIRMWARE.read_text(encoding="utf-8"))
        self.assertEqual(layout["labels_xywh"], {"bongo_phase": [5, 65, 96, 17], "bongo_time": [117, 65, 96, 17],
                         "bongo_pause_0": [221, 69, 3, 11], "bongo_pause_1": [227, 69, 3, 11],
                         "player_phase": [52, 25, 52, 16], "player_time": [112, 24, 56, 18],
                         "player_pause_0": [176, 28, 3, 10], "player_pause_1": [182, 28, 3, 10]})
        self.assertEqual(layout["max_text_widths"], {"bongo_phase": 96, "bongo_time": 96,
                                                   "player_phase": 51, "player_time": 54})
        self.assertEqual(layout["player_card_xywh"], [40, 20, 160, 26])
        self.assertEqual(layout["active_media"], {"box_xywh": [48, 54, 144, 144], "radius": 72, "art_zoom": 320, "cat_zoom": 560})
        self.assertEqual(layout["inactive_media"], {"box_xywh": [34, 26, 172, 172], "radius": 86, "art_zoom": 384, "cat_zoom": 672})
        self.assertIn((0, 82, 240, 238), layout["reserved_xywh"]["bongo"])
        self.assertEqual(layout["hit_xywh_half_open"], {"bongo": [5, 62, 230, 20], "player": [36, 16, 168, 37]})

    def test_layout_rejects_real_collisions(self):
        source = visuals.FIRMWARE.read_text(encoding="utf-8")
        for bad_source in (source.replace("bongo_focus_time_label, 117, 65", "bongo_focus_time_label, 117, 66"),
                           source.replace("bongo_focus_phase_label, 5, 65", "bongo_focus_phase_label, 5, 61"),
                           source.replace("media_focus_phase_label, 11, 4", "media_focus_phase_label, 11, 17")):
            with self.assertRaises(ValueError):
                visuals.focus_countdown_layout(bad_source)

    def test_historical_seek_preview_matches_83cc460_sources_and_pinned_fonts(self):
        preview = ROOT / "visuals/media-seek-implemented-2026-10-12"
        manifest = json.loads((preview / "manifest.json").read_text(encoding="utf-8"))
        if any(not (ROOT/path).exists() for path in manifest['source_sha256'] if path.startswith('.pio/')):
            self.skipTest('Historical seek preview font archive absent')
        self.assertEqual(len(manifest["views"]), 22)
        for path, digest in manifest["source_sha256"].items():
            if path.startswith('.pio/'):
                self.assertEqual(visuals.sha256(ROOT / path), digest, path)
            else:
                # Git retains LF; the historical Windows manifest recorded
                # checkout bytes. Accept only LF/CRLF forms of that exact blob.
                data = subprocess.check_output(['git', 'show', '83cc460:' + path], cwd=ROOT)
                self.assertIn(digest.lower(), {hashlib.sha256(data).hexdigest(),
                    hashlib.sha256(data.replace(b'\n', b'\r\n')).hexdigest()}, path)
        for view in manifest["views"]:
            path = preview / view["file"]
            with visuals.Image.open(path) as image:
                self.assertEqual(image.size, (240, 320))
            self.assertEqual(visuals.sha256(path), view["sha256"])

    def test_player_presentation_preserved_from_08a(self):
        if not (ROOT / "build/focus-status-tap-2026-10-12/baseline/src/bongo_cat_featured.inc").exists():
            self.skipTest('Historical player presentation source archive absent')
        current = json.loads((ROOT / "visuals/media-seek-implemented-2026-10-12/manifest.json").read_text())
        previous = json.loads((ROOT / "visuals/focus-countdown/ui3-implemented-2026-10-12/manifest.json").read_text())
        before = {view["id"]: view["sha256"] for view in previous["views"]}
        for view in current["views"]:
            if view["id"].startswith("player_"):
                self.assertEqual(view["sha256"], before[view["id"]])
        source = visuals.FIRMWARE.read_text(encoding="utf-8")
        saved = (ROOT / "build/focus-status-tap-2026-10-12/baseline/src/bongo_cat_featured.inc").read_text(encoding="utf-8")
        for function in ("createMediaScreen", "refreshFocusMediaLayout", "toggleMediaCatMode", "refreshMediaUi"):
            actual = visuals.section(source, function)
            # Only approved font/one-time buffer setup/settle-before-resize and
            # draw-DJ-before-unhide changes are excluded from presentation equality.
            actual = actual.replace('lv_font_media_swedish_', 'lv_font_montserrat_')
            if function == 'createMediaScreen':
                actual = actual.replace('    allocateMediaRecordPixels();\n', '')
                # Approved turntable sprites are screen children so a full
                # withdrawal escapes the circular viewport. Keep all existing
                # labels/cards/canvas/layout identical after excluding that block.
                start = actual.index('    media_art_image = lv_img_create(media_screen);')
                end = actual.index('    lv_obj_add_flag(media_art_image, LV_OBJ_FLAG_HIDDEN);', start)
                layers = actual[start:end]
                self.assertIn('LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_SCROLLABLE', layers)
                self.assertIn('drawMediaTurntableLayer, LV_EVENT_DRAW_MAIN', layers)
                actual = actual[:start] + '    media_art_image = lv_img_create(media_art_box);\n' + actual[end:]
            if function == 'refreshFocusMediaLayout':
                start = actual.index('    lv_obj_set_pos(media_art_image, layout.x')
                end = actual.index('    lv_obj_center(media_cat_canvas);', start)
                self.assertIn('layout.y + layout.size/2', actual[start:end])
                self.assertIn('lv_obj_add_flag(media_paw_layer, LV_OBJ_FLAG_HIDDEN)', actual[start:end])
                actual = actual[:start] + '    lv_obj_center(media_art_image);\n' + actual[end:]
            actual = actual.replace('    media_record_flip.frame(millis(), false);\n    media_record_dirty = true;\n', '')
            actual = actual.replace('    media_record_dirty = true;  // Also restores generic after sharing the OOM scratch.\n', '')
            actual = actual.replace('        renderMediaCat();\n        lv_obj_clear_flag(media_cat_canvas, LV_OBJ_FLAG_HIDDEN);',
                                    '        lv_obj_clear_flag(media_cat_canvas, LV_OBJ_FLAG_HIDDEN);\n        renderMediaCat();')
            self.assertEqual(actual, visuals.section(saved, function), function)

    def test_bongo_protected_pixels_and_cue_color(self):
        preview = ROOT / "visuals/media-seek-implemented-2026-10-12"
        manifest = json.loads((preview / "manifest.json").read_text())
        source = visuals.FIRMWARE.read_text(encoding="utf-8")
        for view in manifest["views"]:
            if not view["id"].startswith("bongo_"):
                continue
            sample = {**visuals.SAMPLE, "cpu_percent": 100, "ram_percent": 100, "wpm": 200} if view["id"] == "bongo_long_paused" else visuals.SAMPLE
            base = visuals.bongo_base(source, sample)
            image = visuals.Image.open(preview / view["file"])
            for crop in ((0, 0, 240, 62), (0, 82, 240, 320)):
                self.assertEqual(image.crop(crop).tobytes(), base.crop(crop).tobytes(), view["id"])
        for cue, ordinary in (("bongo_compact_cue_paused", "bongo_break_paused"), ("bongo_cyan_cue", "bongo_break")):
            image = visuals.Image.open(preview / "composed" / (cue + ".png"))
            normal = visuals.Image.open(preview / "composed" / (ordinary + ".png"))
            self.assertEqual(image.crop((101, 62, 240, 82)).tobytes(), normal.crop((101, 62, 240, 82)).tobytes())

    def test_source_layout_and_cue_paths(self):
        source = visuals.FIRMWARE.read_text(encoding="utf-8")
        projection = visuals.section(source, "updateMediaRecordFlip")
        self.assertIn("const FocusMediaLayout layout = focusMediaLayout(media_focus_layout_active)", projection)
        self.assertIn("lv_img_set_zoom(media_art_image, layout.art_zoom", projection)
        self.assertIn('media_record_flip.artwork', visuals.section(source, 'activateMediaArtwork'))
        toggle = visuals.section(source, "toggleMediaCatMode")
        self.assertNotIn("lv_img_set_zoom", toggle)
        self.assertNotIn("lv_img_set_zoom", visuals.section(source, "refreshMediaUi"))
        refresh = visuals.section(source, "refreshFocusCountdown")
        self.assertRegex(refresh, r"if \(before.visible != after.visible\) \{[\s\S]*?refreshFocusMediaLayout\(after.visible\)")
        cue = visuals.section(source, "updateFocusCue")
        self.assertIn("if (integrated) lv_obj_add_flag(focus_completion_banner, LV_OBJ_FLAG_HIDDEN)", cue)
        self.assertIn("focusCountdownIntegratedCue(", cue)
        presentation = visuals.section(source, "refreshFocusCountdownPresentation")
        self.assertNotIn("lv_obj_set_pos", presentation)
        self.assertNotIn("lv_label_set_text", presentation)
        self.assertNotIn("focusCountdownNumberFont", source)
        self.assertNotIn("lv_font_unscii_8", source)


if __name__ == "__main__":
    unittest.main()
