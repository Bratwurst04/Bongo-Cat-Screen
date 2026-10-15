"""Render an isolated UI proposal; never alter firmware or the existing exporter.

The two derived fonts are design assets made from actual LVGL glyph bitmaps.
Code2 owns firmware integration. Other screen elements use the existing exporter.
"""
from pathlib import Path
import copy
import hashlib
import json
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import export_ui_visuals as v

OUT = Path(__file__).resolve().parent


def glyph_mask(face, glyph):
    width, height, bpp = glyph["box_w"], glyph["box_h"], face["bpp"]
    mask = Image.new("L", (width, height))
    pixels = []
    for i in range(width * height):
        offset = i * bpp
        byte = face["bitmap"][glyph["bitmap_index"] + offset // 8]
        pixels.append(((byte >> (8 - bpp - offset % 8)) & ((1 << bpp) - 1)) * 255 // ((1 << bpp) - 1))
    mask.putdata(pixels)
    return mask


def tight_number_font():
    face = copy.deepcopy(v.lvgl_ascii_font("montserrat_14"))
    face.pop("path")
    face["height"], face["baseline"] = 11, 1
    for char in "0123456789:":
        glyph = face["glyphs"][ord(char) - 31]
        if glyph["ofs_y"] != 0 or glyph["box_h"] > 10:
            raise ValueError("Numeric subset no longer fits the 11 px line")
    return face


def draw_glyphs(image, xy, value, fill, face, *, center=False):
    advances = v.lvgl_advances(face, value)
    x, y = xy
    if center:
        x -= sum(advances) // 2
    bounds = []
    for char, advance in zip(value, advances):
        glyph = face["glyphs"][ord(char) - 31]
        if glyph["box_w"] and glyph["box_h"]:
            gx = x + glyph["ofs_x"]
            gy = y + face["height"] - face["baseline"] - glyph["box_h"] - glyph["ofs_y"]
            image.paste(fill, (gx, gy), glyph_mask(face, glyph))
            bounds.append((gx, gy, glyph["box_w"], glyph["box_h"]))
        x += advance
    return bounds


def disjoint(a, b):
    x, y, w, h = a
    xx, yy, ww, hh = b
    return x + w <= xx or xx + ww <= x or y + h <= yy or yy + hh <= y


def add_row(image, panel, phase, time, paused, fonts, cue=False):
    if phase is None:
        return []
    if panel == "bongo":
        phase_text = ("FOKUS" if phase == "focus" else "PAUS") + (" ||" if paused else "")
        phase_face = v.lvgl_ascii_font("unscii_8")
        time_face = v.lvgl_ascii_font("unscii_16")
        phase_width = sum(v.lvgl_advances(phase_face, phase_text))
        time_width = sum(v.lvgl_advances(time_face, time))
        return (draw_glyphs(image, (235 - phase_width, 28), phase_text, (0x50, 0x58, 0x60), phase_face)
                + draw_glyphs(image, (235 - time_width, 44), time, (0x30, 0x38, 0x40), time_face))
    bounds = []
    # The compact PAUS cue itself names the phase while present; no duplicate.
    if not cue:
        phase_text = "FOKUS" if phase == "focus" else "PAUS"
        bounds += draw_glyphs(image, (86, 15), phase_text, (0x1E, 0xD7, 0x60),
                              v.lvgl_ascii_font("montserrat_10"), center=True)
    center = 120 if cue else 133
    bounds += draw_glyphs(image, (center, 15), time, (0xE6, 0xEB, 0xEF),
                          fonts["player"], center=True)
    if paused:
        x = 147 if cue else 163
        draw = ImageDraw.Draw(image)
        for dx in (0, 5):
            draw.rectangle((x + dx, 17, x + dx + 1, 23), fill=(0xE6, 0xEB, 0xEF))
            bounds.append((x + dx, 17, 2, 7))
    return bounds


def main():
    source = v.FIRMWARE.read_text(encoding="utf-8")
    fonts = {"player": tight_number_font()}
    for name, face in fonts.items():
        (OUT / f"font-{name}.json").write_text(json.dumps(face, indent=2) + "\n", encoding="utf-8")
    states = [
        ("focus", "Fokus", "focus", "04:59", False, False),
        ("break", "Pausfas", "break", "00:59", False, False),
        ("focus-paused", "Fokus pausad", "focus", "04:31", True, False),
        ("break-paused", "Pausfas pausad", "break", "00:42", True, False),
        ("long-paused", "120 minuter / pausad / maxstatistik", "focus", "120:00", True, False),
        ("idle", "Inaktiv / dold", None, "", False, False),
        ("cue", "Fasnotis / nedräkning", "break", "00:59", False, True),
        ("dj", "DJ / aktiv / lång källa", "focus", "04:59", False, False),
    ]
    views = []
    reserved = {"bongo": [(5, 5, 144, 17), (5, 25, 144, 17), (5, 45, 128, 17), (155, 5, 80, 17)],
                "player": [(0, 4, 240, 11), (34, 26, 172, 172), (85, 0, 70, 14)]}
    for key, caption, phase, time, paused, cue in states:
        for panel in ("bongo", "player"):
            sample = {**v.SAMPLE, "cpu_percent": 100, "ram_percent": 100, "wpm": 200} if key == "long-paused" else v.SAMPLE
            image = v.bongo_base(source, sample) if panel == "bongo" else v.media_view(
                source, sample, mode="dj" if key == "dj" else "artwork", state="PLAYING",
                media_source="SPOTIFY API PAUSED" if key == "dj" else sample["source_api"])
            if cue:
                image = v.focus_cue_preview(source, image, kind="focus", compact=True, panel=panel)
            bounds = add_row(image, panel, phase, time, paused, fonts, cue)
            for box in bounds:
                assert all(disjoint(box, obstacle) for obstacle in reserved[panel]), (panel, key, box)
                assert 0 <= box[0] and 0 <= box[1] and box[0] + box[2] <= 240 and box[1] + box[3] <= 320
            file = OUT / f"{panel}-{key}.png"
            image.save(file)
            views.append({"panel": panel, "state": key, "caption": caption, "file": file.name,
                          "sha256": v.sha256(file), "glyph_boxes": bounds})
    # All allowed seconds, both phases and pause states use the same fixed row.
    maximum = 0
    for phase, limit in (("FOKUS", 7200), ("PAUS", 1800)):
        for seconds in range(limit + 1):
            time = f"{seconds // 60:02}:{seconds % 60:02}"
            maximum = max(maximum, sum(v.lvgl_advances(fonts["player"], time)))
            assert sum(v.lvgl_advances(v.lvgl_ascii_font("unscii_8"), f"{phase} ||")) <= 64
            assert sum(v.lvgl_advances(v.lvgl_ascii_font("unscii_16"), time)) <= 96
    assert maximum <= 48
    sheet = Image.new("RGB", (1040, 1515), (0x1B, 0x21, 0x27))
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 12), "FOKUS · UI-FÖRSLAG · 240×320 · SIMULATION", font=v.font(18), fill=v.WHITE)
    for index, view in enumerate(views):
        x, y = 20 + (index % 4) * 260, 52 + (index // 4) * 365
        sheet.paste(Image.open(OUT / view["file"]), (x, y))
        draw.text((x, y + 325), f'{view["panel"]} · {view["state"]}', font=v.font(13), fill=(0xD5, 0xD9, 0xDE))
    sheet.save(OUT / "contact-sheet.png")
    manifest = {"classification": "UI proposal using exact derived LVGL glyphs; not firmware or a device photo",
                "display_pixels": [240, 320], "views": views,
                "bongo_rectangles": {"phase": [171, 28, 64, 9], "time": [139, 44, 96, 17]},
                "player_rectangles": {"phase": [68, 15, 36, 11], "time": [109, 15, 48, 11], "pause": [163, 17, 7, 7]},
                "player_time_max_width": maximum,
                "source_sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): v.sha256(p)
                                  for p in [v.FIRMWARE, ROOT / "src/focus_countdown.h", ROOT / "tools/export_ui_visuals.py"]},
                "font_sha256": {name: v.sha256(OUT / f"font-{name}.json") for name in fonts},
                "limits": ["Proposed fonts require Code2 integration and verification before any build or flash.",
                           "Non-countdown screen content uses the existing simulated exporter.",
                           "Bongo layout covers the existing companion WPM range 0..200 (three digits); arbitrary out-of-contract serial input is not a layout guarantee.",
                           "No serial, companion or user config access. Large temporary cues retain existing intentional overlay behavior."]}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered {len(views)} proposal frames, all 240x320; max Player digits {maximum}px.")


if __name__ == "__main__":
    main()
