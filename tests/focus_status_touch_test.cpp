#include "../src/focus_status_touch.h"
#include <algorithm>
#include <cstdio>
#include <cstdarg>
#include <cstring>
#include <initializer_list>
using std::min;

constexpr uint16_t rawX(int y) { return uint16_t(200 + (y * 3700 + 319) / 320); }
constexpr uint16_t rawY(int x) { return uint16_t(200 + ((239 - x) * 3700 + 238) / 239); }
constexpr bool hit(PanelId panel, int x, int y, FocusMode mode = FocusMode::Running) {
    return focusStatusHit(panel, mode, false, rawX(y), rawY(x));
}
static_assert(hit(PanelId::Bongo, 5, 62) && hit(PanelId::Bongo, 234, 81) &&
              !hit(PanelId::Bongo, 235, 81) && !hit(PanelId::Bongo, 5, 82) &&
              !hit(PanelId::Bongo, 4, 62) && !hit(PanelId::Bongo, 5, 61), "Bongo half-open bounds");
static_assert(hit(PanelId::Player, 36, 16) && hit(PanelId::Player, 203, 52) &&
              !hit(PanelId::Player, 204, 52) && !hit(PanelId::Player, 36, 53) &&
              !hit(PanelId::Player, 35, 16) && !hit(PanelId::Player, 36, 15), "Player half-open bounds");
static_assert(hit(PanelId::Bongo, 120, 70, FocusMode::Paused) &&
              !hit(PanelId::Bongo, 120, 70, FocusMode::Idle) &&
              !hit(PanelId::Bongo, 120, 70, FocusMode::Prepared) &&
              !hit(PanelId::Bongo, 120, 70, FocusMode::Completed) &&
              !hit(PanelId::Focus, 120, 70) && !hit(PanelId::Settings, 120, 70) &&
              !focusStatusHit(PanelId::Player, FocusMode::Running, true, rawX(34), rawY(120)),
              "Only visible local timer in Bongo/Player outside menu can hit");
static_assert(!focusStatusDragCancelled(false, PanelId::Player, rawX(34), rawY(120), rawX(34), rawY(120), 180) &&
              focusStatusDragCancelled(false, PanelId::Player, rawX(34), rawY(120), rawX(50), rawY(120), 180) &&
              focusStatusDragCancelled(true, PanelId::Player, rawX(34), rawY(120), rawX(34), rawY(120), 180),
              "Movement cancels once, including return to start");


// Actual firmware handler/dispatch/timer functions are extracted by Python.
// TFT input and UI/serial side effects are recorded here, not reimplemented.
constexpr int LV_OBJ_FLAG_HIDDEN = 4, ANIM_STATE_IDLE_STAGE1 = 1;
struct lv_obj_t { int flags = LV_OBJ_FLAG_HIDDEN; } menu, backdrop;
bool lv_obj_has_flag(lv_obj_t *o, int flag) { return (o->flags & flag) != 0; }
void lv_obj_add_flag(lv_obj_t *o, int flag) { o->flags |= flag; }
void lv_obj_clear_flag(lv_obj_t *o, int flag) { o->flags &= ~flag; }
void lv_obj_move_foreground(lv_obj_t *) {}
lv_obj_t *feature_overlay = &menu, *feature_overlay_backdrop = &backdrop;
bool touch_is_down = false, touch_long_press_fired = false, touch_started_in_menu = false;
bool touch_started_in_focus_status = false, touch_focus_status_cancelled = false;
bool media_has_track = true;
bool touch_button_cancelled = false, touch_start_times_open = false, focus_settings_open = false;
bool touch_bonk_active = false;
uint32_t touch_down_time = 0, overlay_hide_time = 0, touch_bonk_until = 0;
uint16_t touch_start_x = 0, touch_start_y = 0, touch_last_x = 0, touch_last_y = 0;
lv_obj_t *touch_feedback_button = nullptr;
PanelId active_panel = PanelId::Bongo, touch_start_panel = PanelId::Bongo;
uint8_t media_tap_count = 0;
uint32_t media_tap_deadline = 0;
FocusState focus_state = focusInitial();
FocusDurations focus_durations{5, 1};
FocusCueState focus_cue = focusCueInitial();
FocusUiSettings focus_ui_settings = focusDefaultUiSettings();
uint32_t test_now = 1000;
int bonks = 0, dj_switches = 0, menu_selections = 0, event_order = 0, last_state_event = 0;
struct {
    char commands[32][64] = {};
    int count = 0, last_event = 0;
    void println(const char *command) { std::snprintf(commands[count++], 64, "%s", command); last_event = ++event_order; }
    void printf(const char *format, ...) {
        va_list args; va_start(args, format);
        std::vsnprintf(commands[count++], 64, format, args); va_end(args); last_event = ++event_order;
    }
} Serial;
struct {
    bool pressed = false;
    uint16_t x = 0, y = 0;
    int getTouchRawZ() { return pressed ? 1000 : 0; }
    void getTouchRaw(uint16_t *xx, uint16_t *yy) { *xx = x; *yy = y; }
} tft;
struct { bool is_streak_mode = false; } sprite_manager;
void sprite_manager_set_state(decltype(sprite_manager) *, int, uint32_t) {}
void updateTimeDisplay() {}
void refreshFeatureOverlay() {}
void refreshFocusCountdown() { last_state_event = ++event_order; }
void refreshFocusUi() {}
void updateFocusCue(uint32_t) {}
void showFocusScreen(bool) { active_panel = PanelId::Focus; media_tap_count = 0; media_tap_deadline = 0; }
void setTouchFeedback(lv_obj_t *o) { touch_feedback_button = o; }
lv_obj_t *pressedButtonAt(uint16_t, uint16_t) { return nullptr; }
TouchRect touchButtonRect(lv_obj_t *) { return {0, 0, 0, 0}; }
void selectFeaturePanel() { ++menu_selections; }
void handleFocusTap(uint32_t) {}
void handleLocalSettingsTap(uint32_t) {}
void triggerTouchBonk(uint32_t) { ++bonks; }
void toggleMediaCatMode() { ++dj_switches; }
#include "focus_status_touch_test_fixture.inc"

int checks = 0;
#define CHECK(condition) do { ++checks; if (!(condition)) { \
    std::printf("FAILED line %d: %s\n", __LINE__, #condition); return 1; } } while (0)
void reset(PanelId panel, FocusPhase phase = FocusPhase::Focus, FocusMode mode = FocusMode::Running) {
    active_panel = panel;
    touch_is_down = touch_long_press_fired = touch_started_in_menu = false;
    touch_started_in_focus_status = touch_focus_status_cancelled = touch_button_cancelled = false;
    touch_feedback_button = nullptr;
    touch_bonk_active = false;
    media_tap_count = 0; media_tap_deadline = 0; overlay_hide_time = 0;
    menu.flags = backdrop.flags = LV_OBJ_FLAG_HIDDEN;
    Serial.count = 0; bonks = dj_switches = menu_selections = 0;
    focus_state = {phase, mode, 300000, test_now, 300000};
    focus_cue = focusCueInitial(); focus_ui_settings = focusDefaultUiSettings();
}
void tick(bool down, int x, int y, uint32_t elapsed = 20) {
    test_now += elapsed; tft.pressed = down; tft.x = rawX(y); tft.y = rawY(x);
    handleTouchFeature(test_now);
    serviceFocusTimer(test_now);
    serviceMediaTaps(test_now);
}
void tap(int x, int y) { tick(true, x, y); tick(true, x, y, 60); tick(false, x, y); }
void finishMedia() { tick(false, 120, 180, 340); }

int main() {
    for (PanelId panel : {PanelId::Bongo, PanelId::Player}) {
        const int y = panel == PanelId::Bongo ? 70 : 34;
        for (FocusPhase phase : {FocusPhase::Focus, FocusPhase::Break}) {
            reset(panel, phase);
            tap(120, y);
            CHECK(focus_state.mode == FocusMode::Paused && focus_state.phase == phase && active_panel == panel);
            CHECK(Serial.count == 0 && bonks == 0 && media_tap_count == 0);
            const uint32_t remaining = focus_state.remaining_ms;
            tick(false, 120, y, 1000);
            CHECK(focus_state.remaining_ms == remaining);
            tap(120, y);
            CHECK(focus_state.mode == FocusMode::Running && active_panel == panel && Serial.count == 0 && bonks == 0);
        }
        for (FocusMode mode : {FocusMode::Idle, FocusMode::Prepared, FocusMode::Completed}) {
            reset(panel, FocusPhase::Focus, mode); tap(120, y); finishMedia();
            CHECK(focus_state.mode == mode);
            CHECK(panel == PanelId::Bongo ? bonks == 1 && Serial.count == 0 : bonks == 0 && Serial.count == 1);
        }
    }
    for (int group = 1; group <= 3; ++group) {
        reset(PanelId::Player);
        for (int i = 0; i < group; ++i) tap(120, 180);
        CHECK(media_tap_count == group && Serial.count == 0);
        tap(120, 34);
        CHECK(Serial.count == 1 && media_tap_count == 0 && focus_state.mode == FocusMode::Paused);
        CHECK(std::strcmp(Serial.commands[0], group == 1 ? "MEDIA_CMD:PLAY_PAUSE" : group == 2 ? "MEDIA_CMD:NEXT" : "MEDIA_CMD:PREVIOUS") == 0);
        CHECK(Serial.last_event < last_state_event);
        tap(120, 180); finishMedia();
        CHECK(Serial.count == 2 && std::strcmp(Serial.commands[1], "MEDIA_CMD:PLAY_PAUSE") == 0);
        reset(PanelId::Player);
        for (int i = 0; i < group; ++i) tap(120, 180);
        finishMedia(); CHECK(Serial.count == 1);
        CHECK(std::strcmp(Serial.commands[0], group == 1 ? "MEDIA_CMD:PLAY_PAUSE" : group == 2 ? "MEDIA_CMD:NEXT" : "MEDIA_CMD:PREVIOUS") == 0);
    }
    reset(PanelId::Bongo); tap(120, 180);
    CHECK(bonks == 1 && Serial.count == 0 && focus_state.mode == FocusMode::Running);
    reset(PanelId::Player); tick(true, 120, 34); tick(true, 136, 34, 60); tick(false, 136, 34);
    CHECK(Serial.count == 0 && media_tap_count == 0 && focus_state.mode == FocusMode::Running);
    reset(PanelId::Player); tick(true, 120, 34); tick(true, 120, 10); tick(true, 120, 34); tick(false, 120, 34);
    CHECK(Serial.count == 0 && media_tap_count == 0 && focus_state.mode == FocusMode::Running);
    for (int x : {80, 160}) {
        reset(PanelId::Player); tap(120, 180);
        tick(true, 120, 34); tick(true, x, 34, 60); tick(false, x, 34);
        CHECK(Serial.count == 1 && media_tap_count == 0 && focus_state.mode == FocusMode::Running);
        CHECK(std::strcmp(Serial.commands[0], x == 80 ? "MEDIA_CMD:NEXT" : "MEDIA_CMD:PREVIOUS") == 0);
    }
    reset(PanelId::Player); tick(true, 120, 34); tick(true, 120, 74, 60); tick(false, 120, 74);
    CHECK(dj_switches == 1 && Serial.count == 0 && focus_state.mode == FocusMode::Running);
    for (PanelId panel : {PanelId::Bongo, PanelId::Player}) {
        reset(panel); if (panel == PanelId::Player) tap(120, 180);
        const int y = panel == PanelId::Bongo ? 70 : 34;
        tick(true, 120, y); tick(true, 120, y, 650); tick(false, 120, y);
        CHECK(!lv_obj_has_flag(feature_overlay, LV_OBJ_FLAG_HIDDEN) && focus_state.mode == FocusMode::Running);
        CHECK(Serial.count == 0 && bonks == 0 && media_tap_count == 0);
    }
    reset(PanelId::Player); menu.flags = 0; tap(120, 34);
    CHECK(menu_selections == 1 && focus_state.mode == FocusMode::Running && Serial.count == 0);
    reset(PanelId::Player); tick(true, 120, 34); active_panel = PanelId::Focus; tick(false, 120, 34, 80);
    CHECK(focus_state.mode == FocusMode::Running && Serial.count == 0);
    reset(PanelId::Player, FocusPhase::Break); focus_state.remaining_ms = 50; tap(120, 34);
    CHECK(focus_state.mode == FocusMode::Completed && Serial.count == 0 && media_tap_count == 0);
    reset(PanelId::Player); focus_state.remaining_ms = 50; focus_ui_settings.auto_show_focus = true; tap(120, 34);
    CHECK(active_panel == PanelId::Focus && focus_state.phase == FocusPhase::Break && focus_state.mode == FocusMode::Running && Serial.count == 0);
    reset(PanelId::Player); focus_state.remaining_ms = 50; tap(120, 34);
    CHECK(active_panel == PanelId::Player && focus_state.phase == FocusPhase::Break && focus_state.mode == FocusMode::Paused && Serial.count == 0);
    test_now = 0xfffffff0u; reset(PanelId::Player); tap(120, 34);
    CHECK(focus_state.mode == FocusMode::Paused && Serial.count == 0 && active_panel == PanelId::Player);
    // The complete lower time region uses ordinary media gestures again.
    for (int y : {261, 278, 293}) {
        reset(PanelId::Player); tap(120, y); finishMedia();
        CHECK(Serial.count == 1 && std::strcmp(Serial.commands[0], "MEDIA_CMD:PLAY_PAUSE") == 0);
        reset(PanelId::Player); tick(true, 120, y); tick(true, 180, y, 60); tick(false, 180, y);
        CHECK(Serial.count == 1 && std::strcmp(Serial.commands[0], "MEDIA_CMD:PREVIOUS") == 0);
        reset(PanelId::Player); tick(true, 120, y); tick(true, 60, y, 60); tick(false, 60, y);
        CHECK(Serial.count == 1 && std::strcmp(Serial.commands[0], "MEDIA_CMD:NEXT") == 0);
    }
    std::printf("PASS: %d actual central-handler/dispatch/timer checks\n", checks);
    return 0;
}
