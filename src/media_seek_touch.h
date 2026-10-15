#pragma once
#include "focus_logic.h"

// Approved half-open start area (16,262,210,31). Once latched, allow modest
// drift outside its edges; excessive vertical movement cancels permanently.
constexpr TouchRect mediaSeekRect() { return {16, 262, 225, 292}; }
constexpr int MEDIA_SEEK_MIN_RAW = 420;
constexpr int MEDIA_SEEK_NOISE_RAW = 180;

struct MediaSeekContextValue { bool valid; uint32_t value; };
constexpr MediaSeekContextValue parseMediaSeekContextDigits(const char *text,
                                                            unsigned int length, uint32_t value) {
    return length == 0 ? MediaSeekContextValue{true, value} :
           text[0] >= '0' && text[0] <= '9' &&
           value <= (UINT32_MAX - uint32_t(text[0] - '0')) / 10 ?
           parseMediaSeekContextDigits(text + 1, length - 1, value * 10 + uint32_t(text[0] - '0')) :
           MediaSeekContextValue{false, 0};
}
constexpr MediaSeekContextValue parseMediaSeekContext(const char *text, unsigned int length) {
    return length > 0 && length <= 10 && (length == 1 || text[0] != '0') ?
           parseMediaSeekContextDigits(text, length, 0) : MediaSeekContextValue{false, 0};
}

constexpr bool mediaSeekStartHit(PanelId panel, bool in_menu, bool has_track,
                                 uint32_t duration, uint16_t raw_x, uint16_t raw_y) {
    return panel == PanelId::Player && !in_menu && has_track && duration > 0 &&
           rawPointInRect(mediaSeekRect(), raw_x, raw_y);
}

constexpr bool mediaSeekSampleCancelled(bool cancelled, uint16_t start_x,
                                         uint16_t raw_x) {
    return cancelled || focusAbs(int(raw_x) - int(start_x)) > MEDIA_SEEK_NOISE_RAW;
}

constexpr int mediaSeekDelta(int raw_vertical, int raw_horizontal) {
    return focusAbs(raw_horizontal) >= MEDIA_SEEK_MIN_RAW &&
           focusAbs(raw_horizontal) >= 2 * focusAbs(raw_vertical) ?
           (raw_horizontal < 0 ? 15 : -15) : 0;
}
