#include "../src/focus_countdown_layout.h"
#include "../src/media_turntable.h"
#include <cstring>
#include <cstdio>
#include <initializer_list>

static_assert(!focusCountdownView(focusInitial()).visible &&
              !focusCountdownView(focusReset(0, {25, 5})).visible,
              "Idle and Prepared hide the local rows");
static_assert(!focusCountdownView({FocusPhase::Break, FocusMode::Completed, 0, 0, 60000}).visible,
              "Completed hides the row");
static_assert(focusCountdownView({FocusPhase::Focus, FocusMode::Running, 1, 0, 300000}).seconds == 1 &&
              focusCountdownView({FocusPhase::Focus, FocusMode::Running, 1000, 0, 300000}).seconds == 1 &&
              focusCountdownView({FocusPhase::Focus, FocusMode::Running, 1001, 0, 300000}).seconds == 2 &&
              focusCountdownView({FocusPhase::Focus, FocusMode::Running, 60001, 0, 300000}).seconds == 61,
              "Displayed seconds use ceiling, including minute boundary");
static_assert(focusCountdownView({FocusPhase::Focus, FocusMode::Paused, 7200000, 0, 7200000}).paused &&
              focusCountdownView({FocusPhase::Break, FocusMode::Paused, 1800000, 0, 1800000}).paused,
              "Both paused phases are visible with a pause marker");
static_assert(focusCountdownEqual(
                  focusCountdownView({FocusPhase::Focus, FocusMode::Running, 60000, 0, 300000}),
                  focusCountdownView({FocusPhase::Focus, FocusMode::Running, 59999, 1, 300000})),
              "Subsecond ticks have an identical display key");
static_assert(!focusCountdownEqual(
                  focusCountdownView({FocusPhase::Focus, FocusMode::Running, 60000, 0, 300000}),
                  focusCountdownView({FocusPhase::Focus, FocusMode::Paused, 60000, 0, 300000})) &&
              !focusCountdownEqual(
                  focusCountdownView({FocusPhase::Focus, FocusMode::Running, 60000, 0, 300000}),
                  focusCountdownView({FocusPhase::Break, FocusMode::Running, 60000, 0, 60000})),
              "Pause and phase changes invalidate even if the same seconds remain");
static_assert(focusCountdownView(focusAdvance(
                  {FocusPhase::Focus, FocusMode::Running, 1, 100, 300000}, 101, {5, 1})).phase == FocusPhase::Break &&
              !focusCountdownView(focusAdvance(
                  {FocusPhase::Break, FocusMode::Running, 1, 100, 60000}, 101, {5, 1})).visible,
              "Focus completion changes phase; break completion hides");

static_assert(focusMediaLayout(true).x == 48 && focusMediaLayout(true).y == 54 &&
              focusMediaLayout(true).size == 144 && focusMediaLayout(true).radius == 72 &&
              focusMediaLayout(true).art_zoom == 320 && focusMediaLayout(true).cat_zoom == 560,
              "Active geometry and both zooms match the approved design");
static_assert(focusMediaLayout(false).x == 34 && focusMediaLayout(false).y == 26 &&
              focusMediaLayout(false).size == 172 && focusMediaLayout(false).radius == 86 &&
              focusMediaLayout(false).art_zoom == 384 && focusMediaLayout(false).cat_zoom == 672,
              "Hidden status restores the original circle and both zooms");
static_assert(focusCountdownIntegratedCue(true, true, FocusCueKind::FocusDone, PanelId::Bongo, true) &&
              focusCountdownIntegratedCue(true, true, FocusCueKind::FocusDone, PanelId::Player, true) &&
              !focusCountdownIntegratedCue(true, false, FocusCueKind::FocusDone, PanelId::Bongo, true) &&
              !focusCountdownIntegratedCue(true, true, FocusCueKind::FocusDone, PanelId::Settings, true) &&
              !focusCountdownIntegratedCue(true, true, FocusCueKind::BreakDone, PanelId::Player, true) &&
              !focusCountdownIntegratedCue(false, true, FocusCueKind::FocusDone, PanelId::Player, true) &&
              !focusCountdownIntegratedCue(true, true, FocusCueKind::FocusDone, PanelId::Player, false),
              "Only a visible compact FocusDone on a visible Bongo/Player status integrates");

// Compile actual UI adapters against a recorder; no TFT pixel simulation.
using lv_text_align_t = int;
using lv_font_t = int;
constexpr int LV_TEXT_ALIGN_RIGHT = 1, LV_TEXT_ALIGN_CENTER = 2, LV_LABEL_LONG_CLIP = 1;
constexpr int LV_OBJ_FLAG_CLICKABLE = 1, LV_OBJ_FLAG_SCROLLABLE = 2, LV_OBJ_FLAG_HIDDEN = 4;
constexpr int LV_OBJ_FLAG_OVERFLOW_VISIBLE = 8;
constexpr lv_font_t font16 = 16, font14 = 14;
struct lv_obj_t {
    int flags = LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_SCROLLABLE;
    int width = 0, height = 0, writes = 0, visibility_changes = 0;
    int x = 0, y = 0, pos_changes = 0;
    int zoom = 256, zoom_changes = 0, radius = 0, centers = 0;
    uint32_t bg = 0, border = 0, text_color = 0;
    const char *text = nullptr;
};
lv_obj_t recorded_labels[4], recorded_bars[4];
lv_obj_t card, art_box, art_viewport, art_image, cat_canvas, state_label, arm_layer, paw_layer;
int labels_created = 0;
lv_obj_t *lv_label_create(lv_obj_t *) { return &recorded_labels[labels_created++]; }
void lv_label_set_text_static(lv_obj_t *obj, const char *text) { obj->text = text; ++obj->writes; }
void lv_label_set_long_mode(lv_obj_t *, int) {}
void lv_obj_set_size(lv_obj_t *obj, int w, int h) { obj->width = w; obj->height = h; }
int lv_obj_get_width(lv_obj_t *obj) { return obj->width; }
int lv_obj_get_height(lv_obj_t *obj) { return obj->height; }
int lv_obj_get_x(lv_obj_t *obj) { return obj->x; }
int lv_obj_get_y(lv_obj_t *obj) { return obj->y; }
void lv_obj_invalidate(lv_obj_t *) {}
void lv_obj_set_style_text_font(lv_obj_t *, const lv_font_t *, int) {}
uint32_t lv_color_hex(uint32_t color) { return color; }
void lv_obj_set_style_text_color(lv_obj_t *obj, uint32_t color, int) { obj->text_color = color; }
void lv_obj_set_style_text_align(lv_obj_t *, int, int) {}
bool lv_obj_has_flag(lv_obj_t *obj, int flag) { return (obj->flags & flag) != 0; }
void lv_obj_clear_flag(lv_obj_t *obj, int flags) {
    obj->flags &= ~flags;
    if (flags & LV_OBJ_FLAG_HIDDEN) ++obj->visibility_changes;
}
void lv_obj_add_flag(lv_obj_t *obj, int flags) {
    obj->flags |= flags;
    if (flags & LV_OBJ_FLAG_HIDDEN) ++obj->visibility_changes;
}
void lv_obj_set_pos(lv_obj_t *obj, int x, int y) { obj->x = x; obj->y = y; ++obj->pos_changes; }
void lv_obj_set_style_bg_color(lv_obj_t *obj, uint32_t color, int) { obj->bg = color; }
void lv_obj_set_style_border_color(lv_obj_t *obj, uint32_t color, int) { obj->border = color; }
void lv_obj_set_style_radius(lv_obj_t *obj, int radius, int) { obj->radius = radius; }
void lv_img_set_zoom(lv_obj_t *obj, int zoom) { obj->zoom = zoom; ++obj->zoom_changes; }
void lv_obj_center(lv_obj_t *obj) { ++obj->centers; }
const void *invalidated_image = nullptr;
int image_invalidations = 0;
void lv_img_cache_invalidate_src(const void *image) { invalidated_image = image; ++image_invalidations; }
void lv_img_set_src(lv_obj_t *, const void *) {}
void lv_img_set_pivot(lv_obj_t *, int, int) {}
void lv_img_set_angle(lv_obj_t *, int) {}
void lv_img_set_antialias(lv_obj_t *, bool) {}
uint32_t focusAccentHex() { return 0x1ED760; }
uint32_t focusDarkAccentHex() { return 0x163521; }
constexpr int MEDIA_ART_SIZE = 112, MEDIA_ART_LV_BYTES = 25088, LV_IMG_CF_TRUE_COLOR_CHROMA_KEYED = 1;
struct { struct { int cf, w, h; } header; int data_size; const uint8_t *data; } media_art_descriptor;
uint8_t mock_art[2][1], *media_art_buffers[2] = {mock_art[0], mock_art[1]};
uint8_t media_art_active_buffer = 0;
int media_vinyl_angle = 0, media_ui_refreshes = 0;
int media_cat_last_frame = 0, media_cat_left_note = 0, media_cat_right_note = 0, media_cat_effect = 0;
bool media_art_valid = false, media_cat_mode = false;
MediaTurntable media_record_flip;
uint32_t media_track_context_id = 0;
bool media_record_dirty = false;
uint32_t millis() { return 0; }
bool mediaRecordVisible() { return false; }
void refreshMediaUi() { ++media_ui_refreshes; }
struct SerialRecorder {
    int writes = 0;
    const char *last_line = nullptr;
    void println(const char *line) { last_line = line; ++writes; }
} Serial;
FocusCountdownCache focus_countdown;
FocusState focus_state = focusInitial();
lv_obj_t *bongo_focus_phase_label = nullptr, *bongo_focus_time_label = nullptr;
lv_obj_t *media_focus_phase_label = nullptr, *media_focus_time_label = nullptr;
lv_obj_t *media_focus_pause_bars[2] = {&recorded_bars[0], &recorded_bars[1]};
lv_obj_t *bongo_focus_pause_bars[2] = {&recorded_bars[2], &recorded_bars[3]};
lv_obj_t *media_focus_card = &card;
lv_obj_t *media_art_box = &art_box, *media_art_image = &art_image;
lv_obj_t *media_art_viewport = &art_viewport;
lv_obj_t *media_arm_layer = &arm_layer, *media_paw_layer = &paw_layer;
lv_obj_t *media_cat_canvas = &cat_canvas, *media_state_label = &state_label;
bool bongo_focus_compact_cue = false, media_focus_layout_active = false;
bool media_focus_compact_cue = false, focus_banner_visible = false, focus_banner_compact = false;
FocusCueKind focus_banner_kind = FocusCueKind::None;
PanelId focus_banner_panel = PanelId::Bongo;
#include "focus_countdown_test_fixture.inc"

int checks = 0;
#define CHECK(condition) do { ++checks; if (!(condition)) { \
    std::printf("FAILED line %d: %s\n", __LINE__, #condition); return 1; } } while (0)

int main() {
    FocusCountdownCache cache;
    CHECK(!cache.update(focusInitial()) && !cache.visible());
    CHECK(!cache.update(focusReset(1, {120, 30})));
    FocusState running = focusToggle(focusInitial({120, 30}), 10, {120, 30});
    CHECK(cache.update(running) && cache.visible());
    CHECK(std::strcmp(cache.phaseText(), "FOKUS:") == 0 && std::strcmp(cache.timeText(), "120:00") == 0);
    const char *phase_buffer = cache.phaseText(), *time_buffer = cache.timeText();
    CHECK(!cache.update(focusAdvance(running, 11, {120, 30})));
    CHECK(!cache.update(focusAdvance(running, 1009, {120, 30})));
    CHECK(cache.update(focusAdvance(running, 1010, {120, 30})));
    CHECK(std::strcmp(cache.timeText(), "119:59") == 0);
    CHECK(cache.phaseText() == phase_buffer && cache.timeText() == time_buffer);
    const uint32_t remaining[] = {60001, 60000, 59999, 1001, 1000, 999, 1, 0};
    const char *expected[] = {"01:01", "01:00", "01:00", "00:02", "00:01", "00:01", "00:01", "00:00"};
    for (int i = 0; i < 8; ++i) {
        cache.update({FocusPhase::Focus, FocusMode::Running, remaining[i], 0, 300000});
        CHECK(std::strcmp(cache.timeText(), expected[i]) == 0);
    }
    for (FocusPhase phase : {FocusPhase::Focus, FocusPhase::Break}) {
        FocusState paused{phase, FocusMode::Paused, 60001, 50, 300000};
        CHECK(cache.update(paused));
        CHECK(std::strcmp(cache.phaseText(), phase == FocusPhase::Focus ? "FOKUS:" : "PAUS:") == 0);
        CHECK(std::strcmp(cache.timeText(), "01:01") == 0);
        CHECK(!cache.update(focusAdvance(paused, 100000, {5, 1})));
        CHECK(cache.update(focusToggle(paused, 100000, {5, 1})));
        CHECK(std::strstr(cache.phaseText(), "||") == nullptr);
    }
    cache.update({FocusPhase::Focus, FocusMode::Paused, 7200000, 0, 7200000});
    CHECK(std::strcmp(cache.phaseText(), "FOKUS:") == 0 && std::strcmp(cache.timeText(), "120:00") == 0);
    cache.update({FocusPhase::Break, FocusMode::Paused, 1800000, 0, 1800000});
    CHECK(std::strcmp(cache.phaseText(), "PAUS:") == 0 && std::strcmp(cache.timeText(), "30:00") == 0);
    FocusState end_focus{FocusPhase::Focus, FocusMode::Running, 1, 100, 300000};
    cache.update(end_focus);
    FocusState start_break = focusAdvance(end_focus, 101, {5, 1});
    CHECK(cache.update(start_break));
    CHECK(std::strcmp(cache.phaseName(), "PAUS") == 0 && std::strcmp(cache.timeText(), "01:00") == 0);
    FocusState completed = focusAdvance(start_break, 60101, {5, 1});
    CHECK(cache.update(completed) && !cache.visible() && cache.timeText()[0] == '\0' && cache.phaseText()[0] == '\0');
    CHECK(!cache.update(completed));
    CHECK(cache.update(focusToggle(completed, 60102, {5, 1})));
    CHECK(std::strcmp(cache.timeText(), "05:00") == 0);
    CHECK(cache.update(focusReset(60103, {5, 1})) && !cache.visible());
    FocusState wrap{FocusPhase::Focus, FocusMode::Running, 2000, 0xfffffff0u, 300000};
    cache.update(wrap);
    CHECK(cache.update(focusAdvance(wrap, 0x3d8, {5, 1})) && std::strcmp(cache.timeText(), "00:01") == 0);

    bongo_focus_phase_label = createFocusCountdownLabel(nullptr, &font16, 96, 17, LV_TEXT_ALIGN_RIGHT, 0, focus_countdown.phaseText());
    bongo_focus_time_label = createFocusCountdownLabel(nullptr, &font16, 96, 17, LV_TEXT_ALIGN_RIGHT, 0, focus_countdown.timeText());
    media_focus_phase_label = createFocusCountdownLabel(nullptr, &font14, 52, 16, LV_TEXT_ALIGN_CENTER, 0, focus_countdown.phaseName());
    media_focus_time_label = createFocusCountdownLabel(nullptr, &font16, 56, 18, LV_TEXT_ALIGN_CENTER, 0, focus_countdown.timeText());
    for (lv_obj_t &bar : recorded_bars) bar.flags = LV_OBJ_FLAG_HIDDEN;
    card.flags = LV_OBJ_FLAG_HIDDEN;
    lv_obj_set_size(media_art_image, MEDIA_ART_SIZE, MEDIA_ART_SIZE);
    CHECK(labels_created == 4 && recorded_labels[1].width == 96 && recorded_labels[3].height == 18);
    refreshFocusCountdown();
    CHECK(recorded_labels[0].writes == 1 && recorded_labels[3].writes == 1);
    focus_state = focusToggle(focusInitial({5, 1}), 100, {5, 1});
    refreshFocusCountdown();
    CHECK(recorded_labels[0].writes == 2 && recorded_labels[3].writes == 2);
    CHECK(art_box.width == 144 && art_box.x == 48 && art_box.y == 54 && art_box.radius == 72);
    CHECK(art_image.zoom == 320 && cat_canvas.zoom == 560 && art_box.pos_changes == 1);
    CHECK(art_image.x == 16 && art_image.y == 16 && art_image.pos_changes == 1);
    CHECK(art_viewport.x + art_image.x == 64 && art_viewport.y + art_image.y == 70);
    CHECK(art_viewport.width == 144 && art_viewport.height == 144);
    CHECK(lv_obj_has_flag(media_arm_layer, LV_OBJ_FLAG_HIDDEN) &&
          lv_obj_has_flag(media_paw_layer, LV_OBJ_FLAG_HIDDEN));
    CHECK(recorded_labels[1].text == recorded_labels[3].text && recorded_labels[1].text == focus_countdown.timeText());
    for (int i = 0; i < 999; ++i) {
        focus_state = focusAdvance(focus_state, 101 + i, {5, 1});
        refreshFocusCountdown();
    }
    CHECK(recorded_labels[0].writes == 2 && recorded_labels[1].writes == 2);
    focus_state = focusAdvance(focus_state, 1100, {5, 1});
    refreshFocusCountdown();
    CHECK(recorded_labels[0].writes == 2 && recorded_labels[2].writes == 2);
    CHECK(recorded_labels[1].writes == 3 && recorded_labels[3].writes == 3);
    CHECK(art_box.pos_changes == 1 && art_image.zoom_changes == 1 && cat_canvas.zoom_changes == 1);
    focus_state = focusToggle(focus_state, 1100, {5, 1});
    refreshFocusCountdown();
    CHECK(recorded_labels[0].writes == 2 && recorded_labels[2].writes == 2);
    for (lv_obj_t &bar : recorded_bars) CHECK(bar.flags == 0);
    for (int i = 0; i < 10000; ++i) refreshFocusCountdown();
    CHECK(recorded_labels[0].writes == 2 && recorded_labels[1].writes == 3 && labels_created == 4);
    CHECK(art_box.pos_changes == 1 && art_image.zoom_changes == 1 && cat_canvas.zoom_changes == 1);
    activateMediaArtwork(1, true);
    CHECK(art_image.zoom == 320 && art_box.width == 144 && media_art_active_buffer == 1 && media_art_valid);
    CHECK(media_art_descriptor.header.w == 112 && media_art_descriptor.header.h == 112 && Serial.writes == 1);
    CHECK(media_art_descriptor.header.cf == LV_IMG_CF_TRUE_COLOR_CHROMA_KEYED &&
          media_art_descriptor.data_size == MEDIA_ART_LV_BYTES && media_art_descriptor.data == mock_art[1]);
    CHECK(image_invalidations == 1 && invalidated_image == &media_art_descriptor && media_record_dirty);
    CHECK(media_ui_refreshes == 1 && std::strcmp(Serial.last_line, "MEDIA_ART_OK") == 0);
    toggleMediaCatMode();
    CHECK(media_cat_mode && cat_canvas.zoom == 560 && art_box.width == 144 && art_box.pos_changes == 1);
    toggleMediaCatMode();
    CHECK(!media_cat_mode && art_image.zoom == 320 && cat_canvas.zoom == 560);
    focus_banner_visible = focus_banner_compact = true;
    focus_banner_kind = FocusCueKind::FocusDone;
    focus_banner_panel = PanelId::Player;
    refreshFocusCountdownPresentation();
    CHECK(media_focus_compact_cue && !bongo_focus_compact_cue && card.bg == focusDarkAccentHex());
    CHECK(card.border == focusAccentHex() && media_focus_phase_label->flags == 0);
    for (int i = 0; i < 10000; ++i) refreshFocusCountdownPresentation();
    CHECK(media_focus_time_label->pos_changes == 0 && recorded_bars[0].pos_changes == 0 && art_box.pos_changes == 1);
    focus_banner_panel = PanelId::Bongo;
    refreshFocusCountdownPresentation();
    CHECK(bongo_focus_compact_cue && !media_focus_compact_cue && bongo_focus_phase_label->text_color == focusAccentHex());
    CHECK(card.bg == 0x15191E && card.border == 0x292E35);
    focus_banner_panel = PanelId::Settings;
    refreshFocusCountdownPresentation();
    CHECK(!bongo_focus_compact_cue && bongo_focus_phase_label->text_color == 0);
    focus_banner_visible = false;
    refreshFocusCountdownPresentation();
    CHECK(!media_focus_compact_cue && media_focus_phase_label->flags == 0);
    focus_state = focusReset(100000, {5, 1});
    refreshFocusCountdown();
    for (lv_obj_t &label : recorded_labels) CHECK(label.flags == LV_OBJ_FLAG_HIDDEN);
    for (lv_obj_t &bar : recorded_bars) CHECK(bar.flags == LV_OBJ_FLAG_HIDDEN);
    CHECK(card.flags == LV_OBJ_FLAG_HIDDEN);
    CHECK(recorded_labels[0].writes == 2 && recorded_labels[3].writes == 3);
    CHECK(art_box.width == 172 && art_box.x == 34 && art_box.y == 26 && art_box.radius == 86);
    CHECK(art_image.zoom == 384 && cat_canvas.zoom == 672 && art_box.pos_changes == 2);
    CHECK(art_image.x == 30 && art_image.y == 30 && art_image.pos_changes == 2);
    CHECK(art_viewport.x + art_image.x == 64 && art_viewport.y + art_image.y == 56);
    CHECK(art_viewport.width == 172 && art_viewport.height == 172);
    activateMediaArtwork(0, false);
    CHECK(media_art_active_buffer == 0 && media_art_descriptor.data == mock_art[0] && image_invalidations == 2);
    toggleMediaCatMode();
    CHECK(art_image.zoom == 384 && cat_canvas.zoom == 672 && art_box.pos_changes == 2 && Serial.writes == 1);
    focus_state = {FocusPhase::Break, FocusMode::Running, 1000, 0, 60000};
    refreshFocusCountdown();
    CHECK(art_box.width == 144 && cat_canvas.zoom == 560);
    focus_state = {FocusPhase::Break, FocusMode::Completed, 0, 1000, 60000};
    refreshFocusCountdown();
    CHECK(card.flags == LV_OBJ_FLAG_HIDDEN && art_box.width == 172 && cat_canvas.zoom == 672);
    std::printf("PASS: %d countdown/state/UI adapter checks\n", checks);
    return 0;
}
