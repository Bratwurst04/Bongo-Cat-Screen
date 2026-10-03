#include "../src/focus_logic.h"

constexpr FocusDurations defaults = focusDefaultDurations();
constexpr FocusDurations chosen{30, 7};
static_assert(defaults.focus_minutes == 25 && defaults.break_minutes == 5,
              "factory settings");
static_assert(focusMinutesValid(5) && focusMinutesValid(120) &&
              !focusMinutesValid(4) && !focusMinutesValid(6) &&
              !focusMinutesValid(125) && breakMinutesValid(1) &&
              breakMinutesValid(30) && !breakMinutesValid(0) &&
              !breakMinutesValid(31), "duration limits and steps");
static_assert(focusDurationsValid(chosen) &&
              focusDurationsFromPacked(focusPackDurations(chosen)).focus_minutes == 30 &&
              focusDurationsFromPacked(focusPackDurations(chosen)).break_minutes == 7 &&
              focusDurationsFromPacked(0xffffffffUL).focus_minutes == 25 &&
              focusDurationsFromPacked(0xffffffffUL).break_minutes == 5 &&
              focusDurationsFromPacked(focusPackDurations({35, 0})).focus_minutes == 35 &&
              focusDurationsFromPacked(focusPackDurations({35, 0})).break_minutes == 5,
              "packed NVS settings and corrupt-field fallback");
static_assert(focusAdjustDurations({5, 1}, true, -1).focus_minutes == 5 &&
              focusAdjustDurations({120, 30}, true, 1).focus_minutes == 120 &&
              focusAdjustDurations({5, 1}, false, -1).break_minutes == 1 &&
              focusAdjustDurations({120, 30}, false, 1).break_minutes == 30 &&
              focusAdjustDurations(defaults, true, 1).focus_minutes == 30 &&
              focusAdjustDurations(defaults, false, 1).break_minutes == 6,
              "plus/minus clamping");

constexpr FocusState initial = focusInitial(chosen);
constexpr FocusState running = focusToggle(initial, 100, chosen);
static_assert(initial.phase == FocusPhase::Focus &&
              initial.mode == FocusMode::Idle && focusDisplaySeconds(initial) == 1800 &&
              running.mode == FocusMode::Running &&
              initial.phase_total_ms == focusMinutesMs(30) &&
              focusProgressPermille(initial) == 0, "saved setting on boot and Start");
constexpr FocusState last_focus_ms = focusAdvance(
    running, 100 + focusMinutesMs(30) - 1, chosen);
constexpr FocusState break_running = focusAdvance(
    running, 100 + focusMinutesMs(30), chosen);
static_assert(last_focus_ms.phase == FocusPhase::Focus &&
              last_focus_ms.remaining_ms == 1 &&
              break_running.phase == FocusPhase::Break &&
              break_running.mode == FocusMode::Running &&
              break_running.remaining_ms == focusMinutesMs(7) &&
              break_running.phase_total_ms == focusMinutesMs(7) &&
              focusProgressPermille(break_running) == 0 &&
              focusJustCompleted(running, break_running),
              "focus reaches boundary exactly once and starts break");
static_assert(!focusJustCompleted(break_running,
              focusAdvance(break_running, break_running.last_tick_ms + 1, chosen)),
              "break ticks never retrigger focus completion");
constexpr FocusState last_break_ms = focusAdvance(
    break_running, break_running.last_tick_ms + focusMinutesMs(7) - 1, chosen);
constexpr FocusState break_done = focusAdvance(
    break_running, break_running.last_tick_ms + focusMinutesMs(7), chosen);
static_assert(last_break_ms.remaining_ms == 1 &&
              break_done.phase == FocusPhase::Break &&
              break_done.mode == FocusMode::Completed && break_done.remaining_ms == 0 &&
              focusProgressPermille(break_done) == 1000 &&
              focusBreakJustCompleted(break_running, break_done) &&
              !focusBreakJustCompleted(break_done,
                  focusAdvance(break_done, 3000000, chosen)) &&
              focusAdvance(break_done, 3000000, chosen).mode == FocusMode::Completed,
              "break ends once and waits for Start");
static_assert(focusToggle(break_done, 3000000, chosen).phase == FocusPhase::Focus &&
              focusToggle(break_done, 3000000, chosen).mode == FocusMode::Running &&
              focusToggle(break_done, 3000000, chosen).remaining_ms == focusMinutesMs(30),
              "Start after break begins next focus");

constexpr FocusState focus_halfway = focusAdvance(running, 100 + focusMinutesMs(10), chosen);
constexpr FocusState focus_paused = focusToggle(
    focus_halfway, 100 + focusMinutesMs(10), chosen);
constexpr FocusState focus_resumed = focusToggle(focus_paused, 2000000, chosen);
static_assert(focus_paused.phase == FocusPhase::Focus &&
              focus_paused.mode == FocusMode::Paused &&
              focus_paused.remaining_ms == focusMinutesMs(20) &&
              focusProgressPermille(focus_halfway) == 333 &&
              focusProgressPermille(focus_paused) == 333 &&
              focusProgressPermille(focus_resumed) == 333 &&
              focusAdvance(focus_paused, 9000000, chosen).remaining_ms == focusMinutesMs(20) &&
              focusAdvance(focus_resumed, 2001000, chosen).remaining_ms ==
                  focusMinutesMs(20) - 1000, "focus pause and resume");
constexpr FocusState break_part = focusAdvance(
    break_running, break_running.last_tick_ms + 60000, chosen);
constexpr FocusState break_paused = focusToggle(
    break_part, break_running.last_tick_ms + 60000, chosen);
constexpr FocusState break_resumed = focusToggle(break_paused, 3000000, chosen);
static_assert(break_paused.phase == FocusPhase::Break &&
              break_paused.mode == FocusMode::Paused &&
              break_paused.remaining_ms == focusMinutesMs(6) &&
              focusAdvance(break_paused, 9000000, chosen).remaining_ms == focusMinutesMs(6) &&
              focusAdvance(break_resumed, 3001000, chosen).remaining_ms ==
                  focusMinutesMs(6) - 1000, "break pause and resume");
static_assert(focusReset(3000, chosen).phase == FocusPhase::Focus &&
              focusReset(3000, chosen).mode == FocusMode::Prepared &&
              focusReset(3000, chosen).remaining_ms == focusMinutesMs(30),
              "NOLLA prepares chosen focus time from either phase");

constexpr FocusDurations changed_focus{40, 9};
constexpr FocusState prepared = focusReset(3000, chosen);
constexpr FocusState prepared_after_save = focusAfterSettingsSave(
    prepared, changed_focus, 4000);
constexpr FocusState paused_after_save = focusAfterSettingsSave(
    focus_paused, changed_focus, 4000);
static_assert(prepared_after_save.mode == FocusMode::Prepared &&
              prepared_after_save.remaining_ms == focusMinutesMs(40) &&
              focusToggle(prepared_after_save, 5000, changed_focus).remaining_ms ==
                  focusMinutesMs(40) &&
              focusAfterSettingsSave(initial, changed_focus, 4000).remaining_ms ==
                  focusMinutesMs(40) &&
              paused_after_save.mode == FocusMode::Paused &&
              paused_after_save.remaining_ms == focusMinutesMs(20) &&
              paused_after_save.phase_total_ms == focusMinutesMs(30) &&
              focusProgressPermille(paused_after_save) == 333 &&
              prepared_after_save.phase_total_ms == focusMinutesMs(40) &&
              focusToggle(paused_after_save, 5000, changed_focus).remaining_ms ==
                  focusMinutesMs(20),
              "saved focus time updates NOLLA/idle but not a started paused timer");

constexpr FocusDurations edited{35, 9};
static_assert(focusAdvance(running, 60100, edited).remaining_ms ==
                  focusMinutesMs(29) &&
              focusAdvance(running, 100 + focusMinutesMs(30), edited).remaining_ms ==
                  focusMinutesMs(9) &&
              focusAdvance(break_running, break_running.last_tick_ms + 1000,
                           edited).remaining_ms == focusMinutesMs(7) - 1000 &&
              focusToggle(break_done, 3000000, edited).remaining_ms ==
                  focusMinutesMs(35),
              "edits leave active phase intact and apply at next phase start");
constexpr FocusState focus_before_wrap{FocusPhase::Focus, FocusMode::Running,
                                       1000, 0xfffffff0UL, 1000};
constexpr FocusState break_before_wrap{FocusPhase::Break, FocusMode::Running,
                                       1000, 0xfffffff0UL, 1000};
static_assert(focusAdvance(focus_before_wrap, 0x20, chosen).remaining_ms == 952 &&
              focusAdvance(focus_before_wrap, 0x400, chosen).phase == FocusPhase::Break &&
              focusAdvance(break_before_wrap, 0x20, chosen).remaining_ms == 952 &&
              focusAdvance(break_before_wrap, 0x400, chosen).mode == FocusMode::Completed,
              "both timers survive millis wrap");

constexpr FocusUiSettings ui_defaults = focusDefaultUiSettings();
constexpr FocusUiSettings ui_auto{AccentTheme::Cyan, true, false};
static_assert(ui_defaults.theme == AccentTheme::Green &&
              !ui_defaults.auto_show_focus && ui_defaults.led_at_phase_end &&
              focusUiSettingsFromPacked(focusPackUiSettings(ui_auto)).theme ==
                  AccentTheme::Cyan &&
              focusUiSettingsFromPacked(focusPackUiSettings(ui_auto)).auto_show_focus &&
              !focusUiSettingsFromPacked(focusPackUiSettings(ui_auto)).led_at_phase_end &&
              focusUiSettingsFromPacked(0xffffffffUL).theme == AccentTheme::Green &&
              focusUiSettingsFromPacked(0xB06F0301UL).theme == AccentTheme::Green &&
              focusUiNextTheme(focusUiNextTheme(focusUiNextTheme(ui_defaults))).theme ==
                  AccentTheme::Green,
              "validated independent NVS settings and theme cycle");
static_assert(!focusUiShouldAutoShow(ui_defaults, running, break_running) &&
              focusUiShouldAutoShow(ui_auto, running, break_running) &&
              focusUiShouldAutoShow(ui_auto, break_running, break_done) &&
              !focusUiShouldAutoShow(ui_auto, focus_halfway, focus_paused) &&
              focusProgressPermille(focusToggle(break_done, 3000000, chosen)) == 0,
              "auto show only at phase end; next focus waits for Start");

constexpr FocusCueState focus_cue = focusCueForTransition(
    focusCueInitial(), running, break_running, 1000);
static_assert(focus_cue.kind == FocusCueKind::FocusDone &&
              focusCueLarge(focus_cue, 1000) &&
              focusCueLedOn(focus_cue, 1000) &&
              !focusCueLedOn(focus_cue, 1180) &&
              focusCueLedOn(focus_cue, 1400) &&
              focusCueLedOn(focus_cue, 1800) &&
              !focusCueLedOn(focus_cue, 2180) &&
              focusCueLarge(focus_cue, 10999) && !focusCueLarge(focus_cue, 11000) &&
              focusCueVisible(focus_cue, 11000, PanelId::Player) &&
              !focusCueVisible(focus_cue, 11000, PanelId::Focus),
              "focus cue: ten seconds, three pulses and off-panel reminder");
static_assert(focusCueForTransition(focus_cue, break_running,
              focusAdvance(break_running, break_running.last_tick_ms + 1,
                           chosen), 1001).started_ms == 1000,
              "break ticks cannot restart focus cue");
constexpr FocusCueState break_cue = focusCueForTransition(
    focus_cue, break_running, break_done, 2000);
static_assert(break_cue.kind == FocusCueKind::BreakDone &&
              focusCueLedOn(break_cue, 2000) &&
              !focusCueLedOn(break_cue, 2180) &&
              !focusCueLedOn(break_cue, 2400) &&
              focusCueLarge(break_cue, 7999) && !focusCueLarge(break_cue, 8000) &&
              focusCueVisible(break_cue, 7999, PanelId::Bongo) &&
              !focusCueVisible(break_cue, 8000, PanelId::Bongo) &&
              !focusCueVisible(break_cue, 8000, PanelId::Player),
              "break cue gives one pulse and no lingering START badge");
static_assert(focusCueAcknowledge(focus_cue).kind == FocusCueKind::None &&
              focusCueAfterPanelShow(focus_cue, false).kind == FocusCueKind::FocusDone &&
              focusCueAfterPanelShow(focus_cue, true).kind == FocusCueKind::None &&
              !focusCueLedOn(focusCueAcknowledge(focus_cue), 1000) &&
              focusCueForTransition(break_cue, break_done,
                  focusToggle(break_done, 3000, chosen), 3000).kind ==
                      FocusCueKind::None &&
              focusCueForTransition(focus_cue, break_running,
                  focusReset(3000, chosen), 3000).kind == FocusCueKind::None,
              "opening Focus, Start and NOLLA stop old cues");
constexpr FocusCueState wrapped_cue = focusCueForTransition(
    focusCueInitial(), running, break_running, 0xfffffff0UL);
static_assert(focusCueLedOn(wrapped_cue, 0x20) &&
              !focusCueLarge(wrapped_cue, 0x3000), "cue survives millis wrap");

static_assert(routeTouch(PanelId::Focus, false) == TouchRoute::Focus &&
              routeTouch(PanelId::Settings, false) == TouchRoute::Settings &&
              routeTouch(PanelId::Player, false) == TouchRoute::Media &&
              routeTouch(PanelId::Bongo, false) == TouchRoute::Bongo &&
              routeTouch(PanelId::Focus, true) == TouchRoute::Menu &&
              touchPanelChangedCancelsTap(PanelId::Player, PanelId::Focus, false) &&
              touchPanelChangedCancelsTap(PanelId::Bongo, PanelId::Focus, false) &&
              !touchPanelChangedCancelsTap(PanelId::Player, PanelId::Player, false) &&
              !touchPanelChangedCancelsTap(PanelId::Player, PanelId::Focus, true) &&
              !touchIsTap(34, false) && touchIsTap(35, false) &&
              !touchIsTap(650, false) && !touchIsTap(100, true),
              "touch routing keeps menu, bonk and media separate");
constexpr TouchRect start_button{22, 229, 217, 272};
constexpr TouchRect reset_button{22, 276, 217, 319};
constexpr TouchRect times_button{158, 4, 231, 47};
static_assert(focusActionForTap(start_button, reset_button, times_button,
                                3090, 2050, 3094, 2054, 180) == FocusAction::Toggle &&
              focusActionForTap(start_button, reset_button, times_button,
                                3645, 2050, 3649, 2054, 180) == FocusAction::Reset &&
              focusActionForTap(start_button, reset_button, times_button,
                                480, 700, 484, 704, 180) == FocusAction::Settings &&
              focusActionForTap(start_button, reset_button, times_button,
                                480, 3260, 484, 3264, 180) == FocusAction::None,
              "reversed raw horizontal axis reaches the displayed right-side TIDER");
constexpr TouchRect focus_plus{20, 57, 219, 100};
constexpr TouchRect focus_minus{20, 101, 219, 144};
constexpr TouchRect break_plus{20, 175, 219, 218};
constexpr TouchRect break_minus{20, 219, 219, 262};
constexpr TouchRect save{22, 269, 217, 316};
constexpr FocusSettingsAction settingAt(uint16_t raw_x) {
    return focusSettingsActionForTap(focus_minus, focus_plus,
        break_minus, break_plus, save, raw_x, 2050, raw_x + 4, 2054, 180);
}
static_assert(settingAt(1080) == FocusSettingsAction::FocusPlus &&
              settingAt(1575) == FocusSettingsAction::FocusMinus &&
              settingAt(2440) == FocusSettingsAction::BreakPlus &&
              settingAt(2950) == FocusSettingsAction::BreakMinus &&
              settingAt(3580) == FocusSettingsAction::Save &&
              focusSettingsActionForTap(focus_minus, focus_plus,
                  break_minus, break_plus, save, 1080, 2050, 1575, 2050,
                  180) == FocusSettingsAction::None,
              "plus above minus with same-button swipe rejection");
constexpr TouchRect bongo_choice{20, 45, 215, 94};
constexpr TouchRect player_choice{20, 106, 215, 155};
constexpr TouchRect focus_choice{20, 167, 215, 216};
constexpr TouchRect settings_choice{20, 228, 215, 277};
static_assert(menuChoiceForTap(bongo_choice, player_choice, focus_choice,
                               settings_choice,
                               1000, 2050, 1004, 2054, 419) == MenuChoice::Bongo &&
              menuChoiceForTap(bongo_choice, player_choice, focus_choice,
                               settings_choice,
                               1000, 600, 1004, 604, 419) == MenuChoice::Bongo &&
              menuChoiceForTap(bongo_choice, player_choice, focus_choice,
                               settings_choice,
                               1000, 3500, 1004, 3504, 419) == MenuChoice::Bongo &&
              menuChoiceForTap(bongo_choice, player_choice, focus_choice,
                               settings_choice,
                               1700, 2050, 1704, 2054, 419) == MenuChoice::Player &&
              menuChoiceForTap(bongo_choice, player_choice, focus_choice,
                               settings_choice,
                               2400, 2050, 2404, 2054, 419) == MenuChoice::Focus &&
              menuChoiceForTap(bongo_choice, player_choice, focus_choice,
                               settings_choice,
                               3100, 2050, 3104, 2054, 419) == MenuChoice::Settings,
              "all four menu choices route correctly");
constexpr TouchRect theme_button{16, 48, 223, 95};
constexpr TouchRect auto_button{16, 105, 223, 162};
constexpr TouchRect led_button{16, 171, 223, 228};
constexpr TouchRect back_button{16, 259, 223, 306};
static_assert(localSettingsActionForTap(theme_button, auto_button, led_button,
                                        back_button, 1000, 2050, 1004, 2054, 180) ==
                  LocalSettingsAction::Theme &&
              localSettingsActionForTap(theme_button, auto_button, led_button,
                                        back_button, 1700, 2050, 1704, 2054, 180) ==
                  LocalSettingsAction::AutoShow &&
              localSettingsActionForTap(theme_button, auto_button, led_button,
                                        back_button, 2500, 2050, 2504, 2054, 180) ==
                  LocalSettingsAction::Led &&
              localSettingsActionForTap(theme_button, auto_button, led_button,
                                        back_button, 3500, 2050, 3504, 2054, 180) ==
                  LocalSettingsAction::Back,
              "settings targets are distinct and do not route to media/bonk");

int main() { return 0; }
