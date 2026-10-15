#pragma once

#include "focus_countdown_layout.h"

// TouchRect uses inclusive ends; the approved x/y/width/height areas are
// half-open: Bongo (5,62,230,20), Player (36,16,168,37).
constexpr TouchRect focusStatusRect(PanelId panel) {
    return panel == PanelId::Bongo ? TouchRect{5, 62, 234, 81} :
           panel == PanelId::Player ? TouchRect{36, 16, 203, 52} :
                                     TouchRect{1, 1, 0, 0};
}

constexpr bool focusStatusHit(PanelId panel, FocusMode mode, bool in_menu,
                               uint16_t raw_x, uint16_t raw_y) {
    return !in_menu && (panel == PanelId::Bongo || panel == PanelId::Player) &&
           (mode == FocusMode::Running || mode == FocusMode::Paused) &&
           rawPointInRect(focusStatusRect(panel), raw_x, raw_y);
}

constexpr bool focusStatusDragCancelled(bool cancelled, PanelId panel,
                                         uint16_t start_x, uint16_t start_y,
                                         uint16_t x, uint16_t y, int max_move) {
    return cancelled || !rawTapInRect(focusStatusRect(panel),
                                     start_x, start_y, x, y, max_move);
}
