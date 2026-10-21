#pragma once

#include <stdio.h>
#include "focus_logic.h"

struct FocusCountdownView {
    bool visible;
    bool paused;
    FocusPhase phase;
    uint32_t seconds;
};

constexpr FocusCountdownView focusCountdownView(FocusState state) {
    return state.mode == FocusMode::Running || state.mode == FocusMode::Paused ?
        FocusCountdownView{true, state.mode == FocusMode::Paused, state.phase,
                           focusDisplaySeconds(state)} :
        FocusCountdownView{false, false, FocusPhase::Focus, 0};
}

constexpr bool focusCountdownEqual(FocusCountdownView a, FocusCountdownView b) {
    return a.visible == b.visible && a.paused == b.paused &&
           a.phase == b.phase && a.seconds == b.seconds;
}

// Labels borrow these lifetime-stable buffers with LVGL's static-text API.
// Subsecond ticks and changes to an inactive timer do not invalidate labels.
class FocusCountdownCache {
public:
    bool update(FocusState state) {
        const FocusCountdownView next = focusCountdownView(state);
        if (focusCountdownEqual(view_, next)) return false;
        if (next.visible) {
            if (!view_.visible || next.seconds != view_.seconds)
                snprintf(time_text_, sizeof(time_text_), "%02lu:%02lu",
                         (unsigned long)(next.seconds / 60),
                         (unsigned long)(next.seconds % 60));
        } else {
            time_text_[0] = '\0';
        }
        view_ = next;
        return true;
    }

    bool visible() const { return view_.visible; }
    FocusCountdownView view() const { return view_; }
    const char *phaseText() const {
        return !view_.visible ? "" : view_.phase == FocusPhase::Focus ? "FOKUS:" : "PAUS:";
    }
    const char *phaseName() const { return view_.phase == FocusPhase::Focus ? "FOKUS" : "PAUS"; }
    const char *timeText() const { return time_text_; }

private:
    FocusCountdownView view_ = {false, false, FocusPhase::Focus, 0};
    char time_text_[12] = {};
};
