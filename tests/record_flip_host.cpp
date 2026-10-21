#include "../src/media_record_flip.h"

typedef unsigned __int64 size_t;
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;
typedef unsigned int uint32_t;
#define UINT32_MAX 0xffffffffu
#include "track_context_fixture.inc"
#include "serial_receiver_fixture.inc"
static SerialLineReceiver<256> serial_receiver;
extern "C" __declspec(dllexport) void rf_serial_reset() { serial_receiver.reset(); }
extern "C" __declspec(dllexport) int rf_serial_push(unsigned char byte, unsigned int now) {
    return static_cast<int>(serial_receiver.push(byte, now));
}
extern "C" __declspec(dllexport) const char *rf_serial_line() { return serial_receiver.line(); }

static MediaRecordFlip state;
extern "C" __declspec(dllexport) void rf_reset() { state = MediaRecordFlip{}; }
extern "C" __declspec(dllexport) int rf_event(int kind, unsigned int value,
                                             unsigned int now, int animate) {
    if (kind == 0) return state.request(RecordSide::Generic, now, false);
    if (kind == 1) return state.trackDefault(value, now, animate != 0);
    if (kind == 2) return state.trackContext(value, now, animate != 0);
    return state.artwork(now, animate != 0);
}
extern "C" __declspec(dllexport) void rf_frame(unsigned int now, int visible, int *out) {
    RecordFrame f = state.frame(now, visible != 0);
    out[0] = static_cast<int>(f.side); out[1] = f.step; out[2] = f.moving;
}
extern "C" __declspec(dllexport) void rf_render(unsigned short *out, const unsigned short *art,
                                               int side, int step, int moving,
                                               int sine, int cosine, const unsigned short *p) {
    RecordPalette palette = {p[0], p[1], p[2], p[3], p[4]};
    RecordFrame frame = {static_cast<RecordSide>(side), static_cast<unsigned char>(step), moving != 0};
    renderRecordFrame(out, art, frame, sine, cosine, palette);
}
extern "C" __declspec(dllexport) unsigned int rf_state_bytes() { return sizeof(MediaRecordFlip); }
extern "C" __declspec(dllexport) int rf_reduced(unsigned short *out, unsigned int capacity,
                                                const unsigned short *p) {
    RecordPalette palette = {p[0], p[1], p[2], p[3], p[4]};
    return renderRecordGenericReduced(out, capacity, palette);
}

// Actual firmware activation/default functions under minimal LVGL/TX adapters.
// No SDK/CRT installation, transport payload or duplicate implementation.
constexpr int MEDIA_ART_SIZE = 112, MEDIA_ART_LV_BYTES = 25088;
constexpr int LV_IMG_CF_TRUE_COLOR_CHROMA_KEYED = 1;
struct { struct { int cf, w, h; } header; int data_size; const uint8_t *data; } media_art_descriptor;
static unsigned short media_art_buffers[2][112 * 112];
static uint8_t media_art_active_buffer = 0, media_art_receiving_buffer = 1;
static MediaRecordFlip media_record_flip;
static bool media_record_dirty = true, media_art_valid = true;
static unsigned int firmware_now = 0;
static uint32_t media_duration_seconds = 0, media_record_metadata_revision = 1, media_track_context_id = 101;
static bool media_art_receiving = true;
static struct { int aborts = 0; void abort() { ++aborts; } } media_art_v2;
static unsigned short *media_record_pixels = nullptr;
constexpr int MALLOC_CAP_INTERNAL = 1, MALLOC_CAP_8BIT = 2;
static int allocation_attempts = 0;
void *heap_caps_malloc(size_t bytes, int flags) {
    ++allocation_attempts;
    return bytes == 25088 && flags == 3 && allocation_attempts == 1 ? nullptr : media_art_buffers[0];
}
unsigned int millis() { return firmware_now; }
bool mediaRecordVisible() { return true; }
void refreshMediaUi() {}
void lv_img_cache_invalidate_src(void *) {}
void *recordClear(void *out, int value, size_t count) {
    volatile unsigned char *p = static_cast<volatile unsigned char *>(out);
    for (size_t i = 0; i < count; ++i) p[i] = static_cast<unsigned char>(value);
    return out;
}
struct { int writes = 0, last = 0; void println(const char *value) {
    ++writes; last = value[10] == 'N' ? 1 : value[11] == 'R' ? 2 : 3;
} } Serial;
static uint8_t media_tap_count = 0;
static uint32_t media_tap_deadline = 0;
static uint16_t touch_start_x = 1000, touch_start_y = 1000, touch_last_x = 1000, touch_last_y = 1000;
static bool touch_is_down = false, touch_started_in_focus_status = false;
static void *feature_overlay = nullptr;
constexpr int LV_OBJ_FLAG_HIDDEN = 1;
bool lv_obj_has_flag(void *, int) {return false;}
uint8_t min(uint8_t a, uint8_t b) {return a < b ? a : b;}
int abs(int a) {return a < 0 ? -a : a;}
static int touch_result = 0;
void toggleMediaCatMode() {touch_result = 4;}
void handleFocusStatusTap(uint32_t) {touch_result = 5;}
#define memset recordClear
#include "record_firmware_fixture.inc"
#undef memset

extern "C" __declspec(dllexport) void rf_fw_reset() {
    media_record_flip = MediaRecordFlip{};
    media_record_metadata_revision = 1; media_duration_seconds = 0; media_track_context_id = 101;
    media_art_v2.aborts = 0; media_art_receiving = true;
    media_record_flip.trackDefault(1, 0, false);
    media_record_flip.trackContext(101, 0, false);
    media_record_flip.artwork(0, false);
    media_art_active_buffer = 0; media_art_receiving_buffer = 1;
    Serial.writes = 0; firmware_now = 0;
    for (int i = 0; i < 112 * 112; ++i) {media_art_buffers[0][i] = 1111;media_art_buffers[1][i] = 2222;}
}
extern "C" __declspec(dllexport) void rf_fw_default() {
    ++media_record_metadata_revision;
    media_record_flip.trackDefault(media_record_metadata_revision, 0, true);
}
extern "C" __declspec(dllexport) void rf_fw_generic() {loadGenericVinyl();}
extern "C" __declspec(dllexport) void rf_fw_accept() {firmware_now=100;activateMediaArtwork(1, true);}
extern "C" __declspec(dllexport) int rf_fw_acks() {return Serial.writes;}
extern "C" __declspec(dllexport) int rf_fw_next_begin() {fwBeginFromSource();return media_art_receiving_buffer;}
extern "C" __declspec(dllexport) unsigned int rf_fw_sum(int slot) {
    unsigned int sum=0;for(int i=0;i<112*112;++i)sum+=media_art_buffers[slot][i];return sum;
}
extern "C" __declspec(dllexport) void rf_fw_overwrite_received() {
    for(int i=0;i<112*112;++i)media_art_buffers[media_art_receiving_buffer][i]=3333;
}
extern "C" __declspec(dllexport) void rf_fw_draw(unsigned short *out, unsigned int now) {
    RecordPalette p={0,1,2,3,4};
    renderRecordFrame(out,media_art_buffers[media_art_active_buffer],media_record_flip.frame(now,true),0,32767,p);
}
extern "C" __declspec(dllexport) int rf_oom_probe() {
    allocateMediaRecordPixels();allocateMediaRecordPixels();
    return media_record_pixels == nullptr ? allocation_attempts : -1;
}
extern "C" __declspec(dllexport) void rf_fw_duration(unsigned int duration) {fwDurationFromSource(duration);}
extern "C" __declspec(dllexport) void rf_fw_resync() {
    media_record_flip.trackDefault(media_record_metadata_revision, 50, true);
    updateMediaTrackContext(101, 50);
}
extern "C" __declspec(dllexport) void rf_fw_new_context() {updateMediaTrackContext(102, 60);}
extern "C" __declspec(dllexport) void rf_fw_frame(unsigned int now, int *out) {
    RecordFrame f=media_record_flip.frame(now,true);
    out[0]=static_cast<int>(f.side);out[1]=f.step;out[2]=f.moving;
}

extern "C" __declspec(dllexport) int rf_fw_track_context(const char *text, unsigned int length, unsigned int now) {
    MediaTrackContextValue parsed = parseMediaTrackContext(text, length);
    if (!parsed.valid) return 0;
    updateMediaTrackContext(parsed.value, now);
    return 1;
}
extern "C" __declspec(dllexport) int rf_fw_context_aborts() {return media_art_v2.aborts;}
extern "C" __declspec(dllexport) int rf_fw_receiving() {return media_art_receiving;}

extern "C" __declspec(dllexport) int rf_touch(int delta_x, int delta_y, int focus) {
    touch_start_x = touch_start_y = 1500;
    touch_last_x = 1500 + delta_x; touch_last_y = 1500 + delta_y;
    media_tap_count = 0; media_tap_deadline = 0; Serial.last = 0; touch_result = 0;
    touch_started_in_focus_status = focus != 0;
    mediaTouchFromSource(10);
    return touch_result ? touch_result : media_tap_count ? 3 : Serial.last;
}
extern "C" __declspec(dllexport) int rf_taps(int count, int down, int menu) {
    media_tap_count = 0; media_tap_deadline = 0; Serial.last = 0;
    for (int i = 0; i < count; ++i) queueMediaTap(10);
    touch_is_down = down != 0;
    feature_overlay = menu ? &touch_result : nullptr;
    serviceMediaTaps(1000);
    touch_is_down = false; feature_overlay = nullptr;
    return Serial.last;
}
