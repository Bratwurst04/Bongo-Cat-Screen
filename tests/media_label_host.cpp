// Actual current firmware functions are included below. These adapters count
// boundary calls; they do not emulate LVGL's animator, allocator or renderer.
typedef unsigned __int64 size_t;
typedef unsigned int uint32_t;
typedef unsigned short uint16_t;

extern "C" void *memcpy(void *out, const void *in, size_t count);
extern "C" void *memset(void *out, int value, size_t count);
#pragma function(memcpy, memset)
extern "C" void *memcpy(void *out, const void *in, size_t count) {
    volatile unsigned char *dst = static_cast<volatile unsigned char *>(out);
    const unsigned char *src = static_cast<const unsigned char *>(in);
    for (size_t i = 0; i < count; ++i) dst[i] = src[i];
    return out;
}
extern "C" void *memset(void *out, int value, size_t count) {
    volatile unsigned char *dst = static_cast<volatile unsigned char *>(out);
    for (size_t i = 0; i < count; ++i) dst[i] = static_cast<unsigned char>(value);
    return out;
}
int strcmp(const char *a, const char *b) {
    while (*a && *a == *b) { ++a; ++b; }
    return static_cast<unsigned char>(*a) - static_cast<unsigned char>(*b);
}
static void copy(char *out, const char *text) {
    size_t i = 0;
    while (text[i] && i < 767) { out[i] = text[i]; ++i; }
    out[i] = 0;
}
class String {
    char data[768];
public:
    String(const char *text = "") { copy(data, text); }
    String(const String &other) { copy(data, other.data); }
    String &operator=(const String &other) { copy(data, other.data); return *this; }
    const char *c_str() const { return data; }
    bool operator!=(const String &other) const { return strcmp(data, other.data) != 0; }
    bool operator==(const char *other) const { return strcmp(data, other) == 0; }
    bool operator!=(const char *other) const { return strcmp(data, other) != 0; }
    bool startsWith(const char *prefix) const {
        size_t i = 0;
        while (prefix[i]) { if (data[i] != prefix[i]) return false; ++i; }
        return true;
    }
    int indexOf(char value) const { for (int i = 0; data[i]; ++i) if (data[i] == value) return i; return -1; }
    String substring(int start, int end = 767) const {
        String result; int i = 0;
        while (data[i] && i < start) ++i;
        int n = 0;
        while (data[i] && i < end && n < 767) result.data[n++] = data[i++];
        result.data[n] = 0;
        return result;
    }
    unsigned int toInt() const {
        unsigned int value = 0;
        for (int i = 0; data[i] >= '0' && data[i] <= '9'; ++i) value = value * 10 + data[i] - '0';
        return value;
    }
};
int snprintf(char *out, size_t, const char *, unsigned long minutes, unsigned long seconds) {
    char digits[12]; int n = 0, pos = 0;
    do { digits[n++] = static_cast<char>('0' + minutes % 10); minutes /= 10; } while (minutes);
    while (n) out[pos++] = digits[--n];
    out[pos++] = ':'; out[pos++] = static_cast<char>('0' + seconds / 10);
    out[pos++] = static_cast<char>('0' + seconds % 10); out[pos] = 0;
    return pos;
}
struct lv_color_t { unsigned int full; };
struct lv_obj_t { char text[768]; int writes; unsigned int background, border; int value; bool hidden; };
static lv_obj_t objects[13];
static int color_writes, total_writes;
static lv_obj_t *media_source_label = &objects[0], *media_title_label = &objects[1], *media_artist_label = &objects[2];
static lv_obj_t *media_playback_status_label = &objects[3], *media_play_label = &objects[4];
static lv_obj_t *media_elapsed_label = &objects[5], *media_duration_label = &objects[6], *media_state_label = &objects[7];
static lv_obj_t *media_art_box = &objects[8], *media_art_image = &objects[9], *media_cat_canvas = &objects[10];
static lv_obj_t *media_progress_bar = &objects[11], *media_screen = &objects[12];
static String media_source, media_title, media_artist;
static bool media_is_playing, media_has_track, media_cat_mode, media_art_valid, media_art_receiving;
static uint32_t media_position_seconds, media_duration_seconds, media_position_anchor_ms, media_record_metadata_revision;
static struct { void abort() {} } media_art_v2;
enum { LV_ANIM_OFF, LV_ALIGN_TOP_RIGHT, LV_OBJ_FLAG_HIDDEN };
#define LV_SYMBOL_PAUSE "[PAUSE]"
#define LV_SYMBOL_PLAY "[PLAY]"
#define LV_SYMBOL_AUDIO "[AUDIO]"
const char *lv_label_get_text(lv_obj_t *obj) { return obj->text; }
void lv_label_set_text(lv_obj_t *obj, const char *text) { copy(obj->text, text); ++obj->writes; ++total_writes; }
void lv_bar_set_value(lv_obj_t *obj, int value, int) { obj->value = value; }
void lv_obj_align(lv_obj_t *, int, int, int) {}
lv_color_t lv_color_white() { return {0xFFFFFF}; }
lv_color_t lv_color_hex(unsigned int value) { return {value}; }
lv_color_t lv_obj_get_style_bg_color(lv_obj_t *obj, int) { return {obj->background}; }
lv_color_t lv_obj_get_style_border_color(lv_obj_t *obj, int) { return {obj->border}; }
void lv_obj_set_style_bg_color(lv_obj_t *obj, lv_color_t value, int) { obj->background = value.full; ++color_writes; }
void lv_obj_set_style_border_color(lv_obj_t *obj, lv_color_t value, int) { obj->border = value.full; ++color_writes; }
void lv_obj_add_flag(lv_obj_t *obj, int) { obj->hidden = true; }
void lv_obj_clear_flag(lv_obj_t *obj, int) { obj->hidden = false; }
void renderMediaCat() {}
void loadGenericVinyl() { media_art_valid = false; }
#include "media_label_fixture.inc"

extern "C" __declspec(dllexport) void mt_reset() {
    memset(objects, 0, sizeof(objects)); color_writes = total_writes = 0;
    media_source = String("WINDOWS"); media_title = String("Nothing playing"); media_artist = String("Start Spotify on this PC");
    media_is_playing = media_has_track = media_cat_mode = media_art_valid = media_art_receiving = false;
    media_position_seconds = media_duration_seconds = media_position_anchor_ms = 0;
    media_record_metadata_revision = 0;
}
extern "C" __declspec(dllexport) void mt_apply(const char *command, unsigned int now) { applyMediaCommand(String(command), now); }
extern "C" __declspec(dllexport) const char *mt_text(int index) { return objects[index].text; }
extern "C" __declspec(dllexport) int mt_writes(int index) { return objects[index].writes; }
extern "C" __declspec(dllexport) int mt_total() { return total_writes; }
extern "C" __declspec(dllexport) int mt_colors() { return color_writes; }
extern "C" __declspec(dllexport) unsigned int mt_anchor() { return media_position_anchor_ms; }
extern "C" __declspec(dllexport) unsigned int mt_revision() { return media_record_metadata_revision; }
extern "C" __declspec(dllexport) void mt_mode(int cat, int art) { media_cat_mode = cat != 0; media_art_valid = art != 0; refreshMediaUi(); }
