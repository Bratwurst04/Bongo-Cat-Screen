"""Deterministic transport-only packing; keep the cached 112px RGB888 intact."""
SOURCE_EDGE = 112
COMPACT_EDGE = 80
COMPACT_BYTES = COMPACT_EDGE * COMPACT_EDGE * 2


def pack_compact_rgb565(rgb888: bytes) -> bytes:
    """Centre nearest sampling, RGB565 big-endian; never blend the green key."""
    if len(rgb888) != SOURCE_EDGE * SOURCE_EDGE * 3:
        raise ValueError("Expected the existing 112x112 RGB888 frame")
    output = bytearray(COMPACT_BYTES)
    for y in range(COMPACT_EDGE):
        sy = ((2 * y + 1) * SOURCE_EDGE) // (2 * COMPACT_EDGE)
        for x in range(COMPACT_EDGE):
            sx = ((2 * x + 1) * SOURCE_EDGE) // (2 * COMPACT_EDGE)
            offset = (sy * SOURCE_EDGE + sx) * 3
            r, g, b = rgb888[offset:offset + 3]
            color = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            target = (y * COMPACT_EDGE + x) * 2
            output[target] = color >> 8
            output[target + 1] = color & 255
    return bytes(output)


def refinement_rgb888(rgb888: bytes, acknowledged_compact: bytes) -> bytes:
    """Keep the shown coarse opacity mask; refine its interior from full cache.

    Nearest80 expansion changes a few edge-key pixels. Retain those exact
    coarse pixels wherever either version is chroma, avoiding a size/halo pop.
    RGB565 channel truncation is idempotent through the existing ESP32 decoder.
    """
    if len(rgb888) != SOURCE_EDGE * SOURCE_EDGE * 3 or len(acknowledged_compact) != COMPACT_BYTES:
        raise ValueError("Expected full cache and its acknowledged compact payload")
    output = bytearray(rgb888)
    for y in range(SOURCE_EDGE):
        sy = ((2 * y + 1) * COMPACT_EDGE) // (2 * SOURCE_EDGE)
        for x in range(SOURCE_EDGE):
            sx = ((2 * x + 1) * COMPACT_EDGE) // (2 * SOURCE_EDGE)
            offset = (y * SOURCE_EDGE + x) * 3
            packed = (sy * COMPACT_EDGE + sx) * 2
            color = (acknowledged_compact[packed] << 8) | acknowledged_compact[packed + 1]
            r, g, b = rgb888[offset:offset + 3]
            full_color = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            if color == 0x07E0 or full_color == 0x07E0:
                output[offset:offset + 3] = bytes(((color >> 8) & 0xF8,
                    (color >> 3) & 0xFC, (color << 3) & 0xF8))
    return bytes(output)
