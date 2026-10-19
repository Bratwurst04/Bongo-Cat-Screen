"""New previews only: actual C++ projection/state and actual firmware glyphs."""
import ctypes
import hashlib
import json
from pathlib import Path
import re
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'tools')]
from record_flip_host import load_host
import export_ui_visuals as v

OUTPUT = ROOT / 'visuals/record-flip-2026-10-15'
SAMPLES = ROOT / 'visuals/media-seek-implemented-2026-10-12/composed'
WORDS = ctypes.c_ushort * (112 * 112)


def rgb565(color):
    r, g, b = color
    value = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    return ((value & 255) << 8) | (value >> 8)  # LV_COLOR_16_SWAP=1.


PALETTE = (ctypes.c_ushort * 5)(*(rgb565(c) for c in
    ((0, 255, 0), (17, 19, 24), (52, 57, 65), (30, 215, 96), (232, 235, 238))))


def album(color):
    image = Image.new('RGB', (112, 112), (0, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((1, 1, 110, 110), fill=color)
    draw.line((18, 83, 78, 21), fill=(242, 244, 247), width=12)
    draw.ellipse((47, 47, 64, 64), fill=(17, 19, 24))
    return WORDS(*(rgb565(c) for c in image.get_flattened_data()))


def glyph_data(size):
    source = (ROOT / 'src/media_swedish_font.h').read_text(encoding='utf-8')
    name = 'media_swedish_' + str(size)
    bitmap = bytes(int(x, 16) for x in re.findall(r'0x([0-9a-f]{2})',
        re.search(name + r'_bitmap\[\] = \{(.*?)\};', source, re.S)[1]))
    ds = [tuple(map(int, row.split(','))) for row in re.findall(r'\{([^{}]+)\}',
        re.search(name + r'_glyphs\[\] = \{(.*?)\};', source, re.S)[1])]
    return bitmap, dict(zip('ÄÅÖäåö', ds[1:]))


def media_text(image, xy, value, size, color):
    face = v.lvgl_ascii_font('montserrat_' + str(size))
    custom, glyphs = glyph_data(size) if size in (14, 16) else (b'', {})
    x, y = xy
    bounds = []
    for i, char in enumerate(value):
        if char in glyphs:
            offset, advance, w, h, ox, oy = glyphs[char]
            bitmap = custom
            advance = (advance + 8) >> 4
        else:
            g = face['glyphs'][ord(char) - 31]
            offset, w, h, ox, oy = (g[k] for k in ('bitmap_index', 'box_w', 'box_h', 'ofs_x', 'ofs_y'))
            bitmap = face['bitmap']
            pair = value[i:i+2]
            advance = v.lvgl_advances(face, pair if all(ord(c) < 127 for c in pair) else char)[0]
        if w and h:
            mask = Image.new('L', (w, h))
            mask.putdata([((bitmap[offset + j // 2] >> (4 if j % 2 == 0 else 0)) & 15) * 17
                          for j in range(w * h)])
            gx, gy = x + ox, y + face['height'] - face['baseline'] - h - oy
            image.paste(color, (gx, gy), mask)
            bounds.append([gx, gy, w, h])
        x += advance
    return bounds


def media_width(value, size):
    face = v.lvgl_ascii_font('montserrat_' + str(size))
    _, glyphs = glyph_data(size) if size in (14, 16) else (b'', {})
    width = 0
    for i, char in enumerate(value):
        if char in glyphs: width += (glyphs[char][1] + 8) >> 4
        else:
            pair = value[i:i+2]
            width += v.lvgl_advances(face, pair if all(ord(c) < 127 for c in pair) else char)[0]
    return width


def scene(frame, pixels, compact=False, dj=False, title='Dö ung', artist='Hov1', paused=False, scroll=0):
    path = ('player_dj.png' if compact else 'player_dj_idle.png') if dj else 'player_focus.png' if compact else 'player_idle.png'
    image = Image.open(SAMPLES / path).convert('RGB')
    draw = ImageDraw.Draw(image)
    if not dj:
        x, y, size = (48, 54, 144) if compact else (34, 26, 172)
        draw.ellipse((x, y, x + size - 1, y + size - 1), fill=(8, 10, 12), outline=(37, 42, 48))
        record = Image.new('RGBA', (112, 112))
        colors = []
        for raw in pixels:
            p = ((raw & 255) << 8) | (raw >> 8)
            c = (((p >> 11) & 31) * 255 // 31, ((p >> 5) & 63) * 255 // 63, (p & 31) * 255 // 31)
            colors.append((*c, 0 if raw == PALETTE[0] else 255))
        record.putdata(colors)
        zoom = 320 if compact else 384
        record = record.resize((112 * zoom // 256,) * 2, Image.Resampling.NEAREST)
        image.paste(record, (x + (size - record.width) // 2, y + (size - record.height) // 2), record)
    source = v.FIRMWARE.read_text(encoding='utf-8')
    body = v.section(source, 'createMediaScreen')
    parent = v.pos(body, 'info_panel')
    card_size = v.size(body, 'info_panel')
    def card_color(key):
        return tuple(bytes.fromhex(re.search(r'lv_obj_set_style_' + key + r'\(info_panel, lv_color_hex\(0x([0-9A-Fa-f]{6})\)', body)[1]))
    background = card_color('bg_color')
    border = card_color('border_color')
    draw.rounded_rectangle((parent[0], parent[1], parent[0] + card_size[0] - 1, parent[1] + card_size[1] - 1),
                           radius=10, fill=background, outline=border)
    for obj, value, font_size, color, height in (
            ('media_title_label', title, 16, (255, 255, 255), 22),
            ('media_artist_label', artist, 14, (215, 219, 224), 18)):
        cx, cy = v.pos(body, obj)
        xy = (parent[0] + 1 + cx, parent[1] + 1 + cy)
        layer = Image.new('RGB', (204, height), background)
        width = media_width(value, font_size)
        # Actual LVGL8 circular-copy spacing: three space glyphs.
        gap = 3 * media_width(' ', font_size)
        offset = scroll % (width + gap) if width > 204 else 0
        media_text(layer, (-offset, 0), value, font_size, color)
        if width > 204: media_text(layer, (width + gap - offset, 0), value, font_size, color)
        image.paste(layer, xy)
    px, py = v.pos(body, 'media_progress_bar')
    px += parent[0] + 1;py += parent[1] + 1
    pw, ph = v.size(body, 'media_progress_bar')
    draw.rounded_rectangle((px, py, px + pw - 1, py + ph - 1), radius=3, fill=(52, 57, 64))
    draw.rounded_rectangle((px, py, px + pw * 82 // 213, py + ph - 1), radius=3, fill=(30, 215, 96))
    media_text(image, (parent[0] + 11, parent[1] + 73), '1:22', 10, (199, 204, 210))
    media_text(image, (parent[0] + card_size[0] - 11 - media_width('3:33', 10), parent[1] + 73),
               '3:33', 10, (199, 204, 210))
    draw.rectangle((0, 298, 239, 319), fill=(8, 10, 12))
    word = 'PAUSED' if paused else 'PLAYING'
    media_text(image, ((240 - media_width(word, 14)) // 2, 300), word, 14, (30, 215, 96))
    return image


def render_scenario(name, compact=False, rapid=False, paused=False, interrupted=False,
                    focus_interrupt=False, panel_interrupt=False, oom=False):
    host = load_host();host.rf_reset()
    host.rf_event(0, 0, 0, 0)
    host.rf_event(3, 0, 0, 0)
    albums = [album(c) for c in ((170, 40, 110), (30, 100, 180), (220, 120, 20))]
    active = albums[0]
    host.rf_event(1, 1, 0, 1);host.rf_event(2, 101, 0, 1)
    frames, states = [], []
    output = WORDS();status = (ctypes.c_int * 3)()
    for now in range(0, 1041, 20):
        dj = interrupted and 100 <= now < 360
        if rapid and now == 100:
            active = albums[1];host.rf_event(3, 0, now, 1)
        if rapid and now == 200:
            host.rf_event(1, 2, now, 1);host.rf_event(2, 102, now, 1)
        if rapid and now == 300:
            active = albums[2];host.rf_event(3, 0, now, 1)
        if not rapid and now == 600:
            active = albums[1];host.rf_event(3, 0, now, not dj)
        other_panel = panel_interrupt and 100 <= now < 360
        host.rf_frame(now, not dj and not other_panel and not oom and not (focus_interrupt and now == 100), status)
        side, step, moving = status
        host.rf_render(output, active, side, step, moving, 0, 32767, PALETTE)
        if oom and side == 0:
            reduced = WORDS()
            host.rf_reduced(reduced, 64 * 64, PALETTE)
            for y in range(112):
                for x in range(112):output[y * 112 + x] = reduced[(y // 2) * 56 + x // 2]
        image = scene(status, output, compact or focus_interrupt and now >= 100, dj, paused=paused)
        if other_panel:image = Image.open(SAMPLES / 'bongo_idle.png').convert('RGB')
        frames.append(image)
        states.append(dict(ms=now, side=side, step=step, moving=bool(moving), dj=dj, playing=not paused,
                           compact=compact or focus_interrupt and now >= 100, other_panel=other_panel, oom=oom))
    frames[0].save(OUTPUT / (name + '.gif'), save_all=True, append_images=frames[1:],
                   duration=20, loop=0, disposal=2)
    return frames, states


def export():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sheets, all_states = [], {}
    for name, options in (
            ('normal', {}), ('focus', dict(compact=True)), ('rapid', dict(rapid=True)),
            ('paused', dict(compact=True, paused=True)), ('dj-interrupt', dict(interrupted=True)),
            ('focus-interrupt', dict(focus_interrupt=True)), ('panel-interrupt', dict(panel_interrupt=True)),
            ('oom-fallback', dict(oom=True))):
        frames, states = render_scenario(name, **options)
        all_states[name] = states
        frames[44].save(OUTPUT / (name + '-end.png'))
        indices = [0, 3, 6, 7, 10, 14] if name not in ('rapid', 'dj-interrupt') else [0, 5, 10, 15, 22, 30]
        row = Image.new('RGB', (720, 187), (29, 34, 40))
        d = ImageDraw.Draw(row)
        for column, index in enumerate(indices):
            row.paste(frames[index].resize((120, 160), Image.Resampling.NEAREST), (column * 120, 22))
            d.text((column * 120 + 3, 4), f'{name} {index * 20}ms', fill='white')
        sheets.append(row)
    glyph_image = Image.new('RGB', (480, 110), (23, 26, 31))
    for x, size in ((12, 16), (252, 14)):
        media_text(glyph_image, (x, 8), 'Dö ung', size, (255, 255, 255))
        media_text(glyph_image, (x, 38), 'Hov1', size, (215, 219, 224))
        media_text(glyph_image, (x, 68), 'åäöÅÄÖ', size, (255, 255, 255))
    glyph_image.save(OUTPUT / 'glyphs.png')
    # Actual glyphs and circular clipping/copy geometry at both label edges.
    host = load_host();output = WORDS();host.rf_render(output, album((30, 100, 180)), 1, 14, 0, 0, 32767, PALETTE)
    title = 'åäöÅÄÖ - Dö ung - Hov1 - åäöÅÄÖ'
    artist = 'ÅÄÖåäö - Hov1 - Dö ung - ÅÄÖåäö'
    period = media_width(title, 16) + 3 * media_width(' ', 16)
    scroll_frames = []
    for offset in range(0, period + 1, 4):
        pair = Image.new('RGB', (480, 320))
        for compact in (False, True):
            sample = scene((1, 14, 0), output, compact, title=title, artist=artist, scroll=offset)
            pair.paste(sample, (240 if compact else 0, 0))
        scroll_frames.append(pair)
    scroll_frames[0].save(OUTPUT/'scroll.gif', save_all=True, append_images=scroll_frames[1:],
                          duration=160, loop=0, disposal=2)
    scroll_sheet = Image.new('RGB', (480, 116 * 4), (29, 34, 40))
    for row, index in enumerate((0, 5, len(scroll_frames)//2, len(scroll_frames)-2)):
        scroll_sheet.paste(scroll_frames[index].crop((0,205,480,295)), (0,row*116+20))
        ImageDraw.Draw(scroll_sheet).text((4,row*116+2), f'offset {index*4}px / 3-space circular gap', fill='white')
    scroll_sheet.save(OUTPUT/'scroll-contact-sheet.png')
    sheet = Image.new('RGB', (720, 187 * len(sheets) + 135), (29, 34, 40))
    for index, row in enumerate(sheets):sheet.paste(row, (0, index * 187))
    sheet.paste(glyph_image, (0, 187 * len(sheets) + 15))
    sheet.save(OUTPUT / 'contact-sheet.png')
    files = ['src/media_record_flip.h', 'src/media_swedish_font.h', 'src/bongo_cat_featured.inc',
             'companion/engine.py', 'tests/record_flip_host.cpp', 'tests/record_flip_host.py',
             'tools/generate_media_swedish_font.py', 'tools/record_flip_visuals.py']
    manifest = dict(classification='Simulated: actual C++ state/projection and actual firmware glyph bitmaps; not ESP32 timing',
        frame_ms=20, flip_ms=280, glyph_samples=['Dö ung', 'Hov1', 'åäöÅÄÖ'],
        source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest().upper() for n in files},
        output_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest().upper()
                       for p in OUTPUT.iterdir() if p.suffix in ('.gif', '.png')},
        states=all_states, limitations=['Frozen zero-degree record angle for clarity; host timing is not ESP32 frame rate.',
            'Background reused from earlier source-derived fixtures; new record pixels and title/artist glyphs come from current solution.',
            'No actual TFT/rotation/serial timing or DPI/hardware acceptance.',
            'Rapid requests can interrupt/coalesce a flip rather than each receiving a full 280ms.',
            'Scroll samples use the actual 3-space circular-copy geometry and 4px/160ms sampling, not measured TFT timing.'])
    (OUTPUT / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(OUTPUT)


if __name__ == '__main__':
    # Keep earlier reviewed previews immutable when a concrete correction
    # requires a new source manifest within this feature's visual directory.
    if '--final' in sys.argv: OUTPUT = OUTPUT / 'final'
    export()
