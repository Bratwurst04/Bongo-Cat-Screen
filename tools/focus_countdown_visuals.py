"""Source-derived simulation of the integrated local Focus status."""
import json
import re


def disjoint(a, b):
    x, y, w, h = a
    xx, yy, ww, hh = b
    return x + w <= xx or xx + ww <= x or y + h <= yy or yy + hh <= y


def media_layout(v, visible):
    source = (v.ROOT / "src/focus_countdown_layout.h").read_text(encoding="utf-8")
    presets = re.findall(r"FocusMediaLayout\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\}", source)
    if len(presets) != 2 or "return visible ?" not in source:
        raise ValueError("Unsupported active/inactive Focus media layout")
    x, y, size, radius, art_zoom, cat_zoom = map(int, presets[0 if visible else 1])
    return {"box_xywh": [x, y, size, size], "radius": radius,
            "art_zoom": art_zoom, "cat_zoom": cat_zoom}


def layout(v, source):
    bongo, player = v.section(source, "createBongoCat"), v.section(source, "createMediaScreen")
    rects, colors, fonts = {}, {}, {}
    card = [*v.pos(player, "media_focus_card"), *v.size(player, "media_focus_card")]
    border = v.match_int(player, r"lv_obj_set_style_border_width\(media_focus_card,\s*(\d+)", "card border")
    for panel, body in (("bongo", bongo), ("player", player)):
        for part in ("phase", "time"):
            obj = f"{'bongo' if panel == 'bongo' else 'media'}_focus_{part}_label"
            match = re.search(obj + r" = createFocusCountdownLabel\(\s*\w+,\s*&lv_font_(\w+),\s*(\d+),\s*(\d+),\s*"
                              r"LV_TEXT_ALIGN_(LEFT|RIGHT|CENTER),\s*0x([\da-fA-F]{6}),", body, re.S)
            if not match:
                raise ValueError(f"Unsupported countdown creation: {obj}")
            x, y = v.pos(body, obj)
            if panel == "player":
                x, y = x + card[0] + border, y + card[1] + border
            key = f"{panel}_{part}"
            rects[key] = [x, y, int(match[2]), int(match[3])]
            colors[key] = tuple(bytes.fromhex(match[5]))
            fonts[key] = {"name": match[1], "alignment": match[4]}
    for panel, body, obj, parent in (("bongo", bongo, "bongo_focus_pause_bars", "screen"),
                                    ("player", player, "media_focus_pause_bars", "media_focus_card")):
        dims = re.search(obj + r"\[i\] = createFocusCountdownBlock\(" + parent + r", (\d+), (\d+), 0x([\da-fA-F]{6})\)", body)
        pos = re.search(r"lv_obj_set_pos\(" + obj + r"\[i\], (\d+) \+ i \* (\d+), (\d+)\)", body)
        if not dims or not pos:
            raise ValueError("Missing separate pause bars")
        x, step, y = map(int, pos.groups())
        if panel == "player":
            x, y = x + card[0] + border, y + card[1] + border
        for i in range(2):
            key = f"{panel}_pause_{i}"
            rects[key] = [x + i * step, y, int(dims[1]), int(dims[2])]
            colors[key] = tuple(bytes.fromhex(dims[3]))
    active, inactive = media_layout(v, True), media_layout(v, False)
    if inactive["box_xywh"] != [*v.pos(player, "media_art_box"), *v.size(player, "media_art_box")]:
        raise ValueError("Initial art box differs from restored layout")
    for preset in (active, inactive):
        x, y, w, h = preset["box_xywh"]
        if x * 2 + w != 240 or y + h != 198 or preset["radius"] != w // 2:
            raise ValueError("Art box center/bottom/circular shape changed")
        for zoom, base in ((preset["art_zoom"], 112), (preset["cat_zoom"], 64)):
            if base * zoom // 256 != w - 4:
                raise ValueError("Art/DJ zoom no longer matches the circle inset")
    maxima = {key: 0 for key in fonts}
    for phase, limit in (("FOKUS", 7200), ("PAUS", 1800)):
        for panel in ("bongo", "player"):
            phase_key, time_key = f"{panel}_phase", f"{panel}_time"
            face = v.lvgl_ascii_font(fonts[phase_key]["name"])
            maxima[phase_key] = max(maxima[phase_key], sum(v.lvgl_advances(face, phase + (":" if panel == "bongo" else ""))))
            face = v.lvgl_ascii_font(fonts[time_key]["name"])
            for seconds in range(limit + 1):
                value = f"{seconds // 60:02}:{seconds % 60:02}"
                maxima[time_key] = max(maxima[time_key], sum(v.lvgl_advances(face, value)))
    for key, width in maxima.items():
        if width > rects[key][2] or v.lvgl_ascii_font(fonts[key]["name"])["height"] != rects[key][3]:
            raise ValueError(f"Countdown font clips in {key}")
    reserved = {"bongo": [(0, 82, 240, 238)],
                "player": [(0, 4, 240, 11), active["box_xywh"], (8, 205, 224, 90), (0, 300, 240, 20)]}
    face = v.lvgl_ascii_font("unscii_16")
    for obj, value in (("cpu_label", "CPU: 100%"), ("ram_label", "RAM: 100%"), ("wpm_label", "WPM: 200")):
        reserved["bongo"].append((*v.align(bongo, obj, "TOP_LEFT"), sum(v.lvgl_advances(face, value)), face["height"]))
    ox, y = v.align(bongo, "time_label", "TOP_RIGHT")
    clock_w = sum(v.lvgl_advances(face, "00:00"))
    reserved["bongo"].append((240 + ox - clock_w, y, clock_w, face["height"]))
    for key, rect in {**rects, "player_card": card}.items():
        panel = key.split("_")[0]
        x, y, w, h = rect
        if x < 0 or y < 0 or x + w > 240 or y + h > 320 or not all(disjoint(rect, other) for other in reserved[panel]):
            raise ValueError(f"Countdown collision in {key}")
        if panel == "player" and key != "player_card":
            if x < card[0] + border or y < card[1] + border or x + w > card[0] + card[2] - border or y + h > card[1] + card[3] - border:
                raise ValueError(f"Status child exceeds card inset: {key}")
    for panel in ("bongo", "player"):
        group = [key for key in rects if key.startswith(panel)]
        for i, first in enumerate(group):
            if any(not disjoint(rects[first], rects[other]) for other in group[i + 1:]):
                raise ValueError("Countdown parts overlap")
    touch_source = (v.ROOT / "src/focus_status_touch.h").read_text(encoding="utf-8")
    hit_rects = re.findall(r"TouchRect\{(\d+), (\d+), (\d+), (\d+)\}", touch_source)
    hits = {}
    for panel, match in zip(("bongo", "player"), hit_rects):
        x, y, right, bottom = map(int, match)
        hits[panel] = [x, y, right - x + 1, bottom - y + 1]
        if not all(disjoint(hits[panel], other) for other in reserved[panel]):
            raise ValueError(f"Status touch area collision: {panel}")
    if set(hits) != {"bongo", "player"}:
        raise ValueError("Missing status hit areas")
    return {"labels_xywh": rects, "colors": colors, "fonts": fonts, "max_text_widths": maxima,
            "hit_xywh_half_open": hits,
            "reserved_xywh": reserved, "player_card_xywh": card, "card_border": border,
            "card_radius": v.match_int(player, r"lv_obj_set_style_radius\(media_focus_card,\s*(\d+)", "card radius"),
            "card_bg": v.color(player, "media_focus_card", "bg_color"),
            "card_border_color": v.color(player, "media_focus_card", "border_color"),
            "active_media": active, "inactive_media": inactive, "overlap_checks_passed": True}


def draw_label(v, image, rect, value, color, font):
    x, y, w, _ = rect
    face = v.lvgl_ascii_font(font["name"])
    width = sum(v.lvgl_advances(face, value))
    x += w - width if font["alignment"] == "RIGHT" else (w - width) // 2 if font["alignment"] == "CENTER" else 0
    return v.lvgl_text(image, (x, y), value, color, face)


def export(v, output):
    source = v.FIRMWARE.read_text(encoding="utf-8")
    geometry = layout(v, source)
    rects, colors, fonts = (geometry[key] for key in ("labels_xywh", "colors", "fonts"))
    v.check_dj_header()
    output.mkdir(parents=True, exist_ok=True)
    (output / "composed").mkdir(exist_ok=True)
    states = [("focus", "focus", "04:59", False, False, "green"),
              ("break", "break", "00:59", False, False, "green"),
              ("focus_paused", "focus", "04:31", True, False, "green"),
              ("break_paused", "break", "00:42", True, False, "green"),
              ("long_paused", "focus", "120:00", True, False, "green"),
              ("idle", None, "", False, False, "green"),
              ("compact_cue", "break", "00:59", False, True, "green"),
              ("compact_cue_paused", "break", "00:42", True, True, "green"),
              ("dj", "focus", "04:59", False, False, "green"),
              ("dj_idle", None, "", False, False, "green"),
              ("cyan_cue", "break", "00:59", False, True, "cyan")]
    views = []
    for state, phase, time, paused, cue, theme in states:
        sample = {**v.SAMPLE, "cpu_percent": 100, "ram_percent": 100, "wpm": 200} if state == "long_paused" else v.SAMPLE
        for panel in ("bongo", "player"):
            image = v.bongo_base(source, sample) if panel == "bongo" else v.media_view(
                source, sample, mode="dj" if state.startswith("dj") else "artwork", state="PLAYING", theme=theme,
                focus_active=bool(phase), media_source="SPOTIFY API PAUSED" if state.startswith("dj") else sample["source_api"])
            bounds = []
            draw = v.ImageDraw.Draw(image)
            if phase:
                caption = "FOKUS" if phase == "focus" else "PAUS"
                if panel == "player":
                    x, y, w, h = geometry["player_card_xywh"]
                    draw.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=geometry["card_radius"],
                        fill=v.theme_color(source, "focusDarkAccentHex", theme) if cue else geometry["card_bg"],
                        outline=v.theme_color(source, "focusAccentHex", theme) if cue else geometry["card_border_color"], width=geometry["card_border"])
                parts = ["phase", "time"] + (["pause_0", "pause_1"] if paused else [])
                for part in parts:
                    key = f"{panel}_{part}"
                    tint = v.theme_color(source, "focusAccentHex", theme) if key == "player_phase" or (key == "bongo_phase" and cue) else colors[key]
                    if part in ("phase", "time"):
                        value = caption + (":" if panel == "bongo" else "") if part == "phase" else time
                        bounds += draw_label(v, image, rects[key], value, tint, fonts[key])
                    else:
                        x, y, w, h = rects[key]
                        draw.rectangle((x, y, x + w - 1, y + h - 1), fill=tint)
                        bounds.append((x, y, w, h))
            for box in bounds:
                if not all(disjoint(box, other) for other in geometry["reserved_xywh"][panel]):
                    raise ValueError(f"Actual glyph collision: {panel}/{state}/{box}")
            name = f"{panel}_{state}"
            path = output / "composed" / f"{name}.png"
            image.save(path)
            views.append({"id": name, "name": name, "file": f"composed/{name}.png", "dimensions": [240, 320],
                          "phase": phase, "time": time, "paused": paused, "compact_cue": cue, "theme": theme,
                          "media_layout": geometry["active_media" if phase else "inactive_media"] if panel == "player" else None,
                          "glyph_boxes": bounds, "sha256": v.sha256(path)})
    v.contact_sheet(views, output)
    for panel in ("bongo", "player"):
        view = next(item for item in views if item["id"] == panel + "_focus")
        annotated = v.Image.open(output / view["file"]).convert("RGB")
        x, y, w, h = geometry["hit_xywh_half_open"][panel]
        v.ImageDraw.Draw(annotated).rectangle((x, y, x + w - 1, y + h - 1), outline=(255, 128, 0), width=1)
        annotated.save(output / ("touch_map_" + panel + ".png"))
    sources = [v.FIRMWARE, v.ROOT / "src/focus_logic.h", v.ROOT / "src/focus_countdown.h", v.ROOT / "src/focus_countdown_layout.h", v.ROOT / "src/focus_status_touch.h",
               v.ROOT / "tools/export_ui_visuals.py", v.ROOT / "tools/focus_countdown_visuals.py", v.ROOT / "lv_conf.h",
               *(v.lvgl_ascii_font(f)["path"] for f in ("unscii_16", "montserrat_10", "montserrat_14", "montserrat_16")),
               v.SPRITES_HEADER, v.DJ_HEADER, *v.CORE_LAYERS.values(), *v.DJ_LAYERS.values()]
    manifest = {"classification": "source-derived simulation, not a physical display test", "display_pixels": [240, 320],
                "layout": geometry, "views": views, "contact_sheet": "contact_sheet_composed.png",
                "source_sha256": {str(p.relative_to(v.ROOT)).replace("\\", "/"): v.sha256(p) for p in sources},
                "rendering_limits": ["Actual LVGL countdown glyphs/metrics and integer label alignment, including parent border inset; other text/borders use Pillow.",
                                     "Synthetic artwork and static sample data; physical heap, touch and art2 smoothness pending on this status-tap candidate. Orange touch-map outlines are review-only.",
                                     "Existing large completion cues intentionally overlay content; compact FocusDone uses the integrated status."]}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(views)} source-derived simulated 240x320 status-tap views to {output}")
