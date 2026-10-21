#pragma once
#include "media_record_flip.h"

// Allocation-free scene state and integer drawing shared by ESP32 and host.
// Owns identities/poses and two slot indices, never pixel storage.
constexpr unsigned int TURNTABLE_CLEAR_END_MS = 160;
constexpr unsigned int TURNTABLE_REACH_END_MS = 300;
constexpr unsigned int TURNTABLE_GRIP_END_MS = 420;
constexpr unsigned int TURNTABLE_LIFT_END_MS = 680;
constexpr unsigned int TURNTABLE_FLIP_END_MS = 1060;
constexpr unsigned int TURNTABLE_FACE_SWITCH_MS =
    (TURNTABLE_LIFT_END_MS + TURNTABLE_FLIP_END_MS) / 2;
constexpr unsigned int TURNTABLE_FULL_OUT_END_MS = 1070;
constexpr unsigned int TURNTABLE_FULL_IN_END_MS = 1550;
constexpr unsigned int TURNTABLE_LOWER_END_MS = 1380;
constexpr unsigned int TURNTABLE_FULL_LOWER_END_MS = 1870;
constexpr unsigned int TURNTABLE_SETTLE_END_MS = 1460;
constexpr unsigned int TURNTABLE_FULL_SETTLE_END_MS = 1950;
constexpr unsigned int TURNTABLE_WITHDRAW_END_MS = 1580;
constexpr unsigned int TURNTABLE_FULL_WITHDRAW_END_MS = 2070;
constexpr unsigned int TURNTABLE_CHANGE_MS = 1880;
constexpr unsigned int TURNTABLE_FULL_MS = 2380;
constexpr unsigned int TURNTABLE_REVEAL_MS = 180;
constexpr int TURNTABLE_LIFT_PIXELS = 5;
constexpr int TURNTABLE_RADIUS = 56;

inline int ttLerp(int a, int b, unsigned int elapsed, unsigned int duration) {
    return elapsed >= duration ? b : a + (b - a) * static_cast<int>(elapsed) / static_cast<int>(duration);
}
inline int ttClamp(int n, int lo, int hi) { return n < lo ? lo : n > hi ? hi : n; }
inline int ttSmoothLerp(int a, int b, unsigned int elapsed, unsigned int duration) {
    if (elapsed >= duration) return b;
    const int q = static_cast<int>(elapsed * 1024 / duration);
    const int eased = q * q * (3072 - 2*q) / (1024*1024);
    return a + (b-a) * eased / 1024;
}

struct TurntableFrame {
    RecordSide side;
    int height, dx, dy, paw_x, paw_y, reveal;
    int groove, arm_engaged, arm_lift;
    bool changing, full, paw;
};

inline bool ttSameDisc(const TurntableFrame &a, const TurntableFrame &b) {
    return a.side == b.side && a.height == b.height && a.dx == b.dx &&
           a.dy == b.dy && a.reveal == b.reveal && a.changing == b.changing;
}

class MediaTurntable {
public:
    bool request(RecordSide side, unsigned int now, bool animate) {
        if (side == RecordSide::Artwork) return artwork(now, animate);
        const bool changed = shown_art_ || physical_ || reveal_;
        art_ = shown_art_ = false;
        physical_ = reveal_ = stable_pending_ = waiting_ = false;
        return changed;
    }

    bool trackDefault(unsigned int, unsigned int, bool) {
        // DEFAULT is preparation, not a second identity/change event.
        return false;
    }

    bool trackContext(unsigned int context, unsigned int now, bool animate) {
        if (context == context_ || (context && context == last_nonzero_)) {
            context_ = context;
            return false;
        }
        context_ = context;
        if (!context) return request(RecordSide::Generic, now, false);
        const bool known = last_nonzero_ != 0;
        if (stable_pending_ && now - last_change_ >= 400) ++completed_;
        stable_pending_ = false;
        last_nonzero_ = context;
        target_groove_ = 350;
        art_ = false; reveal_ = false;
        if (known) ++changes_;
        if (known && animate) {
            if (!physical_) startChange(now);
            else if (face_switched_) waiting_ = true;
            // Before the edge, replace only the target. After it, finish the
            // current motion, then take the single latest target to a new edge.
        } else {
            physical_ = waiting_ = false;
            shown_art_ = false;
        }
        last_change_ = now;
        return true;
    }

    bool artwork(unsigned int now, bool animate) {
        return artworkInSlot(visible_slot_, context_, now, animate);
    }

    unsigned char visibleSlot() const { return visible_slot_; }
    unsigned char beginArtwork() {
        // Keep the displayed slot pinned even when its descriptor is hidden.
        // A new BEGIN may replace staging, never the still-visible old face.
        if (staged_slot_ != visible_slot_) art_ = false;
        return 1 - visible_slot_;
    }

    bool artworkInSlot(unsigned char slot, unsigned int context,
                       unsigned int now, bool animate) {
        if (context != context_ || slot > 1) return false;
        const bool changed = !art_ || !shown_art_ || staged_slot_ != slot;
        art_ = true; staged_slot_ = slot;
        if (!physical_ || (face_switched_ && !waiting_)) {
            const bool first = !shown_art_;
            commitFace();
            if (first && animate) { reveal_ = true; reveal_began_ = now; }
        }
        return changed;
    }

    void playback(bool playing, unsigned int position, unsigned int duration) {
        playing_ = playing;
        position_ = position;
        duration_ = duration;
    }

    TurntableFrame frame(unsigned int now, bool visible) {
        if (duration_) target_groove_ = position_ >= duration_ ? 1000 :
            static_cast<int>((static_cast<unsigned long long>(position_) * 1000) / duration_);
        // Unknown duration on this identity holds the last known groove target.
        const int goal = target_groove_;
        unsigned int dt = sampled_ ? now - sampled_at_ : 20;
        sampled_at_ = now; sampled_ = true;
        dt = dt > 50 ? 50 : dt;
        groove_q16_ += static_cast<int>((static_cast<long long>(goal * 65536 - groove_q16_) * dt) / (280 + dt));
        groove_ = (groove_q16_ + 32768) / 65536;
        if (!visible || !visible_) {
            physical_ = reveal_ = stable_pending_ = waiting_ = false;
            commitFace();
            groove_ = goal;
            groove_q16_ = goal * 65536;
            engaged_ = playing_ ? 1000 : 0;
            lift_ = playing_ ? 0 : 1000;
            wanted_ = playing_;
            arm_phase_ = playing_ ? ArmPhase::Down : ArmPhase::Parked;
        }
        visible_ = visible;
        unsigned int t = physical_ ? now - began_ : 0;
        const unsigned int end = full_ ? TURNTABLE_FULL_MS : TURNTABLE_CHANGE_MS;
        bool show_edge = false;
        if (physical_ && !face_switched_ &&
            t >= (full_ ? TURNTABLE_FULL_OUT_END_MS : TURNTABLE_FACE_SWITCH_MS)) {
            commitFace();
            face_switched_ = true;
            show_edge = true;
        }
        if (physical_ && t >= end && !show_edge) {
            if (waiting_) {
                // No list of stale images and no pose jump in the old motion.
                waiting_ = false; startChange(now); t = 0;
            } else { physical_ = false; stable_pending_ = true; }
        }
        if (stable_pending_ && now - last_change_ >= 400) {
            ++completed_; stable_pending_ = false;
        }
        if (reveal_ && now - reveal_began_ >= TURNTABLE_REVEAL_MS) reveal_ = false;
        // Even after a long frame gap, paint one thin/offscreen pose before a
        // full new face. This holds no RX/ACK and does not restart the clock.
        if (show_edge) t = full_ ? TURNTABLE_FULL_OUT_END_MS : TURNTABLE_FACE_SWITCH_MS;
        const unsigned int withdrawal = full_ ? TURNTABLE_FULL_WITHDRAW_END_MS : TURNTABLE_WITHDRAW_END_MS;
        const bool clear = physical_ && t < withdrawal;
        updateArm(now, playing_ && !clear, clear);

        TurntableFrame f = {shown_art_ ? RecordSide::Artwork : RecordSide::Generic,
            112, 0, 0, -114, 0, reveal_ ? ttLerp(0, 256, now - reveal_began_, TURNTABLE_REVEAL_MS) : 256,
            groove_, engaged_, lift_, physical_ || reveal_, physical_ && full_, false};
        if (!physical_) return f;
        const unsigned int lower_begin = full_ ? TURNTABLE_FULL_IN_END_MS : TURNTABLE_FLIP_END_MS;
        const unsigned int lower_end = full_ ? TURNTABLE_FULL_LOWER_END_MS : TURNTABLE_LOWER_END_MS;
        const unsigned int leave = full_ ? TURNTABLE_FULL_SETTLE_END_MS : TURNTABLE_SETTLE_END_MS;
        f.paw = t >= TURNTABLE_CLEAR_END_MS && t < withdrawal;
        int approach = t < TURNTABLE_REACH_END_MS ? ttSmoothLerp(-60, 0,
            t < TURNTABLE_CLEAR_END_MS ? 0 : t - TURNTABLE_CLEAR_END_MS,
            TURNTABLE_REACH_END_MS - TURNTABLE_CLEAR_END_MS) : 0;
        if (t >= TURNTABLE_GRIP_END_MS)
            f.dy = ttSmoothLerp(0, -TURNTABLE_LIFT_PIXELS, t - TURNTABLE_GRIP_END_MS,
                                TURNTABLE_LIFT_END_MS - TURNTABLE_GRIP_END_MS);
        if (full_) {
            if (t >= TURNTABLE_LIFT_END_MS && t < TURNTABLE_FULL_OUT_END_MS)
                f.dx = ttSmoothLerp(0, -160, t - TURNTABLE_LIFT_END_MS,
                                    TURNTABLE_FULL_OUT_END_MS - TURNTABLE_LIFT_END_MS);
            else if (t >= TURNTABLE_FULL_OUT_END_MS && t < TURNTABLE_FULL_IN_END_MS)
                f.dx = ttSmoothLerp(-160, 0, t - TURNTABLE_FULL_OUT_END_MS,
                                    TURNTABLE_FULL_IN_END_MS - TURNTABLE_FULL_OUT_END_MS);
        } else if (t >= TURNTABLE_LIFT_END_MS && t < TURNTABLE_FLIP_END_MS) {
            const unsigned int flip = t - TURNTABLE_LIFT_END_MS;
            const unsigned int half = (TURNTABLE_FLIP_END_MS - TURNTABLE_LIFT_END_MS) / 2;
            f.height = flip <= half ? ttSmoothLerp(112, 2, flip, half) : ttSmoothLerp(2, 112, flip-half, half);
        }
        if (t >= lower_begin) {
            f.dy = ttSmoothLerp(-TURNTABLE_LIFT_PIXELS, 0, t-lower_begin, lower_end-lower_begin);
        }
        if (t >= lower_end) {
            const unsigned int settle = t-lower_end;
            f.dy = settle < 20 ? ttLerp(0, 1, settle, 20) : settle < 40 ? ttLerp(1, 0, settle-20, 20) : 0;
            f.height = f.dy ? 110 : 112;
        }
        if (t >= leave) approach = ttSmoothLerp(0, -60, t-leave, withdrawal-leave);
        f.paw_x = f.dx - 56 + approach;
        f.paw_y = f.dy;
        return f;
    }

    bool moving() const { return physical_ || reveal_; }
    unsigned int changes() const { return changes_; }
    unsigned int completed() const { return completed_; }

private:
    void commitFace() {
        shown_art_ = art_;
        if (art_) visible_slot_ = staged_slot_;
    }
    void startChange(unsigned int now) {
        full_ = completed_ % 5 == 4 && now - last_change_ >= 400;
        began_ = now; physical_ = true; face_switched_ = false;
    }
    enum class ArmPhase : unsigned char { Parked, Raise, SwingOut, SwingIn, Lower, Down };
    void startArm(ArmPhase phase, unsigned int now) {
        arm_phase_ = phase; arm_began_ = now;
        from_engaged_ = engaged_; from_lift_ = lift_;
    }
    void updateArm(unsigned int now, bool down, bool fast) {
        if (down != wanted_) {
            wanted_ = down;
            startArm(lift_ < 1000 ? ArmPhase::Raise : down ? ArmPhase::SwingIn : ArmPhase::SwingOut, now);
        }
        for (int i = 0; i < 3; ++i) {
            const unsigned int elapsed = now - arm_began_;
            unsigned int duration = 0;
            ArmPhase next = arm_phase_;
            if (arm_phase_ == ArmPhase::Raise) {
                duration = fast ? 80 : 100;
                lift_ = ttLerp(from_lift_, 1000, elapsed, duration);
                next = wanted_ ? ArmPhase::SwingIn : ArmPhase::SwingOut;
            } else if (arm_phase_ == ArmPhase::SwingOut) {
                duration = fast ? 80 : 180;
                engaged_ = ttLerp(from_engaged_, 0, elapsed, duration); lift_ = 1000;
                next = ArmPhase::Parked;
            } else if (arm_phase_ == ArmPhase::SwingIn) {
                duration = 180;
                engaged_ = ttLerp(from_engaged_, 1000, elapsed, duration); lift_ = 1000;
                next = ArmPhase::Lower;
            } else if (arm_phase_ == ArmPhase::Lower) {
                duration = 100;
                engaged_ = 1000; lift_ = ttLerp(from_lift_, 0, elapsed, duration);
                next = ArmPhase::Down;
            } else if (arm_phase_ == ArmPhase::Down) { engaged_ = 1000; lift_ = 0; }
            else { engaged_ = 0; lift_ = 1000; }
            if (!duration || elapsed < duration) break;
            startArm(next, arm_began_ + duration);
        }
    }

    unsigned int context_ = 0, last_nonzero_ = 0, last_change_ = 0, began_ = 0;
    unsigned int reveal_began_ = 0, sampled_at_ = 0, arm_began_ = 0;
    unsigned int position_ = 0, duration_ = 0, changes_ = 0, completed_ = 0;
    int groove_ = 350, groove_q16_ = 350*65536, target_groove_ = 350;
    int engaged_ = 0, lift_ = 1000, from_engaged_ = 0, from_lift_ = 1000;
    unsigned char visible_slot_ = 0, staged_slot_ = 0;
    bool art_ = false, shown_art_ = false, physical_ = false, full_ = false, reveal_ = false;
    bool face_switched_ = false, waiting_ = false;
    bool visible_ = false, sampled_ = false, playing_ = false, wanted_ = false;
    bool stable_pending_ = false;
    ArmPhase arm_phase_ = ArmPhase::Parked;
};

inline unsigned short ttGenericPixel(int x, int y, const RecordPalette &p) {
    const int dx = x - 56, dy = y - 56, r = dx * dx + dy * dy;
    if (r > TURNTABLE_RADIUS * TURNTABLE_RADIUS) return p.chroma;
    unsigned short color = p.record;
    if ((r >= 47*47 && r <= 48*48) || (r >= 38*38 && r <= 39*39) ||
        (r >= 29*29 && r <= 30*30)) color = p.groove;
    if (r <= 23*23) color = p.label;
    if (r <= 5*5) color = p.spindle;
    if (r <= 2*2) color = p.record;
    return color;
}

inline unsigned short ttBlend(unsigned short a, unsigned short b, int mix) {
    // LV_COLOR_16_SWAP=1, as in the established transport/host palette.
    a = static_cast<unsigned short>((a << 8) | (a >> 8));
    b = static_cast<unsigned short>((b << 8) | (b >> 8));
    const int red = ttLerp((a >> 11) & 31, (b >> 11) & 31, mix, 256);
    const int green = ttLerp((a >> 5) & 63, (b >> 5) & 63, mix, 256);
    const int blue = ttLerp(a & 31, b & 31, mix, 256);
    const unsigned short c = static_cast<unsigned short>((red << 11) | (green << 5) | blue);
    return static_cast<unsigned short>((c << 8) | (c >> 8));
}

inline bool renderTurntableDisc(unsigned short *out, unsigned int capacity, const unsigned short *art,
                                const TurntableFrame &f, int sine, int cosine, const RecordPalette &p) {
    if (!out || capacity < 112*112) return false;
    const unsigned long long destination = reinterpret_cast<unsigned long long>(out);
    const unsigned long long source = reinterpret_cast<unsigned long long>(art);
    if (art && destination < source + 112*112*2 && source < destination + 112*112*2) return false;
    const int height = ttClamp(f.height, 2, 112), top = (112 - height) / 2;
    for (int y = 0; y < 112; ++y) for (int x = 0; x < 112; ++x) {
        unsigned short color = p.chroma;
        if (y >= top && y < top + height) {
            const int dx = x - 56, dy = ((2*(y-top)+1)*112)/(2*height)-56;
            const int sx = 56 + recordQ15(cosine*dx+sine*dy);
            const int sy = 56 + recordQ15(-sine*dx+cosine*dy);
            if (height == 2) color = p.groove;
            else if (sx >= 0 && sx < 112 && sy >= 0 && sy < 112 && dx*dx+dy*dy <= 56*56) {
                const unsigned short generic = ttGenericPixel(sx, sy, p);
                color = f.side == RecordSide::Artwork && art ? art[sy*112+sx] : generic;
                if (f.side == RecordSide::Artwork && art && f.reveal < 256 && color != p.chroma)
                    color = ttBlend(generic == p.chroma ? p.record : generic, color, f.reveal);
            }
        }
        out[y*112+x] = color;
    }
    return true;
}

inline bool renderTurntableGenericReduced(unsigned short *out, unsigned int capacity, const RecordPalette &p) {
    if (!out || capacity < 56*56) return false;
    for (int y=0;y<56;++y) for (int x=0;x<56;++x) out[y*56+x]=ttGenericPixel(2*x,2*y,p);
    return true;
}

struct TurntableGeometry { int cx, cy, zoom, pivot_x, pivot_y, tip_x, tip_y, lift, paw_x, paw_y; };
inline TurntableGeometry turntableGeometry(const TurntableFrame &f, bool compact) {
    // Fixed pivot and arm length in both layouts. Interpolated Q15 unit circle.
    static const int sine[] = {0,572,1144,1715,2286,2856,3425,3993,4560,5126,5690,6252,6813,
        7371,7927,8481,9032,9580,10126,10668,11207,11743,12275,12803,13327,13848,14365,
        14876,15384,15887,16384,16877,17364,17847,18324,18795,19261,19721,20174,20622,21063};
    static const int cosine[] = {32768,32763,32748,32723,32688,32643,32588,32524,32449,32365,
        32270,32166,32052,31929,31795,31651,31499,31336,31165,30984,30792,30592,30382,
        30163,29935,29698,29452,29197,28932,28659,28378,28087,27788,27481,27165,26842,
        26510,26170,25822,25466,25102};
    const int target = (compact ? 25000 : 20000) + f.groove * (compact ? 13000 : 16000) / 1000;
    const int angle = ttClamp(target * f.arm_engaged / 1000, 0, 40000);
    const int whole = angle/1000, part = angle%1000, next=whole<40?whole+1:40;
    const int s=ttLerp(sine[whole],sine[next],part,1000), c=ttLerp(cosine[whole],cosine[next],part,1000);
    const int zoom=compact?320:384, cy=compact?126:112;
    return {120,cy,zoom,214,60,214-recordQ15(106*s),60+recordQ15(106*c),
            f.arm_lift*3/1000,120+f.paw_x*zoom/256,cy+f.paw_y*zoom/256};
}

enum class TurntableShape : unsigned char { Rect, Line };
struct TurntablePrimitive { TurntableShape shape; short x1,y1,x2,y2; unsigned short color; unsigned char width; };
struct TurntablePalette { unsigned short black, white, steel, gray, pink; };
inline int turntablePrimitives(const TurntableFrame &f, bool compact, bool paw,
                               const TurntablePalette &p, TurntablePrimitive *out, int capacity) {
    int count=0;
    const auto add=[&](TurntableShape shape,int x1,int y1,int x2,int y2,unsigned short color,int width) {
        if (shape == TurntableShape::Rect && (x1 > x2 || y1 > y2)) return;
        if(count<capacity)out[count++]={shape,static_cast<short>(x1),static_cast<short>(y1),
            static_cast<short>(x2),static_cast<short>(y2),color,static_cast<unsigned char>(width)};
    };
    const TurntableGeometry g=turntableGeometry(f,compact);
    if (paw) {
        if(!f.paw || g.paw_x+3 < 0)return 0;
        // Forearm continues past the left clip edge. Draw all contour pieces
        // before the white core so no black vertical seam splits the wrist.
        const int wrist = g.paw_x-20, end = wrist+4, joint = wrist > 8 ? wrist-8 : -2;
        if (end >= 0) {
            add(TurntableShape::Rect,-2,g.paw_y-8,joint,g.paw_y+7,p.black,1);
            add(TurntableShape::Rect,joint,g.paw_y-6,end,g.paw_y+5,p.black,1);
            add(TurntableShape::Rect,-2,g.paw_y-6,joint+1,g.paw_y+5,p.white,1);
            add(TurntableShape::Rect,joint,g.paw_y-4,end,g.paw_y+3,p.white,1);
        }
        // Horizontal 2x pixel paw: white, black contour and small pink pads,
        // following the established Bongo 9x12 paw's stepped pixel language.
        static const char mask[9][13]={"  BBBBBBB   "," BBWWWWWWBB ","BBWWWWWWWWWB",
            "WWWWWWWWWWWB","WWWWWPWWWWWB","WWWWWPPWWWWB","BBWWWWWWWWWB",
            " BBBWWWWWWB ","   BBBBBBB  "};
        for(int y=0;y<9;++y)for(int x=0;x<12;){
            const char color=mask[y][x];int end=x+1;while(end<12&&mask[y][end]==color)++end;
            if(color!=' ')add(TurntableShape::Rect,g.paw_x-20+x*2,g.paw_y-9+y*2,
                g.paw_x-20+end*2-1,g.paw_y-8+y*2,color=='B'?p.black:color=='P'?p.pink:p.white,1);
            x=end;
        }
    } else {
        const int tx=g.tip_x,ty=g.tip_y-g.lift;
        if(g.lift)add(TurntableShape::Line,g.pivot_x+2,g.pivot_y+2,tx+2,ty+3,p.black,5);
        add(TurntableShape::Line,g.pivot_x,g.pivot_y,tx,ty,p.black,5);
        add(TurntableShape::Line,g.pivot_x,g.pivot_y,tx,ty,p.steel,2);
        add(TurntableShape::Rect,tx-4,ty-3,tx+3,ty+5,p.black,1);
        add(TurntableShape::Rect,tx-2,ty-2,tx+1,ty+3,p.gray,1);
        add(TurntableShape::Rect,tx-1,ty+4,tx,ty+5,p.white,1);
        add(TurntableShape::Rect,g.pivot_x-4,g.pivot_y-3,g.pivot_x+4,g.pivot_y+3,p.black,1);
        add(TurntableShape::Rect,g.pivot_x-3,g.pivot_y-2,g.pivot_x+3,g.pivot_y+2,p.gray,1);
        add(TurntableShape::Rect,g.pivot_x-1,g.pivot_y-1,g.pivot_x+1,g.pivot_y+1,p.steel,1);
    }
    return count;
}
