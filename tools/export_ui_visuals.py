#!/usr/bin/env python3
"""Export deterministic, simulated 240x320 previews of the current ESP32 UI.

Run from any directory: python tools/export_ui_visuals.py
Requires Pillow. The script reads firmware layout constants and the PNG sprite
sources; it does not build firmware, open a serial port, or modify source files.
Unsupported changes to the expected LVGL layout fail visibly instead of
silently producing an old layout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = ROOT / "src" / "bongo_cat_featured.inc"
SPRITES_HEADER = ROOT / "animations_sprites.h"
DJ_HEADER = ROOT / "animations" / "dj" / "dj_sprites.h"
ASSETS = ROOT / "assets"
CORE = ASSETS / "cat-sprites"
DJ = ASSETS / "User-made"

CORE_LAYERS = {
    "standardbody1": CORE / "body" / "standardbody1.png",
    "stock_face": CORE / "face" / "stock_face.png",
    "table1": CORE / "table" / "table1.png",
    "twopawsup": CORE / "paws" / "twopawsup.png",
}
DJ_LAYERS = {
    "dj_glasses": DJ / "Glasses.png",
    "dj_mixer_board": DJ / "Mixer bord 1.png",
    "dj_effect_r1": DJ / "Effects R1.png",
    "dj_effect_r2": DJ / "Effects R2.png",
    "dj_notes_l1": DJ / "Music Notes L1.png",
    "dj_notes_l2": DJ / "Music Notes L2.png",
    "dj_notes_r1": DJ / "Music Notes R1.png",
    "dj_notes_r2": DJ / "Music Notes R2.png",
}
SAMPLE = {
    "time": "14:26",
    "cpu_percent": 18,
    "ram_percent": 42,
    "wpm": 73,
    "bonks": 7,
    "title": "Midnight Circuit — Extended Session Mix",
    "artist": "Demo Artist",
    "elapsed_seconds": 82,
    "duration_seconds": 213,
    "source_windows": "SPOTIFY",
    "source_api": "SPOTIFY API",
    "dj_playing_layers": ["dj_effect_r1", "dj_notes_l1", "dj_notes_r2"],
    "dj_paused_layers": ["dj_effect_r1", "dj_notes_l1", "dj_notes_r2"],
}
WHITE = (255, 255, 255)
GREEN = (0x1E, 0xD7, 0x60)
BG = (0x08, 0x0A, 0x0C)


def theme_color(source: str, function: str, theme: str) -> tuple[int, int, int]:
    found = re.search(rf"uint32_t\s+{function}\(\)\s*\{{(.*?)\n\}}", source, re.S)
    if not found:
        raise ValueError(f"Missing theme source function {function}")
    branch = (rf"case AccentTheme::{theme.capitalize()}: return 0x([0-9A-Fa-f]{{6}})"
              if theme != "green" else r"default: return 0x([0-9A-Fa-f]{6})")
    value = re.search(branch, found[1])
    if not value:
        raise ValueError(f"Missing {theme} in {function}")
    return tuple(bytes.fromhex(value[1]))


def touch_rects_do_not_overlap(rects: list[tuple[int, int, int, int]]) -> None:
    for index, (x, y, width, height) in enumerate(rects):
        if height < 44 or x < 0 or y < 0 or x + width > 240 or y + height > 320:
            raise ValueError(f"Touch target outside 240x320 or below 44 px: {rects[index]}")
        for other in rects[:index]:
            ox, oy, ow, oh = other
            if x < ox + ow and ox < x + width and y < oy + oh and oy < y + height:
                raise ValueError(f"Touch targets overlap: {rects[index]} and {other}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section(source: str, function: str) -> str:
    match = re.search(r"\b(?:void|bool|TouchRect|lv_obj_t\s*\*)\s*" + re.escape(function) + r"\s*\([^)]*\)\s*\{", source)
    if not match:
        raise ValueError(f"Cannot find firmware function {function}")
    start = match.end()
    depth = 1
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index]
    raise ValueError(f"Unclosed firmware function {function}")


def match_int(source: str, pattern: str, label: str) -> int:
    found = re.search(pattern, source, re.S)
    if not found:
        raise ValueError(f"Unsupported firmware layout: missing {label}")
    return int(found.group(1))


def define(source: str, name: str) -> int:
    return match_int(source, rf"#define\s+{name}\s+(\d+)\b", name)


def pos(body: str, obj: str) -> tuple[int, int]:
    found = re.search(rf"lv_obj_set_pos\(\s*{obj}\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)", body)
    if not found:
        raise ValueError(f"Unsupported firmware layout: missing position for {obj}")
    return int(found[1]), int(found[2])


def size(body: str, obj: str) -> tuple[int, int]:
    found = re.search(rf"lv_obj_set_size\(\s*{obj}\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", body)
    if not found:
        raise ValueError(f"Unsupported firmware layout: missing size for {obj}")
    return int(found[1]), int(found[2])


def align(body: str, obj: str, kind: str) -> tuple[int, int]:
    found = re.search(
        rf"lv_obj_align\(\s*{obj}\s*,\s*LV_ALIGN_{kind}\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)",
        body,
    )
    if not found:
        raise ValueError(f"Unsupported firmware layout: missing {kind} alignment for {obj}")
    return int(found[1]), int(found[2])


def color(body: str, obj: str, property_name: str) -> tuple[int, int, int]:
    found = re.search(
        rf"lv_obj_set_style_{property_name}\(\s*{obj}\s*,\s*lv_color_hex\(0x([0-9A-Fa-f]{{6}})\)",
        body,
    )
    if not found:
        raise ValueError(f"Unsupported firmware layout: missing {property_name} for {obj}")
    return tuple(bytes.fromhex(found[1]))


def static_text(body: str, obj: str) -> str:
    found = re.search(rf'lv_label_set_text\(\s*{obj}\s*,\s*"((?:\\.|[^"\\])*)"\s*\)', body)
    if not found:
        raise ValueError(f"Unsupported firmware text: missing static text for {obj}")
    return bytes(found[1], "utf-8").decode("unicode_escape")


def require(source: str, text: str) -> None:
    if text not in source:
        raise ValueError(f"Firmware behavior changed; update preview renderer: {text}")


def load_layer(path: Path, opaque_sparse: bool = False) -> Image.Image:
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
    if image.size != (64, 64):
        raise ValueError(f"Sprite must be 64x64: {path}")
    if opaque_sparse:
        image.putalpha(image.getchannel("A").point(lambda a: 255 if a else 0))
    return image


def check_dj_header() -> None:
    """The preview's PNGs must match the sparse pixels used by firmware."""
    header = DJ_HEADER.read_text(encoding="utf-8")
    for symbol, path in DJ_LAYERS.items():
        match = re.search(
            rf"static const DjPixel {symbol}_pixels\[\] = \{{(.*?)\}};\s*"
            rf"static const DjSprite {symbol} = \{{{symbol}_pixels,\s*(\d+)\}};",
            header,
            re.S,
        )
        if not match:
            raise ValueError(f"Missing DJ sprite {symbol} in {DJ_HEADER}")
        encoded = [tuple(map(int, values)) for values in re.findall(
            r"\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}",
            match[1],
        )]
        image = load_layer(path)
        source = [
            (x, y, *image.getpixel((x, y)))
            for y in range(64) for x in range(64)
            if image.getpixel((x, y))[3]
        ]
        if encoded != source or len(source) != int(match[2]):
            raise ValueError(f"DJ PNG/header mismatch: {path}")


def font(size: int, mono: bool = False) -> ImageFont.FreeTypeFont:
    filename = "consola.ttf" if mono else "arial.ttf"
    try:
        return ImageFont.truetype(str(Path("C:/Windows/Fonts") / filename), size)
    except OSError:
        return ImageFont.truetype("DejaVuSansMono.ttf" if mono else "DejaVuSans.ttf", size)


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str,
         fill: tuple[int, int, int], size: int, *, center: bool = False,
         right: bool = False, mono: bool = False) -> None:
    face = font(size, mono)
    anchor = "mt" if center else "rt" if right else "lt"
    draw.text(xy, value, font=face, fill=fill, anchor=anchor, stroke_width=0)


def clipped(value: str, face: ImageFont.FreeTypeFont, width: int) -> str:
    if face.getlength(value) <= width:
        return value
    ellipsis = "..."
    while value and face.getlength(value + ellipsis) > width:
        value = value[:-1]
    return value.rstrip() + ellipsis


def compose(names: list[str], white_background: bool = False) -> Image.Image:
    canvas = Image.new("RGBA", (64, 64), WHITE + (255,) if white_background else (0, 0, 0, 0))
    for name in names:
        path = CORE_LAYERS.get(name) or DJ_LAYERS.get(name)
        if path is None:
            raise ValueError(f"Unknown sprite {name}")
        canvas.alpha_composite(load_layer(path, name in DJ_LAYERS))
    return canvas


def bongo_base(source: str, sample: dict) -> Image.Image:
    body = section(source, "createBongoCat")
    zoom = match_int(body, r"lv_img_set_zoom\(cat_canvas,\s*(\d+)\)", "cat zoom")
    ox, oy = align(body, "cat_canvas", "CENTER")
    width, height = define(source, "SCREEN_WIDTH"), define(source, "SCREEN_HEIGHT")
    sprite_size = define(source, "CAT_SIZE") * zoom // 256
    image = Image.new("RGB", (width, height), WHITE)
    cat = compose(["standardbody1", "stock_face", "table1", "twopawsup"])
    cat = cat.resize((sprite_size, sprite_size), Image.Resampling.NEAREST)
    image.paste(cat, ((width - sprite_size) // 2 + ox, (height - sprite_size) // 2 + oy), cat)
    draw = ImageDraw.Draw(image)
    x, y = align(body, "cpu_label", "TOP_LEFT")
    text(draw, (x, y), f"CPU: {sample['cpu_percent']}%", (0, 0, 0), 16, mono=True)
    x, y = align(body, "ram_label", "TOP_LEFT")
    text(draw, (x, y), f"RAM: {sample['ram_percent']}%", (0, 0, 0), 16, mono=True)
    x, y = align(body, "wpm_label", "TOP_LEFT")
    text(draw, (x, y), f"WPM: {sample['wpm']}", (0, 0, 0), 16, mono=True)
    x, y = align(body, "time_label", "TOP_RIGHT")
    text(draw, (width + x, y), sample["time"], (0, 0, 0), 16, right=True, mono=True)
    return image


def panel_menu(source: str, base: Image.Image, active_panel: str,
               theme: str = "green", pressed: str | None = None) -> Image.Image:
    body = section(source, "createFeatureOverlay")
    image = Image.new("RGB", base.size,
                      color(body, "feature_overlay_backdrop", "bg_color"))
    width, height = size(body, "feature_overlay")
    ox, oy = align(body, "feature_overlay", "CENTER")
    x = (image.width - width) // 2 + ox
    y = (image.height - height) // 2 + oy
    padding = match_int(body, r"lv_obj_set_style_pad_all\(feature_overlay,\s*(\d+)", "overlay padding")
    border = match_int(body, r"lv_obj_set_style_border_width\(feature_overlay,\s*(\d+)", "overlay border")
    radius = match_int(body, r"lv_obj_set_style_radius\(feature_overlay,\s*(\d+)", "overlay radius")
    draw = ImageDraw.Draw(image)
    accent = theme_color(source, "focusAccentHex", theme)
    dark = theme_color(source, "focusDarkAccentHex", theme)
    pressed_color = theme_color(source, "focusPressedHex", theme)
    draw.rounded_rectangle((x, y, x + width - 1, y + height - 1), radius=radius,
                           fill=color(body, "feature_overlay", "bg_color"),
                           outline=accent, width=border)
    cx, cy = x + padding + border, y + padding + border
    text(draw, (x + width // 2, cy), static_text(body, "feature_overlay_label"), accent, 14, center=True)
    for panel, button, label in (
        ("bongo", "feature_overlay_bongo_button", "feature_overlay_bongo_label"),
        ("player", "feature_overlay_player_button", "feature_overlay_player_label"),
        ("focus", "feature_overlay_focus_button", "feature_overlay_focus_label"),
        ("settings", "feature_overlay_settings_button", "feature_overlay_settings_label"),
    ):
        bx, by = pos(body, button)
        bw, bh = size(body, button)
        selected = active_panel == panel
        draw.rounded_rectangle((cx + bx, cy + by, cx + bx + bw - 1, cy + by + bh - 1),
                               radius=10, fill=pressed_color if pressed == panel else
                               dark if selected else (0x17, 0x1A, 0x1F),
                               outline=accent if selected else (0x4C, 0x55, 0x5D),
                               width=2 if selected else 1)
        caption = static_text(body, label).replace("  AKTIV", "")
        if selected:
            caption += "  AKTIV"
        text(draw, (cx + bx + bw // 2, cy + by + (bh - 14) // 2),
             caption, accent if selected else WHITE, 14, center=True)
    touch_rects_do_not_overlap([
        (*pos(body, button), *size(body, button)) for button in (
            "feature_overlay_bongo_button", "feature_overlay_player_button",
            "feature_overlay_focus_button", "feature_overlay_settings_button")
    ])
    hx, hy = pos(body, "feature_overlay_hint_label")
    hint_width = match_int(body, r"lv_obj_set_width\(feature_overlay_hint_label,\s*(\d+)", "hint width")
    text(draw, (cx + hx + hint_width // 2, cy + hy),
         static_text(body, "feature_overlay_hint_label"),
         (0xD5, 0xD9, 0xDE), 10, center=True)
    return image


def focus_view(source: str, mode: str, theme: str = "green",
               pressed: str | None = None) -> Image.Image:
    body = section(source, "createFocusScreen")
    width, height = define(source, "SCREEN_WIDTH"), define(source, "SCREEN_HEIGHT")
    image = Image.new("RGB", (width, height), color(body, "focus_screen", "bg_color"))
    draw = ImageDraw.Draw(image)
    accent = theme_color(source, "focusAccentHex", theme)
    dark = theme_color(source, "focusDarkAccentHex", theme)
    pressed_color = theme_color(source, "focusPressedHex", theme)
    rx, ry = pos(body, "focus_progress_ring")
    rw, rh = size(body, "focus_progress_ring")
    if rw != rh:
        raise ValueError("Focus progress arc must be circular")
    progress = {"idle": 0.0, "running": (25 * 60 - (12 * 60 + 34)) / (25 * 60),
                "long": 0.0, "break_running": 0.25,
                "break_started": 0.0, "break_done": 1.0}[mode]
    ring_box = (rx + 3, ry + 3, rx + rw - 4, ry + rh - 4)
    draw.ellipse(ring_box, outline=(0x30, 0x3A, 0x42), width=5)
    if progress:
        draw.arc(ring_box, -90, -90 + round(progress * 360), fill=accent, width=6)
    heading_x, heading_y = pos(body, "focus_phase_label")
    is_break = mode.startswith("break")
    text(draw, (heading_x, heading_y), "PAUS" if is_break else "FOKUS",
         accent, 14)
    sx, sy = pos(body, "focus_settings_button")
    sw, sh = size(body, "focus_settings_button")
    draw.rounded_rectangle((sx, sy, sx + sw - 1, sy + sh - 1), radius=8,
                           fill=pressed_color if pressed == "times" else dark, outline=accent)
    text(draw, (sx + sw // 2, sy + (sh - 14) // 2),
         static_text(body, "settings_label"), accent, 14, center=True)

    _, timer_y = align(body, "focus_time_label", "TOP_MID")
    timer = {"idle": "25:00", "running": "12:34", "break_running": "03:45",
             "break_started": "05:00", "break_done": "00:00",
             "long": "120:00"}[mode]
    timer_width = font(40).getlength(timer)
    if timer_width >= rw - 10:
        raise ValueError(f"Timer text may hit progress ring: {timer}")
    text(draw, (width // 2, timer_y), timer, WHITE, 40, center=True)
    _, status_y = align(body, "focus_status_label", "TOP_MID")
    status = {"idle": "REDO FOR FOKUS", "running": "FOKUS AKTIV",
              "long": "REDO FOR FOKUS",
              "break_running": "PAUS AKTIV", "break_started": "PAUS AKTIV",
              "break_done": "PAUS KLAR"}[mode]
    text(draw, (width // 2, status_y), status, accent,
         20 if mode == "break_done" else 14, center=True)

    for button, caption, fill, outline in (
        ("focus_start_button", "START FOKUS" if mode == "break_done" else
         "PAUS" if mode in ("running", "break_running", "break_started") else "START",
         dark, accent),
        ("focus_reset_button", static_text(body, "reset_label"),
         (0x17, 0x1A, 0x1F), (0x4C, 0x55, 0x5D)),
    ):
        x, y = pos(body, button)
        bw, bh = size(body, button)
        if bh < 44:
            raise ValueError(f"Focus touch button too short: {button}")
        draw.rounded_rectangle((x, y, x + bw - 1, y + bh - 1), radius=10,
                               fill=pressed_color if pressed ==
                               ("start" if button == "focus_start_button" else "reset") else fill,
                               outline=outline, width=2 if button == "focus_start_button" else 1)
        text(draw, (x + bw // 2, y + (bh - 14) // 2), caption,
             accent if button == "focus_start_button" else WHITE, 14, center=True)

    nx, ny = pos(body, "focus_next_label")
    text(draw, (nx, ny), "VALT 25 / 5 MIN" if mode != "long" else
         "VALT 120 / 5 MIN", (0x74, 0x7B, 0x84), 10)
    touch_rects_do_not_overlap([
        (*pos(body, name), *size(body, name)) for name in (
            "focus_settings_button", "focus_start_button", "focus_reset_button")
    ])
    return focus_cue_preview(source, image, kind="focus", compact=False,
                             theme=theme) if mode == "break_started" else image


def focus_settings_view(source: str, focus_minutes: int, break_minutes: int,
                        theme: str = "green", pressed: str | None = None) -> Image.Image:
    body = section(source, "createFocusSettingsScreen")
    width, height = define(source, "SCREEN_WIDTH"), define(source, "SCREEN_HEIGHT")
    image = Image.new("RGB", (width, height), color(body, "focus_settings_screen", "bg_color"))
    draw = ImageDraw.Draw(image)
    accent = theme_color(source, "focusAccentHex", theme)
    dark = theme_color(source, "focusDarkAccentHex", theme)
    pressed_color = theme_color(source, "focusPressedHex", theme)
    hx, hy = pos(body, "focus_settings_heading")
    text(draw, (hx, hy), static_text(body, "focus_settings_heading"), accent, 20)
    ix, iy = pos(body, "focus_settings_info_label")
    iw = match_int(body, r"lv_obj_set_width\(focus_settings_info_label,\s*(\d+)", "info width")
    text(draw, (ix + iw, iy), static_text(body, "focus_settings_info_label"),
         (0xD5, 0xD9, 0xDE), 10, right=True)
    targets = []
    for card, value_obj, caption, buttons in (
        ("focus_settings_focus_card", "focus_settings_focus_label",
         f"FOKUS  {focus_minutes} MIN", ("focus_settings_focus_plus", "focus_settings_focus_minus")),
        ("focus_settings_break_card", "focus_settings_break_label",
         f"PAUS  {break_minutes} MIN", ("focus_settings_break_plus", "focus_settings_break_minus")),
    ):
        cx, cy = pos(body, card)
        cw, ch = size(body, card)
        draw.rounded_rectangle((cx, cy, cx + cw - 1, cy + ch - 1), radius=9,
                               fill=color(body, card, "bg_color"),
                               outline=color(body, card, "border_color"))
        lx, ly = pos(body, value_obj)
        lw = match_int(body, rf"lv_obj_set_width\({value_obj},\s*(\d+)\)", "value width")
        text(draw, (cx + lx + lw // 2, cy + ly), caption, WHITE, 16, center=True)
        for button in buttons:
            found = re.search(
                rf'{button}\s*=\s*createFocusSettingsButton\(\s*{card},\s*"([^"]+)",\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)',
                body)
            if not found:
                raise ValueError(f"Unsupported firmware settings layout: {button}")
            label, bx, by, bw, bh = found[1], *map(int, found.groups()[1:])
            targets.append((cx + bx, cy + by, bw, bh))
            draw.rounded_rectangle((cx + bx, cy + by, cx + bx + bw - 1, cy + by + bh - 1),
                                   radius=9, fill=pressed_color if pressed == button else dark,
                                   outline=accent)
            text(draw, (cx + bx + bw // 2, cy + by + (bh - 20) // 2),
                 label, accent, 20, center=True)
    found = re.search(r'focus_settings_save\s*=\s*createFocusSettingsButton\(\s*focus_settings_screen,\s*"([^"]+)",\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', body)
    if not found:
        raise ValueError("Missing TIDER save button")
    label, x, y, bw, bh = found[1], *map(int, found.groups()[1:])
    targets.append((x, y, bw, bh))
    draw.rounded_rectangle((x, y, x + bw - 1, y + bh - 1), radius=9,
                           fill=pressed_color if pressed == "focus_settings_save" else dark,
                           outline=accent)
    text(draw, (x + bw // 2, y + (bh - 14) // 2), label, accent, 14, center=True)
    touch_rects_do_not_overlap(targets)
    return image


def local_settings_view(source: str, theme: str = "green",
                        pressed: str | None = None) -> Image.Image:
    body = section(source, "createLocalSettingsScreen")
    helper = section(source, "createLocalSettingsButton")
    image = Image.new("RGB", (define(source, "SCREEN_WIDTH"),
                              define(source, "SCREEN_HEIGHT")),
                      color(body, "local_settings_screen", "bg_color"))
    draw = ImageDraw.Draw(image)
    accent = theme_color(source, "focusAccentHex", theme)
    dark = theme_color(source, "focusDarkAccentHex", theme)
    pressed_color = theme_color(source, "focusPressedHex", theme)
    _, heading_y = align(body, "local_settings_heading", "TOP_MID")
    text(draw, (120, heading_y), static_text(body, "local_settings_heading"),
         accent, 20, center=True)
    bx = match_int(helper, r'local_settings_screen, caption, (\d+), y,', "settings button x")
    bw = match_int(helper, r'local_settings_screen, caption, \d+, y, (\d+), height', "settings button width")
    targets = []
    for obj, title, y_label in (
        ("local_settings_theme_button", f"TEMA: {dict(green='GRON', cyan='CYAN', amber='AMBER')[theme]}  >", "theme"),
        ("local_settings_auto_button", "VISA FOKUS VID FASSLUT\nAV", "auto"),
        ("local_settings_led_button", "LED VID FASSLUT\nPA", "led"),
    ):
        found = re.search(rf'{obj}\s*=\s*createLocalSettingsButton\(\s*"(?:\\.|[^"\\])*",\s*(\d+),\s*(\d+),', body)
        if not found:
            raise ValueError(f"Missing local settings button {obj}")
        by, bh = map(int, found.groups())
        targets.append((bx, by, bw, bh))
        draw.rounded_rectangle((bx, by, bx + bw - 1, by + bh - 1), radius=9,
                               fill=pressed_color if pressed == y_label else dark,
                               outline=accent)
        lines = title.split("\n")
        top = by + (bh - len(lines) * 16) // 2
        for idx, line in enumerate(lines):
            if font(14).getlength(line) > bw - 14:
                raise ValueError(f"Local settings text too wide: {line}")
            text(draw, (bx + bw // 2, top + idx * 16), line, accent, 14, center=True)
    ix, iy = pos(body, "local_settings_info_label")
    iw = match_int(body, r"lv_obj_set_width\(local_settings_info_label,\s*(\d+)\)", "settings info width")
    text(draw, (ix + iw // 2, iy), static_text(body, "local_settings_info_label"),
         (0xD5, 0xD9, 0xDE), 10, center=True)
    found = re.search(r'local_settings_back_button\s*=\s*createFocusSettingsButton\(\s*local_settings_screen,\s*"([^"]+)",\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', body)
    if not found:
        raise ValueError("Missing local settings back button")
    title, x, y, w, h = found[1], *map(int, found.groups()[1:])
    targets.append((x, y, w, h))
    draw.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=9,
                           fill=pressed_color if pressed == "back" else dark,
                           outline=accent)
    text(draw, (x + w // 2, y + (h - 20) // 2), title, accent, 20, center=True)
    touch_rects_do_not_overlap(targets)
    return image


def focus_cue_preview(source: str, base: Image.Image, *, kind: str,
                      compact: bool, theme: str = "green") -> Image.Image:
    if compact and kind == "break":
        raise ValueError("Break completion has no persistent START badge")
    body = section(source, "createFocusScreen")
    update = section(source, "updateFocusCue")
    require(update, 'focus_done ? "FOKUS KLART" : "PAUS KLAR"')
    require(update, 'focus_done ? "PAUS" : "START"')
    image = base.copy()
    draw = ImageDraw.Draw(image)
    focus_done = kind == "focus"
    if compact:
        bx = match_int(update, r"lv_obj_set_pos\(focus_completion_banner,\s*compact\s*\?\s*(\d+)",
                       "compact completion x")
        by = 0
        width = match_int(update, r"lv_obj_set_size\(focus_completion_banner,\s*compact\s*\?\s*(\d+)",
                          "compact completion width")
        height = 22
    elif focus_done:
        bx, by = pos(body, "focus_completion_banner")
        width, height = size(body, "focus_completion_banner")
    else:
        bx, by, width, height = 0, 0, image.width, 46
    fill = (theme_color(source, "focusDarkAccentHex", theme) if compact else
            theme_color(source, "focusAccentHex", theme))
    caption = ("PAUS" if focus_done else "START") if compact else (
        "FOKUS KLART" if focus_done else "PAUS KLAR")
    draw.rounded_rectangle((bx, by, bx + width - 1, by + height - 1),
                           radius=7 if compact else 12 if focus_done else 0, fill=fill)
    if focus_done and not compact:
        text(draw, (bx + width // 2, by + 20), caption, (0x10, 0x14, 0x19),
             28, center=True)
        text(draw, (bx + width // 2, by + 72),
             static_text(body, "focus_completion_sub_label"),
             (0x10, 0x14, 0x19), 14, center=True)
    else:
        size_px = 10 if compact else 20
        text(draw, (bx + width // 2, by + (height - size_px) // 2), caption,
             theme_color(source, "focusAccentHex", theme) if compact else
             (0x10, 0x14, 0x19), size_px, center=True)
    return image


def vinyl_art(size: int) -> Image.Image:
    art = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    center = size // 2
    for y in range(size):
        for x in range(size):
            radius2 = (x - center) ** 2 + (y - center) ** 2
            pixel = None
            if radius2 <= 46 * 46:
                pixel = (0x11, 0x13, 0x18, 255)
            if 38 * 38 <= radius2 <= 39 * 39 or 31 * 31 <= radius2 <= 32 * 32:
                pixel = (0x34, 0x39, 0x41, 255)
            if radius2 <= 24 * 24:
                pixel = GREEN + (255,)
            if radius2 <= 5 * 5:
                pixel = (0xE8, 0xEB, 0xEE, 255)
            if radius2 <= 2 * 2:
                pixel = (0x11, 0x13, 0x18, 255)
            if (x - center) ** 2 + (y - (center - 39)) ** 2 <= 3 * 3:
                pixel = GREEN + (255,)
            if pixel is not None:
                art.putpixel((x, y), pixel)
    return art


def demo_art(size: int) -> Image.Image:
    """A generated placeholder, never presented as a fetched Spotify cover."""
    image = Image.new("RGBA", (size, size), (27, 35, 77, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, size - 9, size - 9), outline=(53, 205, 202), width=2)
    for radius in (39, 31, 23):
        draw.ellipse((56 - radius, 56 - radius, 56 + radius, 56 + radius),
                     outline=(255, 89, 162), width=3)
    draw.line((12, 85, 99, 28), fill=(233, 237, 255), width=4)
    draw.text((56, 84), "DEMO", fill=WHITE, font=font(13), anchor="mt")
    return image


def timecode(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def media_view(source: str, sample: dict, *, mode: str, state: str,
               media_source: str, dj_extras: list[str] | None = None,
               theme: str = "green") -> Image.Image:
    body = section(source, "createMediaScreen")
    width, height = define(source, "SCREEN_WIDTH"), define(source, "SCREEN_HEIGHT")
    image = Image.new("RGB", (width, height), color(body, "media_screen", "bg_color"))
    draw = ImageDraw.Draw(image)
    accent = theme_color(source, "focusAccentHex", theme)
    bx, by = pos(body, "media_brand_label")
    text(draw, (bx, by), static_text(body, "media_brand_label"), accent, 10)
    sx, sy = align(body, "media_source_label", "TOP_RIGHT")
    text(draw, (width + sx, sy), media_source, (0xD5, 0xD9, 0xDE), 10, right=True)

    art_x, art_y = pos(body, "media_art_box")
    art_w, art_h = size(body, "media_art_box")
    radius = match_int(body, r"lv_obj_set_style_radius\(media_art_box,\s*(\d+)", "media art radius")
    if radius != art_w // 2 or art_w != art_h:
        raise ValueError("Unsupported noncircular media art box")
    if not 144 <= art_w <= 152 or art_x * 2 + art_w != width:
        raise ValueError("Media circle must be centered at 144–152 px")
    box_color = WHITE if mode == "dj" else color(body, "media_art_box", "bg_color")
    border_color = WHITE if mode == "dj" else color(body, "media_art_box", "border_color")
    draw.ellipse((art_x, art_y, art_x + art_w - 1, art_y + art_h - 1),
                 fill=box_color, outline=border_color, width=1)
    if mode == "dj":
        # Firmware fills the 64x64 canvas white, draws these layers in order,
        # and renders sparse DJ pixels as opaque regardless of stored alpha.
        names = ["standardbody1", "stock_face", "dj_glasses", "dj_mixer_board", "twopawsup"]
        names += dj_extras or []
        cat = compose(names, white_background=True)
        zoom = define(source, "MEDIA_CAT_ZOOM")
        cat_px = define(source, "CAT_SIZE") * zoom // 256
        if cat_px > art_w - 4:
            raise ValueError("DJ canvas zoom is clipped by circle")
        cat = cat.resize((cat_px, cat_px), Image.Resampling.NEAREST)
        viewport = Image.new("RGBA", (art_w, art_h), (0, 0, 0, 0))
        viewport.alpha_composite(cat, ((art_w - cat_px) // 2, (art_h - cat_px) // 2))
        clip = Image.new("L", (art_w, art_h), 0)
        ImageDraw.Draw(clip).ellipse((1, 1, art_w - 2, art_h - 2), fill=255)
        viewport.putalpha(Image.composite(viewport.getchannel("A"),
                                          Image.new("L", (art_w, art_h)), clip))
        image.paste(viewport, (art_x, art_y), viewport)
    else:
        art_size = define(source, "MEDIA_ART_SIZE")
        art = vinyl_art(art_size) if mode == "vinyl" else demo_art(art_size)
        zoom = match_int(source, r"lv_img_set_zoom\(media_art_image,\s*(\d+)\)", "media image zoom")
        pixels = art_size * zoom // 256
        if pixels > art_w - 4:
            raise ValueError("Album/vinyl zoom is clipped by circle")
        art = art.resize((pixels, pixels), Image.Resampling.NEAREST)
        mask = Image.new("L", (art_w, art_h), 0)
        ImageDraw.Draw(mask).ellipse((1, 1, art_w - 2, art_h - 2), fill=255)
        cropped = Image.new("RGBA", (art_w, art_h), (0, 0, 0, 0))
        cropped.alpha_composite(art, ((art_w - pixels) // 2, (art_h - pixels) // 2))
        cropped.putalpha(Image.composite(cropped.getchannel("A"), Image.new("L", (art_w, art_h)), mask))
        image.paste(cropped, (art_x, art_y), cropped)

    px, py = pos(body, "info_panel")
    pw, ph = size(body, "info_panel")
    panel_radius = match_int(body, r"lv_obj_set_style_radius\(info_panel,\s*(\d+)", "media panel radius")
    draw.rounded_rectangle((px, py, px + pw - 1, py + ph - 1), radius=panel_radius,
                           fill=color(body, "info_panel", "bg_color"),
                           outline=color(body, "info_panel", "border_color"), width=1)
    tx, ty = pos(body, "media_title_label")
    title_width = match_int(body, r"lv_obj_set_width\(media_title_label,\s*(\d+)\)", "media title width")
    text(draw, (px + tx, py + ty), clipped(sample["title"], font(16), title_width), WHITE, 16)
    ax, ay = pos(body, "media_artist_label")
    artist_width = match_int(body, r"lv_obj_set_width\(media_artist_label,\s*(\d+)\)", "media artist width")
    text(draw, (px + ax, py + ay), clipped(sample["artist"], font(14), artist_width),
         (0xD7, 0xDB, 0xE0), 14)
    gx, gy = pos(body, "media_progress_bar")
    gw, gh = size(body, "media_progress_bar")
    draw.rounded_rectangle((px + gx, py + gy, px + gx + gw - 1, py + gy + gh - 1),
                           radius=3, fill=(0x34, 0x39, 0x40))
    filled = round(gw * sample["elapsed_seconds"] / sample["duration_seconds"])
    draw.rounded_rectangle((px + gx, py + gy, px + gx + filled - 1, py + gy + gh - 1),
                           radius=3, fill=accent)
    ex, ey = pos(body, "media_elapsed_label")
    text(draw, (px + ex, py + ey), timecode(sample["elapsed_seconds"]),
         (0xC7, 0xCC, 0xD2), 10)
    dx, dy = align(body, "media_duration_label", "TOP_RIGHT")
    text(draw, (px + pw + dx, py + dy), timecode(sample["duration_seconds"]),
         (0xC7, 0xCC, 0xD2), 10, right=True)
    status_x, status_y = pos(body, "media_playback_status_label")
    status_width = match_int(body, r"lv_obj_set_width\(media_playback_status_label,\s*(\d+)\)", "status width")
    text(draw, (status_x + status_width // 2, status_y), state, accent, 10, center=True)
    hint_width, hint_height = size(body, "media_gesture_hint_label")
    hint_x, hint_y = pos(body, "media_gesture_hint_label")
    if media_source == sample["source_api"]:
        hint = "SWIPE DOWN  DJ CAT"
    else:
        hint = "TAP  PLAY/PAUSE\nSWIPE  PREV/NEXT  |  DOWN  DJ CAT"
    for index, line in enumerate(hint.split("\n")):
        text(draw, (hint_x + hint_width // 2, hint_y + index * 13), line,
             (0x74, 0x7B, 0x84), 10, center=True)
    if not (art_y + art_h + 4 <= py and
            py + ty + 20 < py + ay and
            py + ay + 17 < py + gy and
            py + gy + gh + 5 < py + ey and
            py + ey + 12 < py + ph and
            py + ph + 4 < status_y and
            status_y + 12 < hint_y and
            hint_y + (13 if "\n" in hint else 0) + 11 <= height):
        raise ValueError("Media layout has a vertical collision")
    if font(10).getlength(max(hint.split("\n"), key=len)) > hint_width - 8:
        raise ValueError("Media gesture hint clips horizontally")
    return image


def contact_sheet(views: list[dict], output: Path) -> None:
    columns = 3
    gap, label_height, top = 20, 32, 48
    card_w, card_h = 240, 320 + label_height
    rows = (len(views) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * card_w + (columns + 1) * gap,
                              top + rows * card_h + (rows + 1) * gap), (28, 33, 39))
    draw = ImageDraw.Draw(sheet)
    text(draw, (gap, 14), "BONGO CAT  /  SIMULERADE FÖRHANDSBILDER", WHITE, 17)
    for index, view in enumerate(views):
        col, row = index % columns, index // columns
        x, y = gap + col * (card_w + gap), top + gap + row * (card_h + gap)
        with Image.open(output / view["file"]) as opened:
            sheet.paste(opened.convert("RGB"), (x, y))
        draw.rectangle((x, y, x + card_w - 1, y + 319), outline=(102, 112, 122), width=1)
        text(draw, (x + 5, y + 325), view["name"], WHITE, 12)
    sheet.save(output / "contact_sheet_composed.png")


def sprite_sheet(output: Path) -> list[dict]:
    layers = {**CORE_LAYERS, **DJ_LAYERS}
    sprite_dir = output / "sprites"
    sprite_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    width, height, gap, label = 256, 256, 14, 26
    columns = 4
    rows = (len(layers) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * width + (columns + 1) * gap,
                              rows * (height + label) + (rows + 1) * gap), (236, 239, 241))
    draw = ImageDraw.Draw(sheet)
    for index, (name, path) in enumerate(layers.items()):
        x = gap + (index % columns) * (width + gap)
        y = gap + (index // columns) * (height + label + gap)
        tile = Image.new("RGBA", (64, 64), WHITE + (255,))
        tile.alpha_composite(load_layer(path, name in DJ_LAYERS))
        tile = tile.resize((width, height), Image.Resampling.NEAREST).convert("RGB")
        target = sprite_dir / f"{name}.png"
        tile.save(target)
        sheet.paste(tile, (x, y))
        draw.rectangle((x, y, x + width - 1, y + height - 1), outline=(140, 146, 150))
        text(draw, (x + 4, y + height + 4), name, (20, 24, 28), 12)
        entries.append({"name": name, "source": str(path.relative_to(ROOT)).replace("\\", "/"),
                        "file": str(target.relative_to(output)).replace("\\", "/")})
    sheet.save(output / "contact_sheet_sprites.png")
    return entries


def export(output: Path) -> None:
    source = FIRMWARE.read_text(encoding="utf-8")
    sprite_header = SPRITES_HEADER.read_text(encoding="utf-8")
    require(sprite_header, "LAYER_BODY = 0")
    require(sprite_header, "LAYER_TABLE")
    require(section(source, "sprite_manager_init"), "&standardbody1")
    require(section(source, "sprite_manager_init"), "&stock_face")
    require(section(source, "sprite_manager_init"), "&table1")
    require(section(source, "sprite_manager_init"), "&twopawsup")
    require(section(source, "renderMediaCat"), "lv_canvas_fill_bg(media_cat_canvas, lv_color_white(), LV_OPA_COVER)")
    require(section(source, "renderMediaCat"), "drawDjSprite(dj_glasses)")
    require(section(source, "renderMediaCat"), "drawDjSprite(dj_mixer_board)")
    require(section(source, "updateMediaCat"), "if (!media_is_playing) return")
    require(section(source, "refreshMediaUi"), 'media_source == "SPOTIFY API"')
    require(section(source, "refreshMediaUi"), '"SWIPE DOWN  DJ CAT"')
    require(section(source, "refreshMediaUi"), '"TAP  PLAY/PAUSE\\nSWIPE  PREV/NEXT  |  DOWN  DJ CAT"')
    require(section(source, "loadGenericVinyl"), "radius2 <= 46 * 46")
    require(section(source, "createFeatureOverlay"), "lv_obj_create(lv_layer_top())")
    require(section(source, "createFeatureOverlay"),
            "lv_obj_set_style_bg_opa(feature_overlay_backdrop, LV_OPA_COVER, 0)")
    require(section(source, "refreshFeatureOverlay"), "focusDarkAccentHex()")
    require(section(source, "touchButtonRect"), "lv_obj_get_coords(button, &area)")
    require(section(source, "selectFeaturePanel"), "menuChoiceForTap")
    require(section(source, "handleFocusTap"), "focusActionForTap")
    require(section(source, "handleFocusTap"), "focusSettingsActionForTap")
    require(section(source, "showFocusScreen"),
            "active_panel == PanelId::Focus && !focus_settings_open")
    require(section(source, "serviceFocusTimer"), "focusAdvance")
    require(section(source, "createFocusScreen"), "lv_font_montserrat_40")
    require(section(source, "createFocusSettingsScreen"), "focus_settings_save")
    require(section(source, "createLocalSettingsScreen"), "local_settings_back_button")
    check_dj_header()
    if (define(source, "SCREEN_WIDTH"), define(source, "SCREEN_HEIGHT")) != (240, 320):
        raise ValueError("Expected 240x320 output; update the preview renderer for new display size")

    output.mkdir(parents=True, exist_ok=True)
    composed = output / "composed"
    composed.mkdir(exist_ok=True)
    bongo = bongo_base(source, SAMPLE)
    artwork = media_view(source, SAMPLE, mode="artwork", state="PLAYING",
                         media_source=SAMPLE["source_api"])
    long_media = {**SAMPLE,
                  "title": "Midnight Circuit — Extended Session Mix / Live at the Observatory / Deluxe Remaster",
                  "artist": "The Extremely Long Demo Artist & Collaborators"}
    plans = [
        ("bongo", "Bongo-skärm", bongo, "IDLE_STAGE1", "CPU/RAM/WPM/tid är exempeldata."),
        ("dashboard", "Meny – Bongo aktiv", panel_menu(source, bongo, "bongo"), "PLAYING", "Gemensam panelmeny öppnad från Bongo, med Bongo markerad."),
        ("menu_player", "Meny – Spelare aktiv", panel_menu(source, artwork, "player"), "PLAYING", "Samma panelmeny öppnad från mediasidan, med Spelare markerad."),
        ("menu_focus", "Meny – Fokus aktiv", panel_menu(source, focus_view(source, "running"), "focus"), "FOCUS", "Samma meny öppnad från Fokus, med Fokus markerad."),
        ("menu_settings", "Meny – inställningar", panel_menu(source, local_settings_view(source), "settings"), "FOCUS", "Fjärde panelvalet är markerat."),
        ("menu_settings_pressed", "Meny – tryckt val", panel_menu(source, bongo, "bongo", pressed="settings"), "FOCUS", "Tryckfeedback under rå touch på inställningsvalet."),
        ("focus_idle", "Fokus – redo", focus_view(source, "idle"), "FOCUS", "Fast 25:00 före start; siffror och träffytor är simulerade."),
        ("focus_running", "Fokus – aktiv", focus_view(source, "running"), "FOCUS", "Exempel vid 12:34 återstående; nedräkningen körs lokalt på ESP32."),
        ("focus_start_pressed", "Fokus – tryckt Start", focus_view(source, "idle", pressed="start"), "FOCUS", "Tryckfeedback visas innan knappen aktiveras vid släpp."),
        ("focus_long", "Fokus – 120 min", focus_view(source, "long"), "FOCUS", "Längsta valbara minuter på timer och vald varaktighet."),
        ("focus_settings", "Tider – standard", focus_settings_view(source, 25, 5), "FOCUS", "Två kort med egna plus/minus-knappar, standardvärden och SPARA/TILLBAKA."),
        ("focus_settings_adjusted", "Tider – ändrade", focus_settings_view(source, 30, 6), "FOCUS", "Exempelvärden före SPARA; aktiv nedräkning ändras inte."),
        ("focus_settings_pressed", "Tider – tryckt Plus", focus_settings_view(source, 30, 6, pressed="focus_settings_focus_plus"), "FOCUS", "Tryckfeedback på ett korts plusknapp."),
        ("local_settings", "Inställningar – grön", local_settings_view(source), "FOCUS", "Separat sparade lokala val; standard är grön, automatisk Fokus av och LED på."),
        ("local_settings_cyan", "Inställningar – cyan", local_settings_view(source, "cyan"), "FOCUS", "Alternativ accentfärg; kattens sprites och omslag ändras inte."),
        ("local_settings_amber", "Inställningar – amber", local_settings_view(source, "amber"), "FOCUS", "Alternativ accentfärg på knappar och rubrik."),
        ("local_settings_pressed", "Inställningar – tryckt", local_settings_view(source, "cyan", pressed="theme"), "FOCUS", "Temaknappen visar tryckfeedback medan fingret hålls kvar."),
        ("focus_break_running", "Paus – aktiv", focus_view(source, "break_running"), "BREAK", "Automatisk paus med lokal nedräkning efter fokusslut."),
        ("focus_break_done", "Paus – klar", focus_view(source, "break_done"), "BREAK", "00:00 och PAUS KLAR väntar på START FOKUS."),
        ("focus_completed", "Fokus – klart", focus_view(source, "break_started"), "BREAK", "Stor central FOKUS KLART-avisering medan vald paus startar; LED visas inte."),
        ("bongo_focus_completed", "Bongo – Fokus klart", focus_cue_preview(source, bongo, kind="focus", compact=False), "BREAK", "Stor central slutsignal direkt vid fokusslut, även på Bongo."),
        ("bongo_focus_reminder", "Bongo – pausmärke", focus_cue_preview(source, bongo, kind="focus", compact=True), "BREAK", "Litet PAUS-märke mellan CPU och klocka efter tio sekunder."),
        ("player_focus_reminder", "Spelare – pausmärke", focus_cue_preview(source, artwork, kind="focus", compact=True), "BREAK", "Liten pauspåminnelse efter tio sekunder."),
        ("player_break_done", "Spelare – paus klar", focus_cue_preview(source, artwork, kind="break", compact=False), "BREAK", "Kort, stillsam PAUS KLAR-remsa när pausen slutar."),
        ("bongo_break_done", "Bongo – paus klar", focus_cue_preview(source, bongo, kind="break", compact=False), "BREAK", "Kort PAUS KLAR-remsa; inget kvarstående START-märke efter sex sekunder."),
        ("media_vinyl", "Medieskärm – vinyl", media_view(source, SAMPLE, mode="vinyl", state="PLAYING", media_source=SAMPLE["source_windows"]), "PLAYING", "Windows Spotify, generisk vinyl och styrinstruktioner."),
        ("media_artwork", "Medieskärm – omslag", artwork, "PLAYING", "Spotify API, syntetiskt DEMO-omslag och källanpassad hjälptext."),
        ("media_artwork_paused", "Medieskärm – paus", media_view(source, SAMPLE, mode="artwork", state="PAUSED", media_source=SAMPLE["source_api"]), "PAUSED", "Pausat omslag med stillastående status och tidsrad."),
        ("media_long_title", "Medieskärm – lång text", media_view(source, long_media, mode="artwork", state="PLAYING", media_source=SAMPLE["source_windows"]), "PLAYING", "Lång titel och artist visas klippta som en stillbild av LVGL:s rullande enradsetiketter."),
        ("media_cyan", "Medieskärm – cyan", media_view(source, SAMPLE, mode="artwork", state="PLAYING", media_source=SAMPLE["source_api"], theme="cyan"), "PLAYING", "Temaaccent i Spelarens rubrik, progress och status; omslagets färger är oförändrade."),
        ("dj_playing", "DJ – uppspelning", media_view(source, SAMPLE, mode="dj", state="PLAYING", media_source=SAMPLE["source_api"], dj_extras=SAMPLE["dj_playing_layers"]), "PLAYING", "En vald bildruta med L1/R2 och effekt R1; lokalt slumpförlopp simuleras inte."),
        ("dj_paused", "DJ – paus", media_view(source, SAMPLE, mode="dj", state="PAUSED", media_source=SAMPLE["source_api"], dj_extras=SAMPLE["dj_paused_layers"]), "PAUSED", "Den senast spelade DJ-rutan förblir stilla när media pausas."),
    ]
    views = []
    for key, name, image, state, note in plans:
        path = composed / f"{key}.png"
        image.save(path)
        views.append({"id": key, "name": name,
                      "file": str(path.relative_to(output)).replace("\\", "/"),
                      "dimensions": [240, 320], "classification": "simulerad förhandsbild",
                      "media_state": state, "note": note, "sha256": sha256(path)})
    contact_sheet(views, output)
    sprite_entries = sprite_sheet(output)
    sources = [FIRMWARE, ROOT / "src" / "focus_logic.h", ROOT / "lv_conf.h",
               SPRITES_HEADER, DJ_HEADER, *CORE_LAYERS.values(), *DJ_LAYERS.values()]
    manifest = {
        "classification": "simulerade förhandsbilder",
        "display_pixels": [240, 320],
        "generator": "tools/export_ui_visuals.py",
        "command": "python tools/export_ui_visuals.py",
        "example_data": SAMPLE,
        "views": views,
        "contact_sheet": "contact_sheet_composed.png",
        "sprite_contact_sheet": "contact_sheet_sprites.png",
        "sprites": sprite_entries,
        "source_sha256": {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in sources},
        "rendering_limits": [
            "Pillow approximates LVGL font metrics, antialiasing, RGB565 colour and widget borders.",
            "The RGB LED's three green completion pulses and their hardware brightness are not represented in PNG previews.",
            "The Bongo and DJ sprite order and nearest-neighbour zoom follow firmware, but actual TFT clipping and colour need a device photo.",
            "The album cover is generated example art; it is not a Spotify cover or a serial transfer test.",
            "Long media titles and artists are shown as clipped still frames; LVGL's circular scroll animation needs a device check.",
            "The DJ playing image is one selected frame, not a test of random timing or pause transitions.",
            "Focus text, the 25-minute countdown, raw button hits, and the completion cue require a physical display test.",
            "Touch targets, gestures, serial communication, progress timing and physical display behaviour require hardware testing.",
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(views)} simulated 240x320 views to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "visuals")
    args = parser.parse_args()
    export(args.output.resolve())


if __name__ == "__main__":
    main()
