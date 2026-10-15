"""An isolated integrated-status design, not firmware or a device screenshot.

Uses native LVGL glyphs and the project's existing Bongo/media sprite renderer.
Writes only this design folder. No shared exporter/source modification.
"""
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import export_ui_visuals as v

OUT = Path(__file__).resolve().parent
SOURCE = v.FIRMWARE.read_text(encoding="utf-8")

BONGO = {
    "phase": [139, 42, 80, 17],
    "time": [139, 63, 96, 17],
    "pause_bars": [[224, 45, 3, 11], [230, 45, 3, 11]],
    "divider": [135, 42, 1, 38],
    "cue_underline": [139, 60, 96, 2],
}
PLAYER = {
    "card": [40, 20, 160, 26],
    "phase": [52, 25, 52, 16],
    "time": [112, 24, 56, 18],
    "pause_bars": [[176, 28, 3, 10], [182, 28, 3, 10]],
    "art_active": [48, 54, 144, 144],
    "art_idle": [34, 26, 172, 172],
    "art_zoom_active": 320,
    "dj_zoom_active": 560,
}


def intersects(a, b):
    x, y, w, h = a
    xx, yy, ww, hh = b
    return x < xx + ww and xx < x + w and y < yy + hh and yy < y + h


def glyphs(image, rect, value, font, color, alignment="left"):
    x, y, width, height = rect
    face = v.lvgl_ascii_font(font)
    advances = v.lvgl_advances(face, value)
    length = sum(advances)
    assert length <= width and face["height"] <= height, (value, font, rect, length)
    if alignment == "right":
        x += width - length
    elif alignment == "center":
        x += (width - length) // 2
    v.lvgl_text(image, (x, y), value, color, font)
    boxes = []
    for char, advance in zip(value, advances):
        g = face["glyphs"][ord(char) - 31]
        if g["box_w"] and g["box_h"]:
            boxes.append([x + g["ofs_x"], y + face["height"] - face["baseline"] - g["box_h"] - g["ofs_y"],
                          g["box_w"], g["box_h"]])
        x += advance
    return boxes


def rect_fill(draw, rect, color):
    x, y, w, h = rect
    draw.rectangle((x, y, x + w - 1, y + h - 1), fill=color)


def render_bongo(phase, time, paused, cue, sample, theme):
    image = v.bongo_base(SOURCE, sample)
    boxes = []
    if phase is not None:
        boxes += glyphs(image, BONGO["phase"], "FOKUS" if phase == "focus" else "PAUS",
                        "unscii_16", (0x50, 0x58, 0x60))
        boxes += glyphs(image, BONGO["time"], time, "unscii_16", (0x40, 0x48, 0x4F), "right")
        draw = ImageDraw.Draw(image)
        rect_fill(draw, BONGO["divider"], (0xD5, 0xD9, 0xDE))
        boxes.append(BONGO["divider"])
        if paused:
            for rect in BONGO["pause_bars"]:
                rect_fill(draw, rect, (0x50, 0x58, 0x60))
                boxes.append(rect)
        if cue:
            rect_fill(draw, BONGO["cue_underline"], v.theme_color(SOURCE, "focusAccentHex", theme))
            boxes.append(BONGO["cue_underline"])
    # The new status also stays ABOVE the full canvas rectangle, not merely its
    # sample cat silhouette. This protects every sprite/animation frame.
    obstacles = [[5, 5, 144, 17], [5, 25, 144, 17], [5, 45, 128, 17], [155, 5, 80, 17], [0, 82, 240, 238]]
    for box in boxes:
        assert not any(intersects(box, obstacle) for obstacle in obstacles), (box, obstacles)
    return image, boxes


def active_player_base(sample, mode, theme, source_text):
    # Preserve the header and entire lower information/status area. Redraw the
    # circular art from the ORIGINAL artwork/sprites at the proposed LVGL zoom;
    # do not resample an old screenshot's cover.
    base = v.media_view(SOURCE, sample, mode=mode, state="PLAYING", media_source=source_text, theme=theme)
    image = Image.new("RGB", (240, 320), (0x08, 0x0A, 0x0C))
    image.paste(base.crop((0, 0, 240, 16)), (0, 0))
    image.paste(base.crop((0, 198, 240, 320)), (0, 198))
    x, y, w, h = PLAYER["art_active"]
    draw = ImageDraw.Draw(image)
    draw.ellipse((x, y, x + w - 1, y + h - 1), fill=v.WHITE if mode == "dj" else (0x08, 0x0A, 0x0C),
                 outline=v.WHITE if mode == "dj" else (0x25, 0x2A, 0x30))
    if mode == "dj":
        art = v.compose(["standardbody1", "stock_face", "dj_glasses", "dj_mixer_board", "twopawsup"], white_background=True)
        pixels = 64 * PLAYER["dj_zoom_active"] // 256
    else:
        art = v.demo_art(112)
        pixels = 112 * PLAYER["art_zoom_active"] // 256
    art = art.resize((pixels, pixels), Image.Resampling.NEAREST)
    viewport = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    viewport.alpha_composite(art, ((w - pixels) // 2, (h - pixels) // 2))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse((1, 1, w - 2, h - 2), fill=255)
    viewport.putalpha(Image.composite(viewport.getchannel("A"), Image.new("L", (w, h)), mask))
    image.paste(viewport, (x, y), viewport)
    return image


def render_player(phase, time, paused, cue, sample, theme, mode="artwork", source_text="SPOTIFY API"):
    if phase is None:
        return v.media_view(SOURCE, sample, mode=mode, state="PLAYING", media_source=source_text, theme=theme), []
    image = active_player_base(sample, mode, theme, source_text)
    draw = ImageDraw.Draw(image)
    x, y, w, h = PLAYER["card"]
    accent = v.theme_color(SOURCE, "focusAccentHex", theme)
    fill = v.theme_color(SOURCE, "focusDarkAccentHex", theme) if cue else (0x15, 0x19, 0x1E)
    draw.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=10,
                           fill=fill, outline=accent if cue else (0x29, 0x2E, 0x35), width=1)
    boxes = [PLAYER["card"]]
    boxes += glyphs(image, PLAYER["phase"], "FOKUS" if phase == "focus" else "PAUS",
                    "montserrat_14", accent, "center")
    boxes += glyphs(image, PLAYER["time"], time, "montserrat_16", (0xF2, 0xF4, 0xF7), "center")
    if paused:
        for rect in PLAYER["pause_bars"]:
            rect_fill(draw, rect, (0xF2, 0xF4, 0xF7))
            boxes.append(rect)
    obstacles = [[0, 4, 240, 11], PLAYER["art_active"], [8, 205, 224, 90], [0, 301, 240, 19]]
    for box in boxes:
        assert not any(intersects(box, obstacle) for obstacle in obstacles), (box, obstacles)
    return image, boxes


def main():
    states = [
        ("focus", "Fokus aktiv", "focus", "04:59", False, False, "green", "artwork"),
        ("long-paused", "120:00 · pausad · maxstatistik", "focus", "120:00", True, False, "green", "artwork"),
        ("cue-paused", "Pausfas · fryst · fasnotis", "break", "00:42", True, True, "green", "artwork"),
        ("break-paused", "Pausfas · fryst", "break", "00:42", True, False, "green", "artwork"),
        ("idle", "Inaktiv · dold", None, "", False, False, "green", "artwork"),
        ("dj", "Fokus · DJ · lång källa", "focus", "04:59", False, False, "green", "dj"),
        ("cyan-cue", "Pausfas · cyan · fasnotis", "break", "00:59", False, True, "cyan", "artwork"),
    ]
    views = []
    for key, caption, phase, time, paused, cue, theme, mode in states:
        sample = {**v.SAMPLE, "cpu_percent": 100, "ram_percent": 100, "wpm": 200} if key in ("long-paused", "cue-paused") else v.SAMPLE
        for panel in ("bongo", "player"):
            image, boxes = (render_bongo(phase, time, paused, cue, sample, theme) if panel == "bongo" else
                            render_player(phase, time, paused, cue, sample, theme, mode,
                                          "SPOTIFY API PAUSED" if key == "dj" else "SPOTIFY API"))
            file = OUT / f"{panel}-{key}.png"
            assert image.size == (240, 320)
            image.save(file)
            views.append({"panel": panel, "state": key, "caption": caption, "file": file.name,
                          "sha256": v.sha256(file), "glyph_and_card_boxes": boxes})
    widths = {}
    for name, rect in (("unscii_16", BONGO["time"]), ("montserrat_16", PLAYER["time"])):
        face = v.lvgl_ascii_font(name)
        widest = max(sum(v.lvgl_advances(face, f"{s // 60:02}:{s % 60:02}")) for s in range(7201))
        assert widest <= rect[2]
        widths[name] = widest
    sheet = Image.new("RGB", (1040, 1520), (0x1B, 0x21, 0x27))
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 12), "FOKUS · INTEGRERAD STATUS · 240×320 · SIMULATION", font=v.font(18), fill=v.WHITE)
    for i, view in enumerate(views):
        x, y = 20 + (i % 4) * 260, 52 + (i // 4) * 365
        sheet.paste(Image.open(OUT / view["file"]), (x, y))
        draw.text((x, y + 326), f'{view["panel"]} · {view["state"]}', font=v.font(13), fill=(0xD5, 0xD9, 0xDE))
    sheet.save(OUT / "contact-sheet.png")
    comparison = Image.new("RGB", (1040, 395), (0x1B, 0x21, 0x27))
    cd = ImageDraw.Draw(comparison)
    for i, (file, caption) in enumerate([
        (ROOT / "visuals/focus-countdown/ui-implemented-2026-10-12/composed/bongo_focus.png", "Bongo · 8BB simulering"),
        (OUT / "bongo-focus.png", "Bongo · nytt förslag"),
        (ROOT / "visuals/focus-countdown/ui-implemented-2026-10-12/composed/player_focus.png", "Player · 8BB simulering"),
        (OUT / "player-focus.png", "Player · nytt förslag"),
    ]):
        x = 20 + i * 260
        cd.text((x, 12), caption, font=v.font(14), fill=v.WHITE)
        comparison.paste(Image.open(file), (x, 42))
    comparison.save(OUT / "comparison.png")
    sources = [v.FIRMWARE, ROOT / "tools/export_ui_visuals.py", ROOT / "src/focus_countdown.h"]
    fonts = [v.lvgl_ascii_font(name)["path"] for name in ("unscii_16", "montserrat_14", "montserrat_16")]
    manifest = {"classification": "isolated design proposal; not firmware or physical screen evidence",
                "display_pixels": [240, 320], "bongo_layout": BONGO, "player_layout": PLAYER,
                "native_fonts": ["lv_font_unscii_16", "lv_font_montserrat_14", "lv_font_montserrat_16"],
                "max_number_widths": widths, "views": views,
                "source_sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): v.sha256(p) for p in sources + fonts},
                "limits": ["Countdown glyphs use unmodified native LVGL font bitmaps and integer label alignment.",
                           "Rounded borders and other media typography use the established simulated exporter.",
                           "Artwork is synthetic demo data. No serial, companion, hardware, build or flash.",
                           "Compact cue is integrated into status; large cue timing/appearance remains existing behavior."]}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered {len(views)} 240x320 designs; numeric widths {widths}.")


if __name__ == "__main__":
    main()
