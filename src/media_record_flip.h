#pragma once

// Integer-only state/rendering shared by firmware and the freestanding host
// fixture. No LVGL, heap, transport buffer ownership, threads or dependencies.
enum class RecordSide : unsigned char { Generic, Artwork };
constexpr unsigned int RECORD_FLIP_MS = 280;
constexpr unsigned int RECORD_FLIP_FRAME_MS = 20;
constexpr int RECORD_PIXELS = 112;

struct RecordFrame {
    RecordSide side;
    unsigned char step;
    bool moving;
};

constexpr int recordHeight(unsigned int step) {
    return step == 0 || step >= 14 ? 112 :
           step == 1 || step == 13 ? 109 :
           step == 2 || step == 12 ? 101 :
           step == 3 || step == 11 ? 88 :
           step == 4 || step == 10 ? 70 :
           step == 5 || step == 9 ? 49 :
           step == 6 || step == 8 ? 25 : 2;
}

class MediaRecordFlip {
public:
    bool request(RecordSide next, unsigned int now, bool animate) {
        if (!animate || !initialized_) {
            const bool changed = !initialized_ || moving_ || target_ != next;
            initialized_ = true;
            shown_ = from_ = target_ = next;
            moving_ = false;
            return changed;
        }
        if (next == target_) return false;
        if (moving_) {
            // A completed cover can make the old active slot writable by the
            // NEXT BEGIN. Never retain/read that old face. Open latest art
            // from the edge; a superseding track settles directly to generic.
            target_ = next;
            from_ = RecordSide::Generic;
            if (next == RecordSide::Artwork) {
                began_ = now - RECORD_FLIP_MS / 2;
            } else {
                shown_ = next;
                moving_ = false;
            }
            return true;
        }
        from_ = shown_;
        target_ = next;
        began_ = now;
        moving_ = true;
        return true;
    }

    bool trackDefault(unsigned int revision, unsigned int now, bool animate) {
        default_open_ = true;
        default_applied_ = revision != last_revision_;
        last_revision_ = revision;
        return default_applied_ && request(RecordSide::Generic, now, animate);
    }

    bool trackContext(unsigned int context, unsigned int now, bool animate) {
        // A key can change while title/artist stay identical. Its existing
        // context marker still identifies a real change without a DEFAULT.
        const bool changed = context != last_context_ &&
            ((default_open_ && !default_applied_) || (!default_open_ && last_context_ != 0));
        last_context_ = context;
        default_open_ = false;
        return changed && request(RecordSide::Generic, now, animate);
    }

    bool artwork(unsigned int now, bool animate) {
        default_open_ = false;
        return request(RecordSide::Artwork, now, animate);
    }

    RecordFrame frame(unsigned int now, bool visible) {
        if (moving_ && (!visible || now - began_ >= RECORD_FLIP_MS)) {
            shown_ = target_;
            moving_ = false;
        }
        unsigned int step = moving_ ? (now - began_) / RECORD_FLIP_FRAME_MS : 14;
        return {moving_ && step < 7 ? from_ : target_,
                static_cast<unsigned char>(step), moving_};
    }
    bool moving() const { return moving_; }

private:
    RecordSide shown_ = RecordSide::Generic, from_ = RecordSide::Generic;
    RecordSide target_ = RecordSide::Generic;
    unsigned int began_ = 0, last_revision_ = 0, last_context_ = 0;
    bool initialized_ = false, moving_ = false;
    bool default_open_ = false, default_applied_ = false;
};

struct RecordPalette {
    unsigned short chroma, record, groove, label, spindle;
};

inline unsigned short recordGenericPixel(int x, int y, const RecordPalette &p) {
    int dx = x - 56, dy = y - 56, r = dx * dx + dy * dy;
    unsigned short pixel = r <= 46 * 46 ? p.record : p.chroma;
    if ((r >= 38 * 38 && r <= 39 * 39) || (r >= 31 * 31 && r <= 32 * 32)) pixel = p.groove;
    if (r <= 24 * 24) pixel = p.label;
    if (r <= 5 * 5) pixel = p.spindle;
    if (r <= 2 * 2) pixel = p.record;
    dy = y - 17;
    if (dx * dx + dy * dy <= 9) pixel = p.label;
    return pixel;
}

inline int recordQ15(int value) { return (value + (value < 0 ? -16384 : 16384)) / 32768; }

inline bool renderRecordGenericReduced(unsigned short *out, unsigned int capacity,
                                        const RecordPalette &palette) {
    if (!out || capacity < 56 * 56) return false;
    for (int y = 0; y < 56; ++y)
        for (int x = 0; x < 56; ++x)
            out[y * 56 + x] = recordGenericPixel(2 * x, 2 * y, palette);
    return true;
}

// Snapshot no source pointer: callers supply only the current committed art.
// Output never aliases either transport slot. Trig is Q15, angle stays fixed
// for a flip. Normal uniform LVGL zoom handles both 172/144 px viewports.
inline void renderRecordFrame(unsigned short *out, const unsigned short *art,
                              RecordFrame frame, int sine, int cosine,
                              const RecordPalette &palette) {
    const int height = frame.moving ? recordHeight(frame.step) : RECORD_PIXELS;
    const int top = (RECORD_PIXELS - height) / 2;
    for (int y = 0; y < RECORD_PIXELS; ++y) {
        for (int x = 0; x < RECORD_PIXELS; ++x) {
            unsigned short pixel = palette.chroma;
            if (y >= top && y < top + height) {
                if (height == 2) {
                    // Never protrude past the smaller existing generic disc.
                    if (x >= 10 && x < 102) pixel = palette.groove;
                } else {
                    int dy = ((2 * (y - top) + 1) * RECORD_PIXELS) / (2 * height) - 56;
                    int dx = x - 56;
                    int sx = 56 + recordQ15(cosine * dx + sine * dy);
                    int sy = 56 + recordQ15(-sine * dx + cosine * dy);
                    if (sx >= 0 && sx < RECORD_PIXELS && sy >= 0 && sy < RECORD_PIXELS)
                        pixel = frame.side == RecordSide::Artwork && art ?
                            art[sy * RECORD_PIXELS + sx] : recordGenericPixel(sx, sy, palette);
                }
            }
            out[y * RECORD_PIXELS + x] = pixel;
        }
    }
}
