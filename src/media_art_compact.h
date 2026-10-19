#pragma once

constexpr unsigned int COMPACT_ART_EDGE = 80;
constexpr unsigned int COMPACT_ART_PIXELS = COMPACT_ART_EDGE * COMPACT_ART_EDGE;
constexpr unsigned int COMPACT_ART_BYTES = COMPACT_ART_PIXELS * 2;

// The source occupies the first 6400 words of the inactive 112px slot.
// Centre-nearest sourceIndex <= destinationIndex: reverse traversal never
// overwrites a source word needed by a later iteration. No second image buffer.
inline bool expandCompactArtwork565(unsigned short *slot, unsigned int capacity) {
    constexpr int edge = 112;
    if (!slot || capacity < edge * edge) return false;
    for (int y = edge - 1; y >= 0; --y) {
        const int sy = ((2 * y + 1) * COMPACT_ART_EDGE) / (2 * edge);
        for (int x = edge - 1; x >= 0; --x) {
            const int sx = ((2 * x + 1) * COMPACT_ART_EDGE) / (2 * edge);
            slot[y * edge + x] = slot[sy * COMPACT_ART_EDGE + sx];
        }
    }
    return true;
}
