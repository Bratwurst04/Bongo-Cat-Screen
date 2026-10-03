#pragma once

#include <stdint.h>

enum class PanelId : uint8_t { Bongo, Player, Focus, Settings };
enum class FocusPhase : uint8_t { Focus, Break };
enum class FocusMode : uint8_t { Idle, Prepared, Running, Paused, Completed };
enum class TouchRoute : uint8_t { Menu, Bongo, Media, Focus, Settings };
enum class MenuChoice : uint8_t { None, Bongo, Player, Focus, Settings };
enum class FocusAction : uint8_t { None, Toggle, Reset, Settings };
enum class FocusSettingsAction : uint8_t {
    None, FocusMinus, FocusPlus, BreakMinus, BreakPlus, Save
};
enum class FocusCueKind : uint8_t { None, FocusDone, BreakDone };
enum class AccentTheme : uint8_t { Green, Cyan, Amber };
enum class LocalSettingsAction : uint8_t { None, Theme, AutoShow, Led, Back };

constexpr uint32_t FOCUS_CUE_LARGE_MS = 10000UL;
constexpr uint32_t BREAK_CUE_LARGE_MS = 6000UL;
constexpr uint32_t FOCUS_LED_PULSE_MS = 180UL;
constexpr uint32_t FOCUS_LED_PERIOD_MS = 400UL;
constexpr uint32_t FOCUS_LED_PULSE_COUNT = 3UL;
constexpr uint32_t TOUCH_LONG_PRESS_MS = 650UL;
constexpr uint32_t TOUCH_TAP_MIN_MS = 35UL;

struct FocusState {
    FocusPhase phase;
    FocusMode mode;
    uint32_t remaining_ms;
    uint32_t last_tick_ms;
    uint32_t phase_total_ms;
};

struct FocusDurations {
    uint16_t focus_minutes;
    uint16_t break_minutes;
};

struct FocusUiSettings {
    AccentTheme theme;
    bool auto_show_focus;
    bool led_at_phase_end;
};

constexpr FocusUiSettings focusDefaultUiSettings() {
    return {AccentTheme::Green, false, true};
}
constexpr bool focusUiSettingsValid(FocusUiSettings values) {
    return static_cast<uint8_t>(values.theme) <=
           static_cast<uint8_t>(AccentTheme::Amber);
}
constexpr uint32_t focusPackUiSettings(FocusUiSettings values) {
    return 0xB06F0000UL | (uint32_t(values.theme) << 8) |
           (values.auto_show_focus ? 2UL : 0UL) |
           (values.led_at_phase_end ? 1UL : 0UL);
}
constexpr FocusUiSettings focusUiSettingsFromPacked(uint32_t packed) {
    return (packed & 0xFFFFFCFCUL) == 0xB06F0000UL &&
           ((packed >> 8) & 3UL) <= 2UL ?
               FocusUiSettings{static_cast<AccentTheme>((packed >> 8) & 3UL),
                               bool(packed & 2UL), bool(packed & 1UL)} :
               focusDefaultUiSettings();
}
constexpr FocusUiSettings focusUiNextTheme(FocusUiSettings values) {
    return {static_cast<AccentTheme>((static_cast<uint8_t>(values.theme) + 1) % 3),
            values.auto_show_focus, values.led_at_phase_end};
}

constexpr FocusDurations focusDefaultDurations() { return {25, 5}; }
constexpr uint32_t focusMinutesMs(uint16_t minutes) {
    return uint32_t(minutes) * 60UL * 1000UL;
}
constexpr bool focusMinutesValid(uint16_t minutes) {
    return minutes >= 5 && minutes <= 120 && minutes % 5 == 0;
}
constexpr bool breakMinutesValid(uint16_t minutes) {
    return minutes >= 1 && minutes <= 30;
}
constexpr bool focusDurationsValid(FocusDurations values) {
    return focusMinutesValid(values.focus_minutes) &&
           breakMinutesValid(values.break_minutes);
}
constexpr uint32_t focusPackDurations(FocusDurations values) {
    return uint32_t(values.focus_minutes) |
           (uint32_t(values.break_minutes) << 16);
}
constexpr FocusDurations focusDurationsFromPacked(uint32_t packed) {
    return {uint16_t(focusMinutesValid(uint16_t(packed)) ?
                         uint16_t(packed) : 25),
            uint16_t(breakMinutesValid(uint16_t(packed >> 16)) ?
                         uint16_t(packed >> 16) : 5)};
}
constexpr FocusDurations focusAdjustDurations(FocusDurations values,
                                               bool adjust_focus, int direction) {
    return adjust_focus ?
        FocusDurations{uint16_t(direction < 0 ?
                           (values.focus_minutes > 5 ? values.focus_minutes - 5 : 5) :
                           (values.focus_minutes < 120 ? values.focus_minutes + 5 : 120)),
                       values.break_minutes} :
        FocusDurations{values.focus_minutes,
                       uint16_t(direction < 0 ?
                           (values.break_minutes > 1 ? values.break_minutes - 1 : 1) :
                           (values.break_minutes < 30 ? values.break_minutes + 1 : 30))};
}

constexpr bool focusJustCompleted(FocusState before, FocusState after) {
    return before.phase == FocusPhase::Focus &&
           after.phase == FocusPhase::Break;
}
constexpr bool focusBreakJustCompleted(FocusState before, FocusState after) {
    return before.phase == FocusPhase::Break &&
           before.mode != FocusMode::Completed &&
           after.phase == FocusPhase::Break &&
           after.mode == FocusMode::Completed;
}

constexpr bool focusUiShouldAutoShow(FocusUiSettings values, FocusState before,
                                     FocusState after) {
    return values.auto_show_focus &&
           (focusJustCompleted(before, after) ||
            focusBreakJustCompleted(before, after));
}

struct FocusCueState {
    FocusCueKind kind;
    uint32_t started_ms;
};

constexpr FocusCueState focusCueInitial() { return {FocusCueKind::None, 0}; }

constexpr FocusCueState focusCueForTransition(FocusCueState cue,
                                              FocusState before,
                                              FocusState after, uint32_t now) {
    return focusJustCompleted(before, after) ?
               FocusCueState{FocusCueKind::FocusDone, now} :
           focusBreakJustCompleted(before, after) ?
               FocusCueState{FocusCueKind::BreakDone, now} :
           after.phase == FocusPhase::Focus ? focusCueInitial() : cue;
}

constexpr FocusCueState focusCueAcknowledge(FocusCueState) {
    return focusCueInitial();
}

constexpr FocusCueState focusCueAfterPanelShow(FocusCueState cue, bool manual) {
    return manual ? focusCueAcknowledge(cue) : cue;
}

constexpr bool focusCueLarge(FocusCueState cue, uint32_t now) {
    return cue.kind != FocusCueKind::None &&
           uint32_t(now - cue.started_ms) <
               (cue.kind == FocusCueKind::FocusDone ?
                    FOCUS_CUE_LARGE_MS : BREAK_CUE_LARGE_MS);
}

constexpr bool focusCueLedOn(FocusCueState cue, uint32_t now) {
    return cue.kind != FocusCueKind::None &&
           uint32_t(now - cue.started_ms) <
               FOCUS_LED_PERIOD_MS * (cue.kind == FocusCueKind::FocusDone ?
                                          FOCUS_LED_PULSE_COUNT : 1UL) &&
           uint32_t(now - cue.started_ms) % FOCUS_LED_PERIOD_MS <
               FOCUS_LED_PULSE_MS;
}

constexpr bool focusCueVisible(FocusCueState cue, uint32_t now,
                               PanelId panel) {
    return cue.kind != FocusCueKind::None &&
           (focusCueLarge(cue, now) ||
            (cue.kind == FocusCueKind::FocusDone && panel != PanelId::Focus));
}

constexpr FocusState focusInitial(FocusDurations values = focusDefaultDurations()) {
    return {FocusPhase::Focus, FocusMode::Idle,
            focusMinutesMs(values.focus_minutes), 0,
            focusMinutesMs(values.focus_minutes)};
}

// Called frequently while running. Unsigned subtraction remains correct across
// millis() wrap, provided consecutive ticks are less than one wrap apart.
constexpr FocusState focusAdvance(FocusState state, uint32_t now,
                                   FocusDurations values) {
    return state.mode != FocusMode::Running ? state :
           uint32_t(now - state.last_tick_ms) >= state.remaining_ms ?
               (state.phase == FocusPhase::Focus ?
                   FocusState{FocusPhase::Break, FocusMode::Running,
                              focusMinutesMs(values.break_minutes), now,
                              focusMinutesMs(values.break_minutes)} :
                   FocusState{FocusPhase::Break, FocusMode::Completed, 0, now,
                              state.phase_total_ms}) :
               FocusState{state.phase, FocusMode::Running,
                          state.remaining_ms - uint32_t(now - state.last_tick_ms), now,
                          state.phase_total_ms};
}

constexpr FocusState focusPauseAdvanced(FocusState state) {
    return state.mode == FocusMode::Completed ? state :
           FocusState{state.phase, FocusMode::Paused,
                      state.remaining_ms, state.last_tick_ms, state.phase_total_ms};
}

// After the break, Start begins a new focus session. Reset prepares focus.
constexpr FocusState focusToggle(FocusState state, uint32_t now,
                                  FocusDurations values) {
    return state.mode == FocusMode::Running ?
               focusPauseAdvanced(focusAdvance(state, now, values)) :
           state.mode == FocusMode::Completed ?
               FocusState{FocusPhase::Focus, FocusMode::Running,
                          focusMinutesMs(values.focus_minutes), now,
                          focusMinutesMs(values.focus_minutes)} :
               FocusState{state.phase, FocusMode::Running,
                          state.remaining_ms, now, state.phase_total_ms};
}

constexpr FocusState focusReset(uint32_t now, FocusDurations values) {
    return {FocusPhase::Focus, FocusMode::Prepared,
            focusMinutesMs(values.focus_minutes), now,
            focusMinutesMs(values.focus_minutes)};
}

// Saving a new focus duration updates a cycle that has not started yet.
// A countdown paused after Start keeps the remainder it already earned.
constexpr FocusState focusAfterSettingsSave(FocusState state,
                                            FocusDurations values,
                                            uint32_t now) {
    return state.phase == FocusPhase::Focus &&
           (state.mode == FocusMode::Idle || state.mode == FocusMode::Prepared) ?
        FocusState{FocusPhase::Focus, state.mode,
                   focusMinutesMs(values.focus_minutes), now,
                   focusMinutesMs(values.focus_minutes)} : state;
}

constexpr uint16_t focusProgressPermille(FocusState state) {
    return state.phase_total_ms == 0 ? 0 :
           state.remaining_ms >= state.phase_total_ms ? 0 :
           uint16_t((uint64_t(state.phase_total_ms - state.remaining_ms) * 1000ULL) /
                    state.phase_total_ms);
}

constexpr uint32_t focusDisplaySeconds(FocusState state) {
    return (state.remaining_ms + 999UL) / 1000UL;
}

constexpr TouchRoute routeTouch(PanelId panel, bool started_in_menu) {
    return started_in_menu ? TouchRoute::Menu :
           panel == PanelId::Settings ? TouchRoute::Settings :
           panel == PanelId::Focus ? TouchRoute::Focus :
           panel == PanelId::Player ? TouchRoute::Media : TouchRoute::Bongo;
}

constexpr bool touchIsTap(uint32_t duration_ms, bool long_press_fired) {
    return !long_press_fired && duration_ms >= TOUCH_TAP_MIN_MS &&
           duration_ms < TOUCH_LONG_PRESS_MS;
}

constexpr bool touchPanelChangedCancelsTap(PanelId started, PanelId current,
                                           bool started_in_menu) {
    return !started_in_menu && started != current;
}

struct TouchRect {
    int x1, y1, x2, y2;
};

constexpr int focusBound(int value, int low, int high) {
    return value < low ? low : value > high ? high : value;
}

constexpr int focusAbs(int value) { return value < 0 ? -value : value; }

// Raw X is screen Y; raw Y is reversed screen X on this portrait controller.
constexpr bool rawPointInRect(TouchRect rect, uint16_t raw_x, uint16_t raw_y) {
    return 239 - (focusBound(raw_y, 200, 3900) - 200) * 239 / 3700 >= rect.x1 &&
           239 - (focusBound(raw_y, 200, 3900) - 200) * 239 / 3700 <= rect.x2 &&
           (focusBound(raw_x, 200, 3900) - 200) * 320 / 3700 >= rect.y1 &&
           (focusBound(raw_x, 200, 3900) - 200) * 320 / 3700 <= rect.y2;
}

constexpr bool rawTapInRect(TouchRect rect, uint16_t start_x, uint16_t start_y,
                            uint16_t end_x, uint16_t end_y, int max_move) {
    return focusAbs(int(end_x) - int(start_x)) <= max_move &&
           focusAbs(int(end_y) - int(start_y)) <= max_move &&
           rawPointInRect(rect, start_x, start_y) &&
           rawPointInRect(rect, end_x, end_y);
}

constexpr MenuChoice menuChoiceForTap(TouchRect bongo, TouchRect player,
                                       TouchRect focus, TouchRect settings,
                                       uint16_t start_x,
                                       uint16_t start_y, uint16_t end_x,
                                       uint16_t end_y, int max_move) {
    return rawTapInRect(bongo, start_x, start_y, end_x, end_y, max_move) ?
               MenuChoice::Bongo :
           rawTapInRect(player, start_x, start_y, end_x, end_y, max_move) ?
               MenuChoice::Player :
           rawTapInRect(focus, start_x, start_y, end_x, end_y, max_move) ?
               MenuChoice::Focus :
           rawTapInRect(settings, start_x, start_y, end_x, end_y, max_move) ?
               MenuChoice::Settings : MenuChoice::None;
}

constexpr LocalSettingsAction localSettingsActionForTap(
    TouchRect theme, TouchRect auto_show, TouchRect led, TouchRect back,
    uint16_t start_x, uint16_t start_y, uint16_t end_x, uint16_t end_y,
    int max_move) {
    return rawTapInRect(theme, start_x, start_y, end_x, end_y, max_move) ?
               LocalSettingsAction::Theme :
           rawTapInRect(auto_show, start_x, start_y, end_x, end_y, max_move) ?
               LocalSettingsAction::AutoShow :
           rawTapInRect(led, start_x, start_y, end_x, end_y, max_move) ?
               LocalSettingsAction::Led :
           rawTapInRect(back, start_x, start_y, end_x, end_y, max_move) ?
               LocalSettingsAction::Back : LocalSettingsAction::None;
}

constexpr FocusAction focusActionForTap(TouchRect start_button,
                                         TouchRect reset_button,
                                         TouchRect settings_button,
                                         uint16_t start_x, uint16_t start_y,
                                         uint16_t end_x, uint16_t end_y,
                                         int max_move) {
    return rawTapInRect(start_button, start_x, start_y, end_x, end_y, max_move) ?
               FocusAction::Toggle :
           rawTapInRect(reset_button, start_x, start_y, end_x, end_y, max_move) ?
               FocusAction::Reset :
           rawTapInRect(settings_button, start_x, start_y, end_x, end_y, max_move) ?
               FocusAction::Settings : FocusAction::None;
}

constexpr FocusSettingsAction focusSettingsActionForTap(
    TouchRect focus_minus, TouchRect focus_plus,
    TouchRect break_minus, TouchRect break_plus, TouchRect save,
    uint16_t start_x, uint16_t start_y, uint16_t end_x, uint16_t end_y,
    int max_move) {
    return rawTapInRect(focus_minus, start_x, start_y, end_x, end_y, max_move) ?
               FocusSettingsAction::FocusMinus :
           rawTapInRect(focus_plus, start_x, start_y, end_x, end_y, max_move) ?
               FocusSettingsAction::FocusPlus :
           rawTapInRect(break_minus, start_x, start_y, end_x, end_y, max_move) ?
               FocusSettingsAction::BreakMinus :
           rawTapInRect(break_plus, start_x, start_y, end_x, end_y, max_move) ?
               FocusSettingsAction::BreakPlus :
           rawTapInRect(save, start_x, start_y, end_x, end_y, max_move) ?
               FocusSettingsAction::Save : FocusSettingsAction::None;
}
