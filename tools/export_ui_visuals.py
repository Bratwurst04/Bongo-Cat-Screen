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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section(source: str, function: str) -> str:
    match = re.search(r"\b(?:void|bool)\s+" + re.escape(function) + r"\s*\([^)]*\)\s*\{", source)
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


def panel_menu(source: str, sample: dict, base: Image.Image, active_panel: str) -> Image.Image:
    image = base.copy()
    body = section(source, "createFeatureOverlay")
    width, height = size(body, "feature_overlay")
    ox, oy = align(body, "feature_overlay", "CENTER")
    x = (image.width - width) // 2 + ox
    y = (image.height - height) // 2 + oy
    padding = match_int(body, r"lv_obj_set_style_pad_all\(feature_overlay,\s*(\d+)", "overlay padding")
    border = match_int(body, r"lv_obj_set_style_border_width\(feature_overlay,\s*(\d+)", "overlay border")
    radius = match_int(body, r"lv_obj_set_style_radius\(feature_overlay,\s*(\d+)", "overlay radius")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((x, y, x + width - 1, y + height - 1), radius=radius,
                           fill=color(body, "feature_overlay", "bg_color"),
                           outline=color(body, "feature_overlay", "border_color"), width=border)
    cx, cy = x + padding + border, y + padding + border
    text(draw, (x + width // 2, cy), static_text(body, "feature_overlay_label"), GREEN, 14, center=True)
    for panel, button, label in (
        ("bongo", "feature_overlay_bongo_button", "feature_overlay_bongo_label"),
        ("player", "feature_overlay_player_button", "feature_overlay_player_label"),
    ):
        bx, by = pos(body, button)
        bw, bh = size(body, button)
        selected = active_panel == panel
        draw.rounded_rectangle((cx + bx, cy + by, cx + bx + bw - 1, cy + by + bh - 1),
                               radius=10, fill=(0x1B, 0x30, 0x25) if selected else (0x17, 0x1A, 0x1F),
                               outline=GREEN if selected else (0x4C, 0x55, 0x5D),
                               width=2 if selected else 1)
        caption = static_text(body, label).replace("  AKTIV", "")
        if selected:
            caption += "  AKTIV"
        text(draw, (cx + bx + bw // 2, cy + by + (bh - 14) // 2),
             caption, GREEN if selected else WHITE, 14, center=True)
    sx, sy = pos(body, "feature_overlay_stats_label")
    stats = f"CPU {sample['cpu_percent']}%   RAM {sample['ram_percent']}%\nWPM {sample['wpm']}   TIME {sample['time']}"
    for row, yy in zip(stats.split("\n"), (cy + sy, cy + sy + 13)):
        text(draw, (cx + sx, yy), row, WHITE, 10)
    mx, my = pos(body, "feature_overlay_media_label")
    text(draw, (cx + mx, cy + my), "MEDIA  PLAYING", GREEN, 10)
    tx, ty = pos(body, "feature_overlay_title_label")
    title_width = size(body, "feature_overlay_title_label")[0]
    text(draw, (cx + tx, cy + ty), clipped(sample["title"], font(10), title_width), WHITE, 10)
    hx, hy = pos(body, "feature_overlay_hint_label")
    text(draw, (cx + hx, cy + hy), static_text(body, "feature_overlay_hint_label"),
         (0xD5, 0xD9, 0xDE), 10)
    kx, ky = pos(body, "feature_overlay_count_label")
    text(draw, (cx + kx, cy + ky), f"BONKS  {sample['bonks']}", GREEN, 10)
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
               media_source: str, dj_extras: list[str] | None = None) -> Image.Image:
    body = section(source, "createMediaScreen")
    width, height = define(source, "SCREEN_WIDTH"), define(source, "SCREEN_HEIGHT")
    image = Image.new("RGB", (width, height), color(body, "media_screen", "bg_color"))
    draw = ImageDraw.Draw(image)
    bx, by = pos(body, "brand")
    text(draw, (bx, by), static_text(body, "brand"), GREEN, 10)
    sx, sy = align(body, "media_source_label", "TOP_RIGHT")
    text(draw, (width + sx, sy), media_source, (0xD5, 0xD9, 0xDE), 10, right=True)

    art_x, art_y = pos(body, "media_art_box")
    art_w, art_h = size(body, "media_art_box")
    radius = match_int(body, r"lv_obj_set_style_radius\(media_art_box,\s*(\d+)", "media art radius")
    if radius != art_w // 2 or art_w != art_h:
        raise ValueError("Unsupported noncircular media art box")
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
    text(draw, (px + tx, py + ty), clipped(sample["title"], font(14), title_width), WHITE, 14)
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
                           radius=3, fill=GREEN)
    ex, ey = pos(body, "media_elapsed_label")
    text(draw, (ex, ey), timecode(sample["elapsed_seconds"]), (0xC7, 0xCC, 0xD2), 10)
    dx, dy = align(body, "media_duration_label", "TOP_RIGHT")
    text(draw, (width + dx, dy), timecode(sample["duration_seconds"]),
         (0xC7, 0xCC, 0xD2), 10, right=True)
    status_x, status_y = pos(body, "media_playback_status_label")
    status_width = match_int(body, r"lv_obj_set_width\(media_playback_status_label,\s*(\d+)\)", "status width")
    text(draw, (status_x + status_width // 2, status_y), state, GREEN, 10, center=True)
    hint_width, hint_height = size(body, "media_gesture_hint_label")
    hint_x, hint_bottom = align(body, "media_gesture_hint_label", "BOTTOM_MID")
    hint_y = height - hint_height + hint_bottom
    if media_source == sample["source_api"]:
        hint = "SWIPE DOWN  DJ CAT"
    else:
        hint = "TAP  PLAY/PAUSE\nSWIPE  PREV/NEXT  |  DOWN  DJ CAT"
    for index, line in enumerate(hint.split("\n")):
        text(draw, (width // 2 + hint_x, hint_y + index * 13), line,
             (0x74, 0x7B, 0x84), 10, center=True)
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
    require(section(source, "refreshFeatureOverlay"), "0x1B3025 : 0x171A1F")
    hit_test = section(source, "touchWithinMenuButton")
    for expected in ("TOUCH_RAW_TOP", "TOUCH_RAW_SIDE_MIN", "area.x1", "area.y1"):
        require(hit_test, expected)
    check_dj_header()
    if (define(source, "SCREEN_WIDTH"), define(source, "SCREEN_HEIGHT")) != (240, 320):
        raise ValueError("Expected 240x320 output; update the preview renderer for new display size")

    output.mkdir(parents=True, exist_ok=True)
    composed = output / "composed"
    composed.mkdir(exist_ok=True)
    bongo = bongo_base(source, SAMPLE)
    artwork = media_view(source, SAMPLE, mode="artwork", state="PLAYING",
                         media_source=SAMPLE["source_api"])
    plans = [
        ("bongo", "Bongo-skärm", bongo, "IDLE_STAGE1", "CPU/RAM/WPM/tid är exempeldata."),
        ("dashboard", "Meny – Bongo aktiv", panel_menu(source, SAMPLE, bongo, "bongo"), "PLAYING", "Gemensam panelmeny öppnad från Bongo, med Bongo markerad."),
        ("menu_player", "Meny – Spelare aktiv", panel_menu(source, SAMPLE, artwork, "player"), "PLAYING", "Samma panelmeny öppnad från mediasidan, med Spelare markerad."),
        ("media_vinyl", "Medieskärm – vinyl", media_view(source, SAMPLE, mode="vinyl", state="PLAYING", media_source=SAMPLE["source_windows"]), "PLAYING", "Windows Spotify, generisk vinyl och styrinstruktioner."),
        ("media_artwork", "Medieskärm – omslag", artwork, "PLAYING", "Spotify API, syntetiskt DEMO-omslag och källanpassad hjälptext."),
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
    sources = [FIRMWARE, SPRITES_HEADER, DJ_HEADER, *CORE_LAYERS.values(), *DJ_LAYERS.values()]
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
            "The Bongo and DJ sprite order and nearest-neighbour zoom follow firmware, but actual TFT clipping and colour need a device photo.",
            "The album cover is generated example art; it is not a Spotify cover or a serial transfer test.",
            "The DJ playing image is one selected frame, not a test of random timing or pause transitions.",
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
