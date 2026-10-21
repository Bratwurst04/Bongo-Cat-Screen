"""Read actual Player geometry; add a review-only overlay to the frozen preview."""
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
import export_ui_visuals as v

SEEK = [16, 262, 210, 31]
BASE = ROOT / "visuals/focus-countdown/status-tap-implemented-2026-10-12/composed/player_focus.png"


def disjoint(a, b):
    x, y, w, h = a
    xx, yy, ww, hh = b
    return x + w <= xx or xx + ww <= x or y + h <= yy or yy + hh <= y


def contains(outer, inner):
    x, y, w, h = outer
    xx, yy, ww, hh = inner
    return x <= xx and y <= yy and xx + ww <= x + w and yy + hh <= y + h


def main():
    source = v.FIRMWARE.read_text(encoding="utf-8")
    body = v.section(source, "createMediaScreen")
    px, py = v.pos(body, "info_panel")
    pw, ph = v.size(body, "info_panel")
    border = v.match_int(body, r"lv_obj_set_style_border_width\(info_panel,\s*(\d+)", "border")
    pad = v.match_int(body, r"lv_obj_set_style_pad_all\(info_panel,\s*(\d+)", "padding")
    assert [px, py, pw, ph, border, pad] == [8, 205, 224, 90, 1, 0]
    gx, gy = v.pos(body, "media_progress_bar")
    gw, gh = v.size(body, "media_progress_bar")
    progress = [px + border + gx, py + border + gy, gw, gh]
    assert progress == [19, 264, 204, 6]
    ex, ey = v.pos(body, "media_elapsed_label")
    dx, dy = v.align(body, "media_duration_label", "TOP_RIGHT")
    elapsed_pos = [px + border + ex, py + border + ey]
    duration_right_y = [px + pw - border + dx, py + border + dy]
    face = v.lvgl_ascii_font("montserrat_10")
    assert face["height"] == 11 and elapsed_pos == [19, 278] and duration_right_y == [221, 278]
    elapsed_width = sum(v.lvgl_advances(face, "1:22"))
    duration_width = sum(v.lvgl_advances(face, "3:33"))
    times = [[*elapsed_pos, elapsed_width, face["height"]],
             [duration_right_y[0] - duration_width, duration_right_y[1], duration_width, face["height"]]]
    ax, ay = v.pos(body, "media_artist_label")
    artist = [px + border + ax, py + border + ay, 204, v.lvgl_ascii_font("montserrat_14")["height"]]
    tx, ty = v.pos(body, "media_title_label")
    title = [px + border + tx, py + border + ty, 204, v.lvgl_ascii_font("montserrat_16")["height"]]
    sx, sy = v.pos(body, "media_playback_status_label")
    status = [sx, sy, 224, v.lvgl_ascii_font("montserrat_14")["height"]]
    protected = {"title": title, "artist": artist, "playback_state": status,
                 "focus_status_touch": [36, 16, 168, 37],
                 "active_art": [48, 54, 144, 144], "inactive_art": [34, 26, 172, 172]}
    assert artist == [19, 238, 204, 16] and status == [8, 300, 224, 16]
    assert all(disjoint(SEEK, rect) for rect in protected.values())
    assert contains([px + border, py + border, pw - 2 * border, ph - 2 * border], SEEK)
    assert all(contains(SEEK, rect) for rect in [progress, *times])
    base = Image.open(BASE).convert("RGBA")
    assert base.size == (240, 320)
    # Exact copy of the approved source-derived preview, no resampling/redraw.
    (OUT / "player-original.png").write_bytes(BASE.read_bytes())
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    x, y, w, h = SEEK
    ImageDraw.Draw(overlay).rectangle((x, y, x + w - 1, y + h - 1),
                                    fill=(255, 153, 0, 48), outline=(255, 153, 0, 255), width=1)
    preview = Image.alpha_composite(base, overlay).convert("RGB")
    preview.save(OUT / "player-seek-overlay.png")
    assert all(preview.crop((xx, yy, xx + ww, yy + hh)).tobytes() == base.convert("RGB").crop((xx, yy, xx + ww, yy + hh)).tobytes()
               for xx, yy, ww, hh in protected.values())
    sheet = Image.new("RGB", (540, 410), (27, 33, 39))
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 12), "PLAYER / SEEK-TOUCH / GRANSKNINGSOVERLAY", font=v.font(15), fill=v.WHITE)
    sheet.paste(base.convert("RGB"), (20, 47))
    sheet.paste(preview, (280, 47))
    draw.text((20, 379), "Godkand F406-preview", font=v.font(13), fill=v.WHITE)
    draw.text((280, 379), "Startyta: 16,262,210,31", font=v.font(13), fill=v.WHITE)
    sheet.save(OUT / "touch-map.png")
    manifest = {
        "classification": "Review-only touch overlay on the approved F406 source-derived preview; no UI change",
        "dimensions": [240, 320], "seek_start_xywh_half_open": SEEK,
        "seek_start_touchrect_inclusive": [16, 262, 225, 292],
        "info_panel_xywh": [px, py, pw, ph], "border": border, "padding": pad,
        "actual_progress_xywh": progress, "actual_elapsed_label_position": elapsed_pos,
        "actual_duration_label_right_edge_exclusive_y": duration_right_y,
        "time_font": "lv_font_montserrat_10", "time_line_height": face["height"],
        "sample_time_rects": times, "protected_xywh": protected,
        "margins_from_progress": {"left": 3, "right": 3, "above": 2, "below": 23},
        "protected_overlap_checks_passed": True, "protected_preview_pixels_unchanged": True,
        "base_preview": str(BASE.relative_to(ROOT)).replace("\\", "/"), "base_preview_sha256": v.sha256(BASE),
        "geometry_function_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "source_sha256_at_render": v.sha256(v.FIRMWARE),
        "rendering_limit": "Existing preview uses approximate Pillow rendering for media metadata; normative geometry includes the actual LVGL 1px parent border.",
        "files": {name: v.sha256(OUT / name) for name in ("player-original.png", "player-seek-overlay.png", "touch-map.png")},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"seek": SEEK, "progress": progress, "time_y_and_height": [278, 11],
                      "artist": artist, "playback": status, "checks": "passed"}))


if __name__ == "__main__":
    main()
