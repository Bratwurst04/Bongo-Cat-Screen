"""Export current source-derived views and a review-only seek start area."""
import json
from pathlib import Path
import re
import export_ui_visuals as v
import focus_countdown_visuals

OUTPUT = v.ROOT / "visuals/media-seek-implemented-2026-10-12"


def export():
    header = v.ROOT / "src/media_seek_touch.h"
    source = header.read_text(encoding="utf-8")
    coords = re.search(r"mediaSeekRect\(\).*?return\s*\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\}", source)
    if coords is None:
        raise ValueError("Seek rectangle not found in actual firmware header")
    x, y, right, bottom = map(int, coords.groups())
    rect = [x, y, right-x+1, bottom-y+1]
    if rect != [16, 262, 210, 31]:
        raise ValueError("Seek start region differs from approved UI spec")
    firmware = v.FIRMWARE.read_text(encoding="utf-8")
    body = v.section(firmware, "createMediaScreen")
    parent = v.pos(body, "info_panel")
    border = v.match_int(body, r"lv_obj_set_style_border_width\(info_panel,\s*(\d+)", "info border")
    bar_child = v.pos(body, "media_progress_bar")
    bar_size = v.size(body, "media_progress_bar")
    bar = [parent[0]+border+bar_child[0], parent[1]+border+bar_child[1], *bar_size]
    if bar != [19, 264, 204, 6]:
        raise ValueError("Unexpected progress geometry")
    focus_countdown_visuals.export(v, OUTPUT)
    manifest_path = OUTPUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_sha256"]["src/media_seek_touch.h"] = v.sha256(header)
    manifest["source_sha256"]["tools/media_seek_visuals.py"] = v.sha256(Path(__file__))
    manifest["seek"] = {"start_xywh_half_open":rect, "bar_xywh":bar,
        "physical_right_delta_seconds":15, "physical_left_delta_seconds":-15,
        "release_can_leave_horizontal_ends":True, "overlay_is_review_only":True}
    manifest["rendering_limits"][1] = "Synthetic artwork and static samples; new seek hardware/heap/art2 tests pending. Orange outlines are review-only."
    overlays = []
    for state in ("focus", "focus_paused", "idle", "dj", "dj_idle"):
        view = next(item for item in manifest["views"] if item["id"] == "player_"+state)
        image = v.Image.open(OUTPUT / view["file"]).convert("RGB")
        v.ImageDraw.Draw(image).rectangle((x,y,right,bottom), outline=(255,128,0), width=1)
        path = OUTPUT / ("seek_map_player_"+state+".png")
        image.save(path)
        overlays.append({"file":path.name,"dimensions":[240,320],"sha256":v.sha256(path)})
    manifest["seek"]["overlays"] = overlays
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Actual seek region exported with",len(overlays),"review-only overlays")


if __name__ == "__main__":
    export()
