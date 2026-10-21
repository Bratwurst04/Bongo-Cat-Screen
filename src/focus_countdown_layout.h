#pragma once

#include "focus_countdown.h"

struct FocusMediaLayout {
    int x, y, size, radius;
    uint16_t art_zoom, cat_zoom;
};

constexpr FocusMediaLayout focusMediaLayout(bool visible) {
    return visible ? FocusMediaLayout{48, 54, 144, 72, 320, 560} :
                     FocusMediaLayout{34, 26, 172, 86, 384, 672};
}

constexpr bool focusCountdownIntegratedCue(bool visible, bool compact,
                                            FocusCueKind kind, PanelId panel,
                                            bool countdown_visible) {
    return visible && compact && countdown_visible && kind == FocusCueKind::FocusDone &&
           (panel == PanelId::Bongo || panel == PanelId::Player);
}
