"""Bongo-only design reference; uses native glyphs and writes only this folder."""
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import export_ui_visuals as v

OUT = Path(__file__).resolve().parent
SOURCE = v.FIRMWARE.read_text(encoding="utf-8")
FONT = v.lvgl_ascii_font("unscii_16")
BLACK = (0, 0, 0)
GEOMETRY = {
    "phase": [5, 65, 96, 17],
    "time": [117, 65, 96, 17],
    "pause_bars": [[221, 69, 3, 11], [227, 69, 3, 11]],
}
HIT_REGIONS = {"bongo": [5, 62, 230, 20], "player": [36, 16, 168, 37]}
RESERVED = [[5, 5, 144, 17], [5, 25, 144, 17], [5, 45, 128, 17],
            [155, 5, 80, 17], [0, 82, 240, 238]]


def disjoint(a, b):
    x, y, w, h = a
    xx, yy, ww, hh = b
    return x + w <= xx or xx + ww <= x or y + h <= yy or yy + hh <= y


def label(image, rect, text, color):
    x, y, w, h = rect
    assert sum(v.lvgl_advances(FONT, text)) <= w
    assert FONT["height"] == h
    return v.lvgl_text(image, (x, y), text, color, FONT)


def render(phase, time, paused, cue, theme, maximum):
    sample = {**v.SAMPLE, "cpu_percent": 100, "ram_percent": 100, "wpm": 200} if maximum else v.SAMPLE
    base = v.bongo_base(SOURCE, sample)
    image = base.copy()
    bounds = []
    if phase:
        bounds += label(image, GEOMETRY["phase"], "FOKUS:" if phase == "focus" else "PAUS:",
                        v.theme_color(SOURCE, "focusAccentHex", theme) if cue else BLACK)
        bounds += label(image, GEOMETRY["time"], time, BLACK)
        if paused:
            draw = ImageDraw.Draw(image)
            for rect in GEOMETRY["pause_bars"]:
                x, y, w, h = rect
                draw.rectangle((x, y, x + w - 1, y + h - 1), fill=BLACK)
                bounds.append(rect)
    for box in bounds:
        assert all(disjoint(box, protected) for protected in RESERVED), box
    # Compare all protected pixels, including the complete transformed cat canvas.
    for x, y, w, h in RESERVED:
        assert image.crop((x, y, x + w, y + h)).tobytes() == base.crop((x, y, x + w, y + h)).tobytes()
    return image, bounds


def main():
    boxes = [GEOMETRY["phase"], GEOMETRY["time"], *GEOMETRY["pause_bars"]]
    for index, box in enumerate(boxes):
        x, y, w, h = box
        assert x >= 0 and y >= 0 and x + w <= 240 and y + h <= 320
        assert all(disjoint(box, protected) for protected in RESERVED)
        assert all(disjoint(box, other) for other in boxes[:index])
    assert all(disjoint(HIT_REGIONS["bongo"], protected) for protected in RESERVED)
    assert all(disjoint(HIT_REGIONS["player"], protected) for protected in
               [[0, 4, 240, 11], [48, 54, 144, 144], [8, 205, 224, 90], [0, 300, 240, 20]])
    max_width = max(sum(v.lvgl_advances(FONT, f"{seconds // 60:02}:{seconds % 60:02}")) for seconds in range(7201))
    assert max_width == GEOMETRY["time"][2] == 96
    assert sum(v.lvgl_advances(FONT, "FOKUS:")) == 96
    assert sum(v.lvgl_advances(FONT, "PAUS:")) == 80
    states = [
        ("focus", "Fokus aktiv", "focus", "04:59", False, False, "green", False),
        ("focus-paused", "Fokus fryst", "focus", "04:31", True, False, "green", False),
        ("long-paused", "120 min / maxstatistik", "focus", "120:00", True, False, "green", True),
        ("break", "Pausfas aktiv", "break", "00:59", False, False, "green", False),
        ("break-paused", "Pausfas fryst", "break", "00:42", True, False, "green", False),
        ("cue-paused", "Fasnotis / fryst / maxstatistik", "break", "00:42", True, True, "green", True),
        ("cyan-cue", "Fasnotis / cyan", "break", "00:59", False, True, "cyan", False),
        ("idle", "Inaktiv / dold", None, "", False, False, "green", False),
    ]
    views = []
    for key, caption, phase, time, paused, cue, theme, maximum in states:
        image, bounds = render(phase, time, paused, cue, theme, maximum)
        path = OUT / f"bongo-{key}.png"
        assert image.size == (240, 320)
        image.save(path)
        views.append({"state": key, "caption": caption, "file": path.name, "sha256": v.sha256(path),
                      "phase": phase, "time": time, "paused": paused, "compact_cue": cue,
                      "theme": theme, "maximum_stats": maximum, "glyph_boxes": bounds})
    baseline = OUT / "bongo-original.png"
    v.bongo_base(SOURCE, v.SAMPLE).save(baseline)
    bg = (27, 33, 39)
    sheet = Image.new("RGB", (1040, 790), bg)
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 12), "BONGO / EN TEXTRAD / 240x320 / SIMULERING", font=v.font(18), fill=v.WHITE)
    for index, view in enumerate(views):
        x, y = 20 + index % 4 * 260, 52 + index // 4 * 365
        sheet.paste(Image.open(OUT / view["file"]), (x, y))
        draw.text((x, y + 327), view["caption"], font=v.font(12), fill=v.WHITE)
    sheet.save(OUT / "contact-sheet.png")
    comparison = Image.new("RGB", (1040, 394), bg)
    draw = ImageDraw.Draw(comparison)
    for index, (path, caption) in enumerate([
        (baseline, "Befintlig Bongo / inaktiv"),
        (ROOT / "visuals/focus-countdown/ui3-implemented-2026-10-12/composed/bongo_focus.png", "Installerad UI3 / aktiv"),
        (OUT / "bongo-focus.png", "Ny Bongo-rad / aktiv"),
        (OUT / "bongo-long-paused.png", "Ny rad / 120 min / fryst"),
    ]):
        x = 20 + index * 260
        comparison.paste(Image.open(path), (x, 43))
        draw.text((x, 14), caption, font=v.font(13), fill=v.WHITE)
    comparison.save(OUT / "before-after.png")
    touch_map = Image.new("RGB", (540, 409), bg)
    draw = ImageDraw.Draw(touch_map)
    draw.text((20, 12), "TOUCHYTOR / ENDAST GRANSKNINGSOVERLAY", font=v.font(15), fill=v.WHITE)
    for index, (panel, path) in enumerate([
        ("bongo", OUT / "bongo-focus.png"),
        ("player", ROOT / "visuals/focus-countdown/ui3-implemented-2026-10-12/composed/player_focus.png"),
    ]):
        preview = Image.open(path).convert("RGBA")
        overlay = Image.new("RGBA", preview.size, (0, 0, 0, 0))
        x, y, w, h = HIT_REGIONS[panel]
        ImageDraw.Draw(overlay).rectangle((x, y, x + w - 1, y + h - 1), fill=(255, 120, 0, 50),
                                          outline=(255, 120, 0, 255), width=1)
        preview = Image.alpha_composite(preview, overlay)
        touch_map.paste(preview.convert("RGB"), (20 + index * 260, 49))
        draw.text((20 + index * 260, 378), f"{panel}: {x},{y},{w},{h}", font=v.font(13), fill=v.WHITE)
    touch_map.save(OUT / "touch-map.png")
    sources = [v.FIRMWARE, FONT["path"], ROOT / "tools/export_ui_visuals.py", *v.CORE_LAYERS.values()]
    manifest = {
        "classification": "Bongo-only design simulation, not firmware or a physical photograph",
        "dimensions": [240, 320], "font": "lv_font_unscii_16", "font_line_height": FONT["height"],
        "geometry_xywh": GEOMETRY, "alignment": "LEFT", "normal_color": "000000",
        "hit_regions_xywh": HIT_REGIONS, "hit_regions_do_not_overlap_protected_areas": True,
        "touch_rule": "Visible status only; single tap toggles local timer in place; existing swipe/long-press arbitration retained",
        "cue": "Existing compact FocusDone cue accents only the phase prefix; no additional object or line",
        "max_time_width_0_to_7200_seconds": max_width, "reserved_xywh": RESERVED,
        "control_and_glyph_overlap_checks_passed": True, "protected_pixels_unchanged": True,
        "scope": "Bongo only; no Player, firmware, shared exporter or focus-logic edits",
        "views": views, "source_sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): v.sha256(p) for p in sources},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(views)} native 240x320 Bongo states; max time width {max_width}px; protected pixels unchanged.")


if __name__ == "__main__":
    main()
