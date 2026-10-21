#pragma once
#include <stdint.h>

// Strict, bounded metadata identity for record artwork, including clear (0).
struct MediaTrackContextValue { bool valid; uint32_t value; };
constexpr MediaTrackContextValue parseMediaTrackContextDigits(const char *text,
                                                             unsigned int length, uint32_t value) {
    return length == 0 ? MediaTrackContextValue{true, value} :
           text[0] >= '0' && text[0] <= '9' &&
           value <= (UINT32_MAX - uint32_t(text[0] - '0')) / 10 ?
           parseMediaTrackContextDigits(text + 1, length - 1, value * 10 + uint32_t(text[0] - '0')) :
           MediaTrackContextValue{false, 0};
}
constexpr MediaTrackContextValue parseMediaTrackContext(const char *text, unsigned int length) {
    return length > 0 && length <= 10 && (length == 1 || text[0] != '0') ?
           parseMediaTrackContextDigits(text, length, 0) : MediaTrackContextValue{false, 0};
}
