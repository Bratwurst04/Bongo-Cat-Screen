#pragma once

#include <stddef.h>
#include <stdint.h>

// The line-framed transport may interleave ordinary serial commands between
// chunks. Only a complete, ordered frame with the advertised CRC may be shown.
struct MediaArtV2Transfer {
    explicit MediaArtV2Transfer(size_t frame_bytes) : frame_bytes(frame_bytes) {}

    void abort() {
        active = false;
        received = 0;
        crc = 0xFFFFFFFFu;
    }

    bool begin(uint16_t next_id, size_t length, uint32_t expected) {
        abort();
        if (!next_id || length != frame_bytes) return false;
        id = next_id;
        expected_crc = expected;
        active = true;
        return true;
    }

    bool accept(uint16_t chunk_id, size_t offset, const uint8_t *bytes, size_t length) {
        if (!active || chunk_id != id || offset != received || !bytes ||
            !length || length > 128 || received > frame_bytes ||
            length > frame_bytes - received) return false;
        for (size_t index = 0; index < length; ++index) {
            crc ^= bytes[index];
            for (uint8_t bit = 0; bit < 8; ++bit) {
                crc = (crc >> 1) ^ ((crc & 1u) ? 0xEDB88320u : 0u);
            }
        }
        received += length;
        return true;
    }

    bool complete(uint16_t end_id) const {
        return active && end_id == id && received == frame_bytes &&
               (~crc) == expected_crc;
    }

    const size_t frame_bytes;
    size_t received = 0;
    uint32_t crc = 0xFFFFFFFFu;
    uint32_t expected_crc = 0;
    uint16_t id = 0;
    bool active = false;
};
