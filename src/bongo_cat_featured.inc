#include <lvgl.h>
#include <TFT_eSPI.h>
#include <WiFi.h>
#include <EEPROM.h>
#include <esp_freertos_hooks.h>
#include "Free_Fonts.h"
#include "animations_sprites.h"

// Display settings
#define SCREEN_WIDTH 240
#define SCREEN_HEIGHT 320
#define DRAW_BUFFER_ROWS 40
#define TOUCH_PRESSURE_THRESHOLD 350
#define TOUCH_LONG_PRESS_MS 650
#define TOUCH_BONK_DURATION_MS 1400
#define MEDIA_MULTI_TAP_WINDOW_MS 320
#define MEDIA_ART_SIZE 112
#define MEDIA_ART_LV_BYTES (MEDIA_ART_SIZE * MEDIA_ART_SIZE * 2)
#define MEDIA_ART_RGB_BYTES (MEDIA_ART_SIZE * MEDIA_ART_SIZE * 3)
#define MEDIA_SWIPE_THRESHOLD 420
#define MEDIA_VINYL_FRAME_MS 60
#define MEDIA_VINYL_ANGLE_STEP 18
#define MEDIA_CAT_FRAME_MS 450
#define MEDIA_CAT_ZOOM 640
// The existing raw touch X axis increases from top to bottom; raw Y runs
// across the display. Only the menu uses approximate absolute positions.
#define TOUCH_RAW_TOP 200
#define TOUCH_RAW_BOTTOM 3900
#define TOUCH_RAW_SIDE_MIN 200
#define TOUCH_RAW_SIDE_MAX 3900

// Configuration settings structure
struct BongoCatSettings {
    bool show_cpu = true;
    bool show_ram = true;
    bool show_wpm = true;
    bool show_time = true;
    bool time_format_24h = true;
    int sleep_timeout_minutes = 5;
    float animation_sensitivity = 1.0;
    uint32_t checksum = 0;  // For validation
};

// EEPROM settings
#define SETTINGS_ADDRESS 0
#define SETTINGS_SIZE sizeof(BongoCatSettings)
#define EEPROM_SIZE 512  // ESP32 EEPROM size

// Global settings instance
BongoCatSettings settings;

TFT_eSPI tft = TFT_eSPI();

// LVGL display buffer
static lv_disp_draw_buf_t draw_buf;
static lv_color_t buf[SCREEN_WIDTH * DRAW_BUFFER_ROWS];

// Animation system with sprites
sprite_manager_t sprite_manager;
lv_obj_t * cat_canvas = NULL;
uint32_t last_frame_time = 0;
bool animation_paused = false;

// Enhanced animation control
bool python_control_mode = true;  // Python controls idle progression
uint32_t last_command_time = 0;   // Track when last command received
#define TYPING_TIMEOUT_MS 2000    // Stop typing animation after 2 seconds of no commands
#define PYTHON_TIMEOUT_MS 5000    // Fall back to auto mode after 5 seconds

// Simplified animation performance (removed aggressive frame limiting)
uint32_t frame_skip_counter = 0;

// Cat positioning (restored to original working method)
#define CAT_SIZE 64   // Base sprite size

// System stats display
lv_obj_t * screen = NULL;
lv_obj_t * cpu_label = NULL;
lv_obj_t * ram_label = NULL;
lv_obj_t * wpm_label = NULL;
lv_obj_t * time_label = NULL;

// One menu on LVGL's top layer stays above either underlying screen.
lv_obj_t * feature_overlay = NULL;
lv_obj_t * feature_overlay_label = NULL;
lv_obj_t * feature_overlay_bongo_button = NULL;
lv_obj_t * feature_overlay_player_button = NULL;
lv_obj_t * feature_overlay_bongo_label = NULL;
lv_obj_t * feature_overlay_player_label = NULL;
lv_obj_t * feature_overlay_stats_label = NULL;
lv_obj_t * feature_overlay_media_label = NULL;
lv_obj_t * feature_overlay_title_label = NULL;
lv_obj_t * feature_overlay_hint_label = NULL;
lv_obj_t * feature_overlay_count_label = NULL;
bool touch_is_down = false;
bool touch_long_press_fired = false;
bool touch_started_in_menu = false;
bool touch_bonk_active = false;
uint32_t touch_down_time = 0;
uint32_t touch_bonk_until = 0;
uint32_t overlay_hide_time = 0;
uint32_t touch_bonk_count = 0;
uint16_t touch_start_x = 0;
uint16_t touch_start_y = 0;
uint16_t touch_last_x = 0;
uint16_t touch_last_y = 0;

// Bongo DJ / Windows media screen. Artwork arrives as RGB888 so the ESP32 can
// convert through LVGL itself without any controller-specific byte ordering.
lv_obj_t * media_screen = NULL;
lv_obj_t * media_art_box = NULL;
lv_obj_t * media_art_image = NULL;
lv_obj_t * media_source_label = NULL;
lv_obj_t * media_playback_status_label = NULL;
lv_obj_t * media_gesture_hint_label = NULL;
lv_obj_t * media_title_label = NULL;
lv_obj_t * media_artist_label = NULL;
lv_obj_t * media_state_label = NULL;
lv_obj_t * media_progress_bar = NULL;
lv_obj_t * media_elapsed_label = NULL;
lv_obj_t * media_duration_label = NULL;
lv_obj_t * media_play_label = NULL;
lv_obj_t * media_cat_canvas = NULL;
static lv_color_t media_cat_canvas_buffer[CAT_SIZE * CAT_SIZE];
static lv_color_t media_art_buffers[2][MEDIA_ART_SIZE * MEDIA_ART_SIZE];
static lv_img_dsc_t media_art_descriptor;
uint8_t media_art_active_buffer = 0;
uint8_t media_art_receiving_buffer = 1;
bool media_art_receiving = false;
size_t media_art_expected = 0;
size_t media_art_received = 0;
size_t media_art_pixels_received = 0;
uint8_t media_art_rgb_triplet[3] = {0, 0, 0};
uint8_t media_art_rgb_triplet_used = 0;
bool media_art_valid = false;
bool spotify_screen_active = false;
bool media_is_playing = false;
bool media_has_track = false;
uint16_t media_vinyl_angle = 0;
uint32_t media_vinyl_last_frame = 0;
String media_source = "WINDOWS";
String media_title = "Nothing playing";
String media_artist = "Start Spotify on this PC";
uint32_t media_position_seconds = 0;
uint32_t media_duration_seconds = 0;
uint32_t media_position_anchor_ms = 0;
uint8_t media_tap_count = 0;
uint32_t media_tap_deadline = 0;
bool media_cat_mode = false;
uint8_t media_cat_left_note = 0;
uint8_t media_cat_right_note = 0;
uint8_t media_cat_effect = 0;

// Optional, deliberately low-overhead CPU activity estimate. The callbacks run
// at most once per FreeRTOS tick and are ignored until diagnostics enables it.
volatile bool cpu_diagnostics_enabled = false;
volatile uint32_t cpu_idle_ticks_core0 = 0;
volatile uint32_t cpu_idle_ticks_core1 = 0;
bool cpu_diagnostics_hooks_ready = false;
uint32_t cpu_diagnostics_last_time = 0;
uint32_t cpu_diagnostics_last_idle0 = 0;
uint32_t cpu_diagnostics_last_idle1 = 0;
int cpu_diagnostics_estimate = -1;
uint32_t cpu_diagnostics_sample_ms = 0;

bool cpuIdleHookCore0();
bool cpuIdleHookCore1();
void setCpuDiagnostics(bool enabled, uint32_t current_time);
uint32_t media_cat_last_frame = 0;

// Stats data
int cpu_usage = 0;
int ram_usage = 0;
int wpm_speed = 0;
String current_time_str = "00:00";
bool time_initialized = false;  // Track if we've received time from Python

void refreshFeatureOverlay() {
    if (!feature_overlay || lv_obj_has_flag(feature_overlay, LV_OBJ_FLAG_HIDDEN)) return;

    bool player_active = spotify_screen_active;
    lv_label_set_text(feature_overlay_bongo_label,
                      player_active ? "BONGO" : "BONGO  AKTIV");
    lv_label_set_text(feature_overlay_player_label,
                      player_active ? "SPELARE  AKTIV" : "SPELARE");
    for (lv_obj_t *button : {feature_overlay_bongo_button,
                             feature_overlay_player_button}) {
        bool active = button == (player_active ? feature_overlay_player_button
                                               : feature_overlay_bongo_button);
        lv_obj_set_style_bg_color(button,
                                  lv_color_hex(active ? 0x1B3025 : 0x171A1F), 0);
        lv_obj_set_style_border_color(button,
                                      lv_color_hex(active ? 0x1ED760 : 0x4C555D), 0);
        lv_obj_set_style_border_width(button, active ? 2 : 1, 0);
    }
    lv_obj_set_style_text_color(feature_overlay_bongo_label,
                                player_active ? lv_color_white() : lv_color_hex(0x1ED760), 0);
    lv_obj_set_style_text_color(feature_overlay_player_label,
                                player_active ? lv_color_hex(0x1ED760) : lv_color_white(), 0);

    char cpu[18] = "", ram[18] = "", wpm[18] = "", time[20] = "";
    if (settings.show_cpu) snprintf(cpu, sizeof(cpu), "CPU %d%%", cpu_usage);
    if (settings.show_ram) snprintf(ram, sizeof(ram), "RAM %d%%", ram_usage);
    if (settings.show_wpm) snprintf(wpm, sizeof(wpm), "WPM %d", wpm_speed);
    if (settings.show_time) {
        snprintf(time, sizeof(time), "TIME %s",
                 time_label ? lv_label_get_text(time_label) : current_time_str.c_str());
    }

    char row1[40], row2[44], stats[88];
    snprintf(row1, sizeof(row1), "%s%s%s", cpu, cpu[0] && ram[0] ? "   " : "", ram);
    snprintf(row2, sizeof(row2), "%s%s%s", wpm, wpm[0] && time[0] ? "   " : "", time);
    snprintf(stats, sizeof(stats), "%s%s%s", row1,
             row1[0] && row2[0] ? "\n" : "", row2);
    lv_label_set_text(feature_overlay_stats_label,
                      stats[0] ? stats : "STATS HIDDEN");
    lv_label_set_text_fmt(feature_overlay_media_label, "MEDIA  %s",
                          media_is_playing ? "PLAYING" :
                          (media_has_track ? "PAUSED" : "NO MEDIA"));
    lv_label_set_text(feature_overlay_title_label,
                      media_has_track ? media_title.c_str() : "Nothing playing");
}

// Function to flush the display buffer
void my_disp_flush(lv_disp_drv_t *disp, const lv_area_t *area, lv_color_t *color_p) {
    uint32_t w = (area->x2 - area->x1 + 1);
    uint32_t h = (area->y2 - area->y1 + 1);

    tft.startWrite();
    tft.setAddrWindow(area->x1, area->y1, w, h);
    // LV_COLOR_16_SWAP is enabled, so the LVGL buffer is already in the byte
    // order expected on the SPI wire. Asking TFT_eSPI to swap it again turns
    // antialiased greys into purple/rainbow artefacts.
    tft.pushColors((uint16_t*)&color_p->full, w * h, false);
    tft.endWrite();

    lv_disp_flush_ready(disp);
}

// Update system stats display
void updateSystemStats(int cpu, int ram, int wpm) {
    cpu_usage = cpu;
    ram_usage = ram;
    wpm_speed = wpm;
    
    if (cpu_label) {
        lv_label_set_text_fmt(cpu_label, "CPU: %d%%", cpu);
    }
    if (ram_label) {
        lv_label_set_text_fmt(ram_label, "RAM: %d%%", ram);
    }
    if (wpm_label) {
        lv_label_set_text_fmt(wpm_label, "WPM: %d", wpm);
    }
}

// Update time display  
void updateTimeDisplay() {
    if (time_label && current_time_str.length() > 0) {
        String display_time = current_time_str;
        
        // Convert to 12-hour format if needed
        if (!settings.time_format_24h && current_time_str.length() == 5) {
            int hour = current_time_str.substring(0, 2).toInt();
            String minute = current_time_str.substring(3, 5);
            String ampm = (hour >= 12) ? "PM" : "AM";
            
            if (hour == 0) hour = 12;      // 00:xx -> 12:xx AM
            else if (hour > 12) hour -= 12; // 13:xx -> 1:xx PM
            
            display_time = String(hour) + ":" + minute + " " + ampm;
        }
        
        lv_label_set_text(time_label, display_time.c_str());
        
        // Debug output for time updates
        if (!time_initialized) {
            Serial.print("🕐 Time initialized: ");
            Serial.println(display_time);
            time_initialized = true;
        }
    }
}

// Settings management functions
uint32_t calculateChecksum(const BongoCatSettings* s) {
    // Simple checksum calculation (excluding checksum field itself)
    uint32_t sum = 0;
    const uint8_t* data = (const uint8_t*)s;
    size_t size = sizeof(BongoCatSettings) - sizeof(uint32_t); // Exclude checksum field
    
    for (size_t i = 0; i < size; i++) {
        sum += data[i];
    }
    return sum;
}

bool validateSettings(const BongoCatSettings* s) {
    // Check if settings are within valid ranges
    if (s->sleep_timeout_minutes < 1 || s->sleep_timeout_minutes > 60) return false;
    if (s->animation_sensitivity < 0.1 || s->animation_sensitivity > 5.0) return false;
    
    // Check if checksum matches
    uint32_t expected_checksum = calculateChecksum(s);
    return (s->checksum == expected_checksum);
}

void saveSettings() {
    settings.checksum = calculateChecksum(&settings);
    EEPROM.put(SETTINGS_ADDRESS, settings);
    EEPROM.commit();
    Serial.println("💾 Settings saved to EEPROM");
}

void loadSettings() {
    BongoCatSettings temp_settings;
    EEPROM.get(SETTINGS_ADDRESS, temp_settings);
    
    if (validateSettings(&temp_settings)) {
        settings = temp_settings;
        Serial.println("📂 Settings loaded from EEPROM");
        // Note: updateDisplayVisibility() will be called after UI creation
    } else {
        Serial.println("⚠️ Invalid settings in EEPROM, using defaults");
        resetSettings();
    }
}

void resetSettings() {
    // Reset to default values
    settings.show_cpu = true;
    settings.show_ram = true;
    settings.show_wpm = true;
    settings.show_time = true;
    settings.time_format_24h = true;
    settings.sleep_timeout_minutes = 5;
    settings.animation_sensitivity = 1.0;
    settings.checksum = calculateChecksum(&settings);
    
    Serial.println("🔄 Settings reset to factory defaults");
    // Note: updateDisplayVisibility() will be called after UI creation if needed
}

void updateDisplayVisibility() {
    // Show/hide labels based on settings (only if UI is created)
    if (cpu_label) {
        if (settings.show_cpu) {
            lv_obj_clear_flag(cpu_label, LV_OBJ_FLAG_HIDDEN);
        } else {
            lv_obj_add_flag(cpu_label, LV_OBJ_FLAG_HIDDEN);
        }
        Serial.println("🖥️ CPU visibility updated: " + String(settings.show_cpu ? "ON" : "OFF"));
    }
    
    if (ram_label) {
        if (settings.show_ram) {
            lv_obj_clear_flag(ram_label, LV_OBJ_FLAG_HIDDEN);
        } else {
            lv_obj_add_flag(ram_label, LV_OBJ_FLAG_HIDDEN);
        }
        Serial.println("💾 RAM visibility updated: " + String(settings.show_ram ? "ON" : "OFF"));
    }
    
    if (wpm_label) {
        if (settings.show_wpm) {
            lv_obj_clear_flag(wpm_label, LV_OBJ_FLAG_HIDDEN);
        } else {
            lv_obj_add_flag(wpm_label, LV_OBJ_FLAG_HIDDEN);
        }
        Serial.println("⌨️ WPM visibility updated: " + String(settings.show_wpm ? "ON" : "OFF"));
    }
    
    if (time_label) {
        if (settings.show_time) {
            lv_obj_clear_flag(time_label, LV_OBJ_FLAG_HIDDEN);
        } else {
            lv_obj_add_flag(time_label, LV_OBJ_FLAG_HIDDEN);
        }
        Serial.println("🕐 Time visibility updated: " + String(settings.show_time ? "ON" : "OFF"));
    }
}

String formatMediaTime(uint32_t total_seconds) {
    char value[12];
    uint32_t minutes = total_seconds / 60;
    uint32_t seconds = total_seconds % 60;
    snprintf(value, sizeof(value), "%lu:%02lu",
             (unsigned long)minutes, (unsigned long)seconds);
    return String(value);
}

void refreshMediaProgressUi() {
    if (!media_progress_bar) return;
    int progress = 0;
    if (media_duration_seconds > 0) {
        uint32_t scaled_progress =
            (media_position_seconds * (uint32_t)1000) / media_duration_seconds;
        progress = (int)(scaled_progress > 1000 ? 1000 : scaled_progress);
    }
    lv_bar_set_value(media_progress_bar, progress, LV_ANIM_OFF);
    lv_label_set_text(media_elapsed_label,
                      formatMediaTime(media_position_seconds).c_str());
    lv_label_set_text(media_duration_label,
                      formatMediaTime(media_duration_seconds).c_str());
}

void drawDjSprite(const DjSprite &sprite) {
    if (!media_cat_canvas) return;
    for (uint16_t index = 0; index < sprite.pixel_count; index++) {
        const DjPixel &pixel = sprite.pixels[index];
        lv_canvas_set_px(media_cat_canvas, pixel.x, pixel.y,
                         lv_color_make(pixel.r, pixel.g, pixel.b));
    }
}

void renderMediaCat() {
    if (!media_cat_canvas) return;

    // This is deliberately independent from the normal Bongo sprite manager:
    // entering DJ view never changes typing, idle, blink, or touch state.
    lv_canvas_fill_bg(media_cat_canvas, lv_color_white(), LV_OPA_COVER);
    lv_draw_img_dsc_t img_dsc;
    lv_draw_img_dsc_init(&img_dsc);
    for (const lv_img_dsc_t *sprite : {&standardbody1, &stock_face}) {
        lv_canvas_draw_img(media_cat_canvas, 0, 0, sprite, &img_dsc);
    }

    drawDjSprite(dj_glasses);
    drawDjSprite(dj_mixer_board);
    lv_canvas_draw_img(media_cat_canvas, 0, 0, &twopawsup, &img_dsc);

    // Each sparse layer has its own local variant; zero leaves it out.
    if (media_cat_effect == 1) drawDjSprite(dj_effect_r1);
    if (media_cat_effect == 2) drawDjSprite(dj_effect_r2);
    if (media_cat_left_note == 1) drawDjSprite(dj_notes_l1);
    if (media_cat_left_note == 2) drawDjSprite(dj_notes_l2);
    if (media_cat_right_note == 1) drawDjSprite(dj_notes_r1);
    if (media_cat_right_note == 2) drawDjSprite(dj_notes_r2);
    lv_obj_invalidate(media_cat_canvas);
}

void refreshMediaUi() {
    if (!media_screen) return;

    lv_label_set_text(media_source_label, media_source.c_str());
    lv_obj_align(media_source_label, LV_ALIGN_TOP_RIGHT, -10, 4);
    lv_label_set_text(media_title_label, media_title.c_str());
    lv_label_set_text(media_artist_label, media_artist.c_str());
    if (media_playback_status_label) {
        lv_label_set_text(media_playback_status_label,
                          media_is_playing ? "PLAYING" :
                          (media_has_track ? "PAUSED" : "NO MEDIA"));
    }
    if (media_gesture_hint_label) {
        lv_label_set_text(media_gesture_hint_label,
                          media_source == "SPOTIFY API" ? "SWIPE DOWN  DJ CAT" :
                          "TAP  PLAY/PAUSE\nSWIPE  PREV/NEXT  |  DOWN  DJ CAT");
    }
    if (media_play_label) {
        lv_label_set_text(media_play_label,
                          media_is_playing ? LV_SYMBOL_PAUSE : LV_SYMBOL_PLAY);
    }
    refreshMediaProgressUi();

    // The circular viewport is white only for DJ mode. Restore its original
    // dark fill and border before showing artwork or the generic vinyl.
    lv_obj_set_style_bg_color(media_art_box,
                              media_cat_mode ? lv_color_white() : lv_color_hex(0x080A0C), 0);
    lv_obj_set_style_border_color(media_art_box,
                                  media_cat_mode ? lv_color_white() : lv_color_hex(0x252A30), 0);

    if (media_cat_mode) {
        lv_obj_add_flag(media_state_label, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(media_art_image, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(media_cat_canvas, LV_OBJ_FLAG_HIDDEN);
        renderMediaCat();
    } else if (media_art_valid) {
        lv_obj_add_flag(media_state_label, LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(media_art_image, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(media_cat_canvas, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_clear_flag(media_state_label, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(media_art_image, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(media_cat_canvas, LV_OBJ_FLAG_HIDDEN);
        lv_label_set_text(media_state_label, LV_SYMBOL_AUDIO "\nVINYL");
    }
}

void activateMediaArtwork(uint8_t buffer_index, bool acknowledge) {
    memset(&media_art_descriptor, 0, sizeof(media_art_descriptor));
    media_art_active_buffer = buffer_index;
    media_art_descriptor.header.cf = LV_IMG_CF_TRUE_COLOR_CHROMA_KEYED;
    media_art_descriptor.header.w = MEDIA_ART_SIZE;
    media_art_descriptor.header.h = MEDIA_ART_SIZE;
    media_art_descriptor.data_size = MEDIA_ART_LV_BYTES;
    media_art_descriptor.data = reinterpret_cast<const uint8_t *>(
        media_art_buffers[media_art_active_buffer]);
    lv_img_cache_invalidate_src(&media_art_descriptor);
    lv_img_set_src(media_art_image, &media_art_descriptor);
    lv_img_set_pivot(media_art_image, MEDIA_ART_SIZE / 2, MEDIA_ART_SIZE / 2);
    lv_img_set_zoom(media_art_image, 384);
    media_vinyl_angle = 0;
    lv_img_set_angle(media_art_image, media_vinyl_angle);
    lv_img_set_antialias(media_art_image, false);
    lv_obj_center(media_art_image);
    media_art_valid = true;
    refreshMediaUi();
    if (acknowledge) Serial.println("MEDIA_ART_OK");
}

void loadGenericVinyl() {
    uint8_t buffer_index = 1 - media_art_active_buffer;
    lv_color_t chroma = lv_color_make(0, 255, 0);
    lv_color_t record = lv_color_hex(0x111318);
    lv_color_t groove = lv_color_hex(0x343941);
    lv_color_t label = lv_color_hex(0x1ED760);
    lv_color_t spindle = lv_color_hex(0xE8EBEE);
    const int center = MEDIA_ART_SIZE / 2;

    for (int y = 0; y < MEDIA_ART_SIZE; y++) {
        for (int x = 0; x < MEDIA_ART_SIZE; x++) {
            int dx = x - center;
            int dy = y - center;
            int radius2 = dx * dx + dy * dy;
            lv_color_t pixel = chroma;
            if (radius2 <= 46 * 46) pixel = record;
            if ((radius2 >= 38 * 38 && radius2 <= 39 * 39) ||
                (radius2 >= 31 * 31 && radius2 <= 32 * 32)) pixel = groove;
            if (radius2 <= 24 * 24) pixel = label;
            if (radius2 <= 5 * 5) pixel = spindle;
            if (radius2 <= 2 * 2) pixel = record;
            // An off-centre marker makes the rotation clearly visible.
            int marker_dx = x - center;
            int marker_dy = y - (center - 39);
            if (marker_dx * marker_dx + marker_dy * marker_dy <= 3 * 3) {
                pixel = label;
            }
            media_art_buffers[buffer_index][y * MEDIA_ART_SIZE + x] = pixel;
        }
    }
    activateMediaArtwork(buffer_index, false);
}

void finishMediaArtwork() {
    activateMediaArtwork(media_art_receiving_buffer, true);
}

bool serviceMediaArtworkReceive() {
    if (!media_art_receiving) return false;

    size_t available = Serial.available();
    if (available > 0 && media_art_received < media_art_expected) {
        size_t remaining = media_art_expected - media_art_received;
        uint8_t incoming[192];
        size_t amount = min(min(available, remaining), sizeof(incoming));
        int bytes_read = Serial.read(incoming, amount);
        if (bytes_read > 0) {
            media_art_received += (size_t)bytes_read;
            for (int index = 0; index < bytes_read; index++) {
                media_art_rgb_triplet[media_art_rgb_triplet_used++] = incoming[index];
                if (media_art_rgb_triplet_used == 3) {
                    if (media_art_pixels_received < MEDIA_ART_SIZE * MEDIA_ART_SIZE) {
                        media_art_buffers[media_art_receiving_buffer]
                                         [media_art_pixels_received++] = lv_color_make(
                            media_art_rgb_triplet[0],
                            media_art_rgb_triplet[1],
                            media_art_rgb_triplet[2]);
                    }
                    media_art_rgb_triplet_used = 0;
                }
            }
        }
    }

    if (media_art_received >= media_art_expected) {
        media_art_receiving = false;
        if (media_art_pixels_received == MEDIA_ART_SIZE * MEDIA_ART_SIZE &&
            media_art_rgb_triplet_used == 0) {
            finishMediaArtwork();
        } else {
            media_art_valid = false;
            Serial.println("MEDIA_ART_ERROR");
        }
    }
    return true;
}

void updateMediaVinyl(uint32_t current_time) {
    if (!spotify_screen_active || media_cat_mode || !media_art_valid || !media_is_playing ||
        !media_art_image) {
        return;
    }
    if (current_time - media_vinyl_last_frame < MEDIA_VINYL_FRAME_MS) return;

    media_vinyl_last_frame = current_time;
    media_vinyl_angle = (media_vinyl_angle + MEDIA_VINYL_ANGLE_STEP) % 3600;
    // Invalidate the entire circular viewport, not only LVGL's calculated
    // transformed rectangle. This prevents stale halves from adjacent frames.
    lv_obj_invalidate(media_art_box);
    lv_img_set_angle(media_art_image, media_vinyl_angle);
    lv_obj_invalidate(media_art_box);
}

void updateMediaCat(uint32_t current_time) {
    if (!spotify_screen_active || !media_cat_mode || !media_cat_canvas) return;
    if (!media_is_playing) return;
    if (current_time - media_cat_last_frame < MEDIA_CAT_FRAME_MS) return;
    media_cat_last_frame = current_time;
    uint8_t left = random(3);
    uint8_t right = random(3);
    uint8_t effect = random(3);
    if (left == media_cat_left_note && right == media_cat_right_note &&
        effect == media_cat_effect) {
        // Avoid an unchanged frame while keeping all three choices independent.
        switch (random(3)) {
            case 0: left = (left + 1 + random(2)) % 3; break;
            case 1: right = (right + 1 + random(2)) % 3; break;
            default: effect = (effect + 1 + random(2)) % 3; break;
        }
    }
    media_cat_left_note = left;
    media_cat_right_note = right;
    media_cat_effect = effect;
    renderMediaCat();
}

void toggleMediaCatMode() {
    media_cat_mode = !media_cat_mode;
    media_cat_last_frame = 0;
    media_cat_left_note = 0;
    media_cat_right_note = 0;
    media_cat_effect = 0;
    refreshMediaUi();
}

void updateMediaProgressClock(uint32_t current_time) {
    if (!media_is_playing || media_duration_seconds == 0) {
        media_position_anchor_ms = current_time;
        return;
    }
    uint32_t elapsed = current_time - media_position_anchor_ms;
    if (elapsed < 1000) return;
    uint32_t seconds = elapsed / 1000;
    media_position_anchor_ms += seconds * 1000;
    media_position_seconds = min(media_position_seconds + seconds,
                                 media_duration_seconds);
    refreshMediaProgressUi();
}

void queueMediaTap(uint32_t current_time) {
    media_tap_count = min((uint8_t)3, (uint8_t)(media_tap_count + 1));
    media_tap_deadline = current_time + MEDIA_MULTI_TAP_WINDOW_MS;
}

void serviceMediaTaps(uint32_t current_time) {
    // A press can become a long press. Do not dispatch a queued tap while the
    // finger is still down, and never dispatch one underneath the menu.
    if (touch_is_down ||
        (feature_overlay && !lv_obj_has_flag(feature_overlay, LV_OBJ_FLAG_HIDDEN))) return;
    if (!media_tap_count || current_time < media_tap_deadline) return;
    if (media_tap_count == 1) {
        Serial.println("MEDIA_CMD:PLAY_PAUSE");
    } else if (media_tap_count == 2) {
        Serial.println("MEDIA_CMD:NEXT");
    } else {
        Serial.println("MEDIA_CMD:PREVIOUS");
    }
    media_tap_count = 0;
    media_tap_deadline = 0;
}

// Handle serial commands from Python script
void handleSerialCommands() {
    if (serviceMediaArtworkReceive()) return;
    if (Serial.available()) {
        String command = Serial.readStringUntil('\n');
        command.trim();
        
        uint32_t current_time = millis();
        last_command_time = current_time;  // Update command timestamp
        python_control_mode = true;        // Ensure Python control is active
        
        if (command.startsWith("MEDIA_SOURCE:")) {
            media_source = command.substring(13);
            refreshMediaUi();
        } else if (command.startsWith("MEDIA_TITLE:")) {
            media_title = command.substring(12);
            refreshMediaUi();
        } else if (command.startsWith("MEDIA_ARTIST:")) {
            media_artist = command.substring(13);
            refreshMediaUi();
        } else if (command.startsWith("MEDIA_STATE:")) {
            String state = command.substring(12);
            media_is_playing = state == "PLAYING";
            media_has_track = state != "NONE";
            media_position_anchor_ms = current_time;
            if (state == "NONE") loadGenericVinyl();
            refreshMediaUi();
        } else if (command.startsWith("MEDIA_TIME:")) {
            String timing = command.substring(11);
            int separator = timing.indexOf(':');
            if (separator > 0) {
                media_position_seconds = timing.substring(0, separator).toInt();
                media_duration_seconds = timing.substring(separator + 1).toInt();
                media_position_anchor_ms = current_time;
                refreshMediaProgressUi();
            }
        } else if (command.startsWith("MEDIA_ART_RGB:")) {
            int final_separator = command.lastIndexOf(':');
            size_t incoming_size = command.substring(final_separator + 1).toInt();
            if (incoming_size == MEDIA_ART_RGB_BYTES) {
                media_art_receiving_buffer = 1 - media_art_active_buffer;
                media_art_expected = incoming_size;
                media_art_received = 0;
                media_art_pixels_received = 0;
                media_art_rgb_triplet_used = 0;
                media_art_receiving = true;
            }
        } else if (command == "MEDIA_ART_DEFAULT") {
            loadGenericVinyl();
        } else if (command.startsWith("SPEED:")) {
            cancelTouchBonk();
            // Handle speed commands with enhanced logic  
            String speed_str = command.substring(6);
            uint16_t speed = speed_str.toInt();
            
            // Updated thresholds to match Python script (2024 industry standards)
            // Research shows: Average 40-45 WPM, Slow <20, Good 50-60, Professional 70+
            animation_state_t new_state = sprite_manager.current_state;
            
            if (speed == 0) {
                // Explicit stop command
                sprite_manager_set_state(&sprite_manager, ANIM_STATE_IDLE_STAGE1, current_time);
            } else if (speed < 80) {        // Slow threshold: <20 WPM -> speed 80+
                new_state = ANIM_STATE_TYPING_SLOW;
            } else if (speed < 150) {       // Normal threshold: 20-40 WPM -> speed 80-150
                new_state = ANIM_STATE_TYPING_NORMAL;
            } else {                        // Fast threshold: 40+ WPM -> speed 150+
                new_state = ANIM_STATE_TYPING_FAST;
            }
            
            // Always refresh state to prevent stuck animations (even if same state)
            sprite_manager_set_state(&sprite_manager, new_state, current_time);
            Serial.println("🔄 Animation state refreshed");
            
            // Check for significant speed changes that might cause stuck paws
            uint16_t old_speed = sprite_manager.animation_speed_ms;
            sprite_manager.animation_speed_ms = speed;
            
            // If speed changed significantly, reset paw timing to prevent stuck paws
            if (sprite_manager.paw_animation_active && abs((int)speed - (int)old_speed) > 50) {
                sprite_manager.paw_timer = current_time;  // Reset timing
                Serial.println("🔄 Speed change - resetting paw timing");
            }
            
            // Reset Python control timeout
            last_command_time = current_time;
            python_control_mode = true;
            sprite_manager.idle_progression_enabled = false;
        } else if (command == "STOP") {
            cancelTouchBonk();
            // Explicit stop command - better than IDLE
            sprite_manager_set_state(&sprite_manager, ANIM_STATE_IDLE_STAGE1, current_time);
            sprite_manager.idle_progression_enabled = false; // Keep disabled until IDLE_START
            python_control_mode = true;
            last_command_time = current_time;
            Serial.println("🛑 Received STOP command");
            
        } else if (command == "IDLE_START") {
            cancelTouchBonk();
            // Enable idle progression when Python detects no typing
            sprite_manager_set_state(&sprite_manager, ANIM_STATE_IDLE_STAGE1, current_time);
            sprite_manager.idle_progression_enabled = true;  // Enable automatic progression
            python_control_mode = false;  // Let Arduino handle idle progression
            Serial.println("😴 Idle progression enabled");
            
        } else if (command == "IDLE") {
            cancelTouchBonk();
            // Compatibility with old command
            sprite_manager_set_state(&sprite_manager, ANIM_STATE_IDLE_STAGE1, current_time);
            Serial.println("PONG");
            
        } else if (command == "HEARTBEAT") {
            // Connection keepalive - just reset timeout
            last_command_time = current_time;
            python_control_mode = true;
        } else if (command == "STREAK_ON") {
            // Enable streak mode (happy face)
            sprite_manager.is_streak_mode = true;
            if (sprite_manager.paw_animation_active) {
                sprite_manager.current_sprites[LAYER_FACE] = &happy_face;
            }
            Serial.println("😊 Streak mode enabled - happy face!");
        } else if (command == "STREAK_OFF") {
            // Disable streak mode
            sprite_manager.is_streak_mode = false;
            if (sprite_manager.paw_animation_active) {
                sprite_manager.current_sprites[LAYER_FACE] = &stock_face;
            }
            Serial.println("😐 Streak mode disabled - normal face");
        } else if (command.startsWith("STATS:")) {
            // Parse stats: STATS:CPU:45,RAM:67,WPM:23
            String stats = command.substring(6);
            
            int cpuStart = stats.indexOf("CPU:") + 4;
            int cpuEnd = stats.indexOf(",", cpuStart);
            int cpu = stats.substring(cpuStart, cpuEnd).toInt();
            
            int ramStart = stats.indexOf("RAM:") + 4;
            int ramEnd = stats.indexOf(",", ramStart);
            int ram = stats.substring(ramStart, ramEnd).toInt();
            
            int wpmStart = stats.indexOf("WPM:") + 4;
            int wpm = stats.substring(wpmStart).toInt();
            
            updateSystemStats(cpu, ram, wpm);
            
        } else if (command.startsWith("TIME:")) {
            // Handle time updates from Python script
            String time_str = command.substring(5);
            if (time_str.length() == 5 && time_str.charAt(2) == ':') {
                current_time_str = time_str;
            }
            
        } else if (command.startsWith("CPU:")) {
            // Handle CPU usage updates
            cpu_usage = command.substring(4).toInt();
            
        } else if (command.startsWith("RAM:")) {
            // Handle RAM usage updates  
            ram_usage = command.substring(4).toInt();

        } else if (command.startsWith("DIAG_CPU:")) {
            String value = command.substring(9);
            setCpuDiagnostics(value == "ON", current_time);
            Serial.println("ESP32_CPU:" + String(cpu_diagnostics_enabled ? "ON" : "OFF"));
            
        } else if (command.startsWith("WPM:")) {
            // Handle WPM display updates
            wpm_speed = command.substring(4).toInt();
            
        } else if (command == "PING") {
            Serial.println("PONG");
            
        } else if (command.startsWith("ANIM:")) {
            // Handle specific animation commands from tester
            String anim = command.substring(5);
            if (anim == "IDLE_1") {
                sprite_manager_set_state(&sprite_manager, ANIM_STATE_IDLE_STAGE1, current_time);
            } else if (anim == "IDLE_2") {
                sprite_manager_set_state(&sprite_manager, ANIM_STATE_IDLE_STAGE2, current_time);
            } else if (anim == "IDLE_3") {
                sprite_manager_set_state(&sprite_manager, ANIM_STATE_IDLE_STAGE3, current_time);
            } else if (anim == "IDLE_4") {
                sprite_manager_set_state(&sprite_manager, ANIM_STATE_IDLE_STAGE4, current_time);
            } else if (anim == "BLINK") {
                sprite_manager_set_state(&sprite_manager, ANIM_STATE_BLINKING, current_time);
            } else if (anim == "EAR_TWITCH") {
                sprite_manager_set_state(&sprite_manager, ANIM_STATE_EAR_TWITCH, current_time);
            } else if (anim == "TYPING_SLOW") {
                sprite_manager_set_state(&sprite_manager, ANIM_STATE_TYPING_SLOW, current_time);
            } else if (anim == "TYPING_NORMAL") {
                sprite_manager_set_state(&sprite_manager, ANIM_STATE_TYPING_NORMAL, current_time);
            } else if (anim == "TYPING_FAST") {
                sprite_manager_set_state(&sprite_manager, ANIM_STATE_TYPING_FAST, current_time);
            } else if (anim == "HAPPY") {
                sprite_manager.is_streak_mode = true;
                sprite_manager_set_state(&sprite_manager, ANIM_STATE_TYPING_FAST, current_time);
            }
            Serial.println("PONG");
            
        // NEW CONFIGURATION COMMANDS
        } else if (command.startsWith("DISPLAY_CPU:")) {
            String value = command.substring(12);
            settings.show_cpu = (value == "ON");
            updateDisplayVisibility();
            Serial.println("🖥️ CPU display: " + value);
            
        } else if (command.startsWith("DISPLAY_RAM:")) {
            String value = command.substring(12);
            settings.show_ram = (value == "ON");
            updateDisplayVisibility();
            Serial.println("💾 RAM display: " + value);
            
        } else if (command.startsWith("DISPLAY_WPM:")) {
            String value = command.substring(12);
            settings.show_wpm = (value == "ON");
            updateDisplayVisibility();
            Serial.println("⌨️ WPM display: " + value);
            
        } else if (command.startsWith("DISPLAY_TIME:")) {
            String value = command.substring(13);
            settings.show_time = (value == "ON");
            updateDisplayVisibility();
            Serial.println("🕐 Time display: " + value);
            
        } else if (command.startsWith("TIME_FORMAT:")) {
            String format = command.substring(12);
            settings.time_format_24h = (format == "24");
            Serial.println("🕐 Time format: " + format + " hour");
            
        } else if (command.startsWith("SLEEP_TIMEOUT:")) {
            int timeout = command.substring(14).toInt();
            if (timeout >= 1 && timeout <= 60) {
                settings.sleep_timeout_minutes = timeout;
                Serial.println("😴 Sleep timeout: " + String(timeout) + " minutes");
            } else {
                Serial.println("❌ Invalid sleep timeout (1-60 minutes)");
            }
            
        } else if (command.startsWith("SENSITIVITY:")) {
            float sensitivity = command.substring(12).toFloat();
            if (sensitivity >= 0.1 && sensitivity <= 5.0) {
                settings.animation_sensitivity = sensitivity;
                Serial.println("🎚️ Animation sensitivity: " + String(sensitivity));
            } else {
                Serial.println("❌ Invalid sensitivity (0.1-5.0)");
            }
            
        } else if (command == "SAVE_SETTINGS") {
            saveSettings();
            
        } else if (command == "LOAD_SETTINGS") {
            loadSettings();
            updateDisplayVisibility();  // Apply the loaded settings immediately
            
        } else if (command == "RESET_SETTINGS") {
            resetSettings();
            updateDisplayVisibility();  // Apply the reset settings immediately
            saveSettings();  // Save defaults to EEPROM
            Serial.println("🔄 Settings reset and saved");
        }
    }
}

// Sprite management functions
void sprite_manager_init(sprite_manager_t* manager) {
    // Initialize all layers to basic state
    manager->current_sprites[LAYER_BODY] = &standardbody1;
    manager->current_sprites[LAYER_FACE] = &stock_face;
    manager->current_sprites[LAYER_TABLE] = &table1;
    manager->current_sprites[LAYER_PAWS] = &twopawsup;  // Default paws up
    manager->current_sprites[LAYER_EFFECTS] = NULL;
    
    manager->current_state = ANIM_STATE_IDLE_STAGE1;
    manager->state_start_time = millis();
    manager->blink_timer = millis() + random(3000, 8000);
    manager->ear_twitch_timer = millis() + random(10000, 30000);
    manager->effect_timer = 0;
    manager->effect_frame = 0;
    manager->paw_animation_active = false;
    manager->paw_frame = 0;
    manager->paw_timer = 0;
    manager->animation_speed_ms = 200;  // Default speed
    manager->click_effect_left = false;
    
    // Enhanced animation control
    manager->idle_progression_enabled = false;  // Start with Python control
    manager->last_typing_time = 0;
    manager->is_streak_mode = false;             // Start without streak mode
    
    // Initialize animation state variables
    manager->blink_start_time = 0;
    manager->blinking = false;
    manager->ear_twitch_start_time = 0;
    manager->ear_twitching = false;
    
    Serial.println("🐱 Sprite manager initialized");
}

// Calculate adaptive sleep stage timing based on user's timeout setting
void calculateSleepStageTiming(int timeout_minutes, unsigned long* stage1_ms, unsigned long* stage2_ms, unsigned long* stage3_ms) {
    unsigned long total_ms = (unsigned long)timeout_minutes * 60 * 1000;
    
    // Define minimums and maximums for each stage
    unsigned long min_stage2 = 5000;   // 5 seconds minimum
    unsigned long max_stage2 = 60000;  // 1 minute maximum
    unsigned long min_stage3 = 3000;   // 3 seconds minimum  
    unsigned long max_stage3 = 30000;  // 30 seconds maximum
    
    // Calculate based on timeout range for optimal user experience
    if (timeout_minutes <= 3) {
        // Short timeouts: quick but visible progression
        *stage2_ms = max(min_stage2, min(max_stage2, (unsigned long)(total_ms * 0.25)));
        *stage3_ms = max(min_stage3, min(max_stage3, (unsigned long)(total_ms * 0.15)));
    } else if (timeout_minutes <= 10) {
        // Medium timeouts: balanced progression
        *stage2_ms = max(min_stage2, min(max_stage2, (unsigned long)(total_ms * 0.20)));
        *stage3_ms = max(min_stage3, min(max_stage3, (unsigned long)(total_ms * 0.10)));
    } else {
        // Long timeouts: mostly normal, quick sleep transition
        *stage2_ms = max(min_stage2, min(max_stage2, (unsigned long)(total_ms * 0.15)));
        *stage3_ms = max(min_stage3, min(max_stage3, (unsigned long)(total_ms * 0.05)));
    }
    
    // Stage 1 gets the remainder to ensure total equals user setting
    *stage1_ms = total_ms - *stage2_ms - *stage3_ms;
}

void sprite_manager_update(sprite_manager_t* manager, uint32_t current_time) {
    // Check for typing timeout (Arduino-side safety)
    if (manager->paw_animation_active && manager->last_typing_time > 0) {
        if (current_time - manager->last_typing_time > TYPING_TIMEOUT_MS) {
            // Stop typing animation due to timeout
            manager->paw_animation_active = false;
            manager->current_sprites[LAYER_EFFECTS] = NULL;
            Serial.println("🛑 Typing timeout - stopping animation");
        }
    }
    
    // Check if Python control has timed out
    if (python_control_mode && current_time - last_command_time > PYTHON_TIMEOUT_MS) {
        python_control_mode = false;
        manager->idle_progression_enabled = true;
        Serial.println("⚠️ Python timeout - enabling auto mode");
    }
    
    // Handle automatic idle progression only if enabled
    if (manager->idle_progression_enabled || !python_control_mode) {
        // Calculate adaptive timing based on current sleep timeout setting
        unsigned long stage1_duration, stage2_duration, stage3_duration;
        calculateSleepStageTiming(settings.sleep_timeout_minutes, &stage1_duration, &stage2_duration, &stage3_duration);
        
        if (manager->current_state == ANIM_STATE_IDLE_STAGE1) {
            if (current_time - manager->state_start_time > stage1_duration) {
                sprite_manager_set_state(manager, ANIM_STATE_IDLE_STAGE2, current_time);
            }
        } else if (manager->current_state == ANIM_STATE_IDLE_STAGE2) {
            if (current_time - manager->state_start_time > stage2_duration) {
                sprite_manager_set_state(manager, ANIM_STATE_IDLE_STAGE3, current_time);
            }
        } else if (manager->current_state == ANIM_STATE_IDLE_STAGE3) {
            if (current_time - manager->state_start_time > stage3_duration) {
                sprite_manager_set_state(manager, ANIM_STATE_IDLE_STAGE4, current_time);
            }
        }
    }
    
    // Handle paw animations - 4-step pattern: left_down → both_up → right_down → both_up
    if (manager->paw_animation_active) {
        // Trust Python's speed calculations - no additional rate limiting
        if (current_time - manager->paw_timer >= manager->animation_speed_ms) {
            manager->paw_frame = (manager->paw_frame + 1) % 4;  // 4-step pattern
            
            // 4-step typing pattern with effects synchronized to paw strikes
            switch (manager->paw_frame) {
                case 0:  // Left paw down
                    manager->current_sprites[LAYER_PAWS] = &leftpawdown;
                    // Show left click effect for fast typing
                    if (manager->current_state == ANIM_STATE_TYPING_FAST || 
                        manager->current_state == ANIM_STATE_TYPING_STREAK) {
                        manager->current_sprites[LAYER_EFFECTS] = &left_click_effect;
                    } else {
                        manager->current_sprites[LAYER_EFFECTS] = NULL;
                    }
                    break;
                    
                case 1:  // Both paws up (rest position)
                    manager->current_sprites[LAYER_PAWS] = &twopawsup;
                    manager->current_sprites[LAYER_EFFECTS] = NULL;  // No effects during rest
                    break;
                    
                case 2:  // Right paw down  
                    manager->current_sprites[LAYER_PAWS] = &rightpawdown;
                    // Show right click effect for fast typing
                    if (manager->current_state == ANIM_STATE_TYPING_FAST || 
                        manager->current_state == ANIM_STATE_TYPING_STREAK) {
                        manager->current_sprites[LAYER_EFFECTS] = &right_click_effect;
                    } else {
                        manager->current_sprites[LAYER_EFFECTS] = NULL;
                    }
                    break;
                    
                case 3:  // Both paws up (rest position)
                    manager->current_sprites[LAYER_PAWS] = &twopawsup;
                    manager->current_sprites[LAYER_EFFECTS] = NULL;  // No effects during rest
                    break;
            }
            manager->paw_timer = current_time;
        }
    } else {
        // When not typing, ensure paws are in the correct idle position based on state
        if (manager->current_state == ANIM_STATE_IDLE_STAGE1) {
            manager->current_sprites[LAYER_PAWS] = &twopawsup;  // Visible paws for stage 1
        } else if (manager->current_state >= ANIM_STATE_IDLE_STAGE2 && 
                   manager->current_state <= ANIM_STATE_IDLE_STAGE4) {
            manager->current_sprites[LAYER_PAWS] = NULL;  // Hidden paws for stages 2-4
        }
        
        // Only clear effects if NOT in IDLE_STAGE4 (which needs sleepy effects)
        if (manager->current_state != ANIM_STATE_IDLE_STAGE4) {
            manager->current_sprites[LAYER_EFFECTS] = NULL;  // Clear typing effects
        }
    }
    
    // Handle sleepy effects animation (for IDLE_STAGE4)
    if (manager->current_state == ANIM_STATE_IDLE_STAGE4) {
        if (current_time - manager->effect_timer > 1000) { // Change effect every second
            manager->effect_frame = (manager->effect_frame + 1) % 3;
            switch (manager->effect_frame) {
                case 0: manager->current_sprites[LAYER_EFFECTS] = &sleepy1; break;
                case 1: manager->current_sprites[LAYER_EFFECTS] = &sleepy2; break;
                case 2: manager->current_sprites[LAYER_EFFECTS] = &sleepy3; break;
            }
            manager->effect_timer = current_time;
        }
    }
    
    // Handle automatic blinking (only when awake, not during sleep)
    // Only blink when not sleeping (stages 3 and 4 have sleepy face, no blinking)
    bool can_blink = (manager->current_state != ANIM_STATE_IDLE_STAGE3 && 
                      manager->current_state != ANIM_STATE_IDLE_STAGE4);
    
    if (!manager->blinking && current_time >= manager->blink_timer && can_blink) {
        // Start blink
        manager->blinking = true;
        manager->blink_start_time = current_time;
        manager->current_sprites[LAYER_FACE] = &blink_face;
    } else if (manager->blinking && current_time - manager->blink_start_time > 200) {
        // End blink after 200ms
        manager->blinking = false;
        // Restore normal face after blink based on current state and streak mode
        if (manager->current_state == ANIM_STATE_IDLE_STAGE3 || 
            manager->current_state == ANIM_STATE_IDLE_STAGE4) {
            manager->current_sprites[LAYER_FACE] = &sleepy_face;
        } else if (manager->is_streak_mode && manager->paw_animation_active) {
            manager->current_sprites[LAYER_FACE] = &happy_face;  // Happy face during any typing streak
        } else {
            manager->current_sprites[LAYER_FACE] = &stock_face;  // Default face
        }
        // Set next blink time (only if can still blink)
        if (can_blink) {
            manager->blink_timer = current_time + random(3000, 8000);
        } else {
            // When entering sleep, set longer blink timer for when waking up
            manager->blink_timer = current_time + random(5000, 10000);
        }
    }
    
    // Handle ear twitch
    if (!manager->ear_twitching && current_time >= manager->ear_twitch_timer) {
        // Start ear twitch
        manager->ear_twitching = true;
        manager->ear_twitch_start_time = current_time;
        manager->current_sprites[LAYER_BODY] = &bodyeartwitch;
    } else if (manager->ear_twitching && current_time - manager->ear_twitch_start_time > 500) {
        // End ear twitch after 500ms
        manager->ear_twitching = false;
        manager->current_sprites[LAYER_BODY] = &standardbody1;
        // Set next ear twitch time
        manager->ear_twitch_timer = current_time + random(10000, 30000);
    }
}

void sprite_manager_set_state(sprite_manager_t* manager, animation_state_t new_state, uint32_t current_time) {
    Serial.print("🔄 Animation state: ");
    Serial.print(get_state_name(manager->current_state));
    Serial.print(" → ");
    Serial.println(get_state_name(new_state));
    
    manager->current_state = new_state;
    manager->state_start_time = current_time;
    
    // Update typing timing for timeout tracking
    if (new_state == ANIM_STATE_TYPING_SLOW || 
        new_state == ANIM_STATE_TYPING_NORMAL || 
        new_state == ANIM_STATE_TYPING_FAST) {
        manager->last_typing_time = current_time;
    }
    
    // Set appropriate sprites based on state - always ensure base layers are set
    // Base layers that should always be present
    manager->current_sprites[LAYER_BODY] = &standardbody1;
    manager->current_sprites[LAYER_TABLE] = &table1;
    
    switch (new_state) {
        case ANIM_STATE_IDLE_STAGE1:
            // Stage 1: Stock face with paws up (hands visible above table)
            manager->current_sprites[LAYER_PAWS] = &twopawsup;  // Both paws visible above table
            manager->current_sprites[LAYER_EFFECTS] = NULL;
            manager->current_sprites[LAYER_FACE] = &stock_face;
            manager->paw_animation_active = false;
            Serial.println("😐 Stage 1: Stock face, paws up");
            break;
            
        case ANIM_STATE_IDLE_STAGE2:
            // Stage 2: Stock face + hands gone (underneath table)
            manager->current_sprites[LAYER_PAWS] = NULL;  // No paws visible (hands underneath table)
            manager->current_sprites[LAYER_EFFECTS] = NULL;
            manager->current_sprites[LAYER_FACE] = &stock_face;  // Still stock face
            manager->paw_animation_active = false;
            Serial.println("😐 Stage 2: Stock face, hands hidden");
            break;
            
        case ANIM_STATE_IDLE_STAGE3:
            // Stage 3: Hands gone + sleepy face (prepare for effects)
            manager->current_sprites[LAYER_PAWS] = NULL;  // No paws visible
            manager->current_sprites[LAYER_EFFECTS] = NULL;
            manager->current_sprites[LAYER_FACE] = &sleepy_face;
            manager->paw_animation_active = false;
            Serial.println("😴 Stage 3: Deep sleep preparation, hands hidden");
            break;
            
        case ANIM_STATE_IDLE_STAGE4:
            // Stage 4: Hands gone + sleepy face + cycling sleepy effects
            manager->current_sprites[LAYER_PAWS] = NULL;  // No paws visible
            manager->current_sprites[LAYER_FACE] = &sleepy_face;
            manager->paw_animation_active = false;
            manager->effect_timer = current_time;  // Initialize effect timer for cycling
            // Effects will cycle in main update loop
            Serial.println("😴 Stage 4: Deep sleep with cycling effects, hands hidden");
            break;
            
        case ANIM_STATE_TYPING_SLOW:
            // Slow typing: 4-step paw pattern, no effects
            manager->current_sprites[LAYER_FACE] = manager->is_streak_mode ? &happy_face : &stock_face;
            manager->current_sprites[LAYER_EFFECTS] = NULL;
            manager->current_sprites[LAYER_PAWS] = &leftpawdown;  // Start with left paw (frame 0)
            manager->paw_animation_active = true;
            manager->paw_frame = 0;  // Reset paw frame to prevent stuck paws
            manager->paw_timer = current_time;
            Serial.println(manager->is_streak_mode ? "👐😊 Slow typing with happy face" : "👐 Slow typing");
            break;
            
        case ANIM_STATE_TYPING_NORMAL:
            // Normal typing: 4-step paw pattern, no effects
            manager->current_sprites[LAYER_FACE] = manager->is_streak_mode ? &happy_face : &stock_face;
            manager->current_sprites[LAYER_EFFECTS] = NULL;
            manager->current_sprites[LAYER_PAWS] = &leftpawdown;  // Start with left paw (frame 0)
            manager->paw_animation_active = true;
            manager->paw_frame = 0;  // Reset paw frame to prevent stuck paws
            manager->paw_timer = current_time;
            Serial.println(manager->is_streak_mode ? "👐😊 Normal typing with happy face" : "👐 Normal typing");
            break;
            
        case ANIM_STATE_TYPING_FAST:
            // Fast typing: 4-step paw pattern + click effects
            manager->current_sprites[LAYER_FACE] = manager->is_streak_mode ? &happy_face : &stock_face;
            manager->current_sprites[LAYER_PAWS] = &leftpawdown;  // Start with left paw (frame 0)
            manager->paw_animation_active = true;
            manager->paw_frame = 0;  // Reset paw frame to prevent stuck paws
            manager->paw_timer = current_time;
            Serial.println(manager->is_streak_mode ? "👐⚡😊 Fast typing with happy face and effects" : "👐⚡ Fast typing with click effects");
            break;
            
        case ANIM_STATE_TYPING_STREAK:
            // Legacy streak state - treat as fast typing with happy face
            manager->current_sprites[LAYER_FACE] = &happy_face;
            manager->current_sprites[LAYER_PAWS] = &leftpawdown;  // Start with left paw (frame 0)
            manager->paw_animation_active = true;
            manager->paw_frame = 0;  // Reset paw frame to prevent stuck paws
            manager->paw_timer = current_time;
            Serial.println("👐⚡😊 Legacy streak mode - fast typing with happy face");
            break;
    }
    
    // Reset idle progression when entering any typing state
    if (new_state == ANIM_STATE_TYPING_SLOW || 
        new_state == ANIM_STATE_TYPING_NORMAL || 
        new_state == ANIM_STATE_TYPING_FAST) {
        manager->idle_progression_enabled = false;  // Stop auto idle progression
        Serial.println("🚫 Auto idle progression disabled");
    }
}

void sprite_render_layers(sprite_manager_t* manager, lv_obj_t* canvas, uint32_t current_time) {
    // Clear canvas with minimal operations
    lv_canvas_fill_bg(canvas, lv_color_white(), LV_OPA_TRANSP);
    
    // Render layers in order (back to front) with optimized drawing
    lv_draw_img_dsc_t img_dsc;
    lv_draw_img_dsc_init(&img_dsc);  // Initialize once outside loop
    
    for (int layer = 0; layer < NUM_LAYERS; layer++) {
        const lv_img_dsc_t* sprite = manager->current_sprites[layer];
        if (sprite) {
            // Draw sprite at origin (0,0) - canvas will be zoomed to 4x size
            // Using single draw call per sprite to minimize operations
            lv_canvas_draw_img(canvas, 0, 0, sprite, &img_dsc);
        }
    }
}

// Helper function to get state name for debugging
const char* get_state_name(animation_state_t state) {
    switch (state) {
        case ANIM_STATE_IDLE_STAGE1: return "IDLE_STAGE1";
        case ANIM_STATE_IDLE_STAGE2: return "IDLE_STAGE2"; 
        case ANIM_STATE_IDLE_STAGE3: return "IDLE_STAGE3";
        case ANIM_STATE_IDLE_STAGE4: return "IDLE_STAGE4";
        case ANIM_STATE_TYPING_SLOW: return "TYPING_SLOW";
        case ANIM_STATE_TYPING_NORMAL: return "TYPING_NORMAL";
        case ANIM_STATE_TYPING_FAST: return "TYPING_FAST";
        case ANIM_STATE_TYPING_STREAK: return "TYPING_STREAK";  // Keep for compatibility but unused
        default: return "UNKNOWN";
    }
}

void setup() {
    // Covers arrive over the same UART as commands. Keep enough headroom for
    // a chunk while LVGL is rendering a frame, otherwise one lost RGB byte
    // shifts the remaining image into a scrambled pattern.
    Serial.setRxBufferSize(8192);
    Serial.begin(115200);
    Serial.setTimeout(10);
    Serial.println("🐱 Bongo Cat with Sprites Starting...");

    // Register once; the measurement itself stays disabled until BongoDesk
    // sends DIAG_CPU:ON. Returning true makes each callback run only per tick.
    cpu_diagnostics_hooks_ready =
        esp_register_freertos_idle_hook_for_cpu(cpuIdleHookCore0, 0) == ESP_OK &&
        esp_register_freertos_idle_hook_for_cpu(cpuIdleHookCore1, 1) == ESP_OK;
    if (!cpu_diagnostics_hooks_ready) {
        Serial.println("ESP32_CPU:UNAVAILABLE");
    }
    
    // Initialize EEPROM for settings persistence
    EEPROM.begin(EEPROM_SIZE);
    
    // Load settings from EEPROM (will use defaults if invalid)
    loadSettings();
    
    // Initialize random seed for animations
    randomSeed(analogRead(0));
    
    tft.init();
    tft.setRotation(0);
    tft.fillScreen(TFT_WHITE);  // White background
    
    lv_init();
    
    lv_disp_draw_buf_init(&draw_buf, buf, NULL, SCREEN_WIDTH * DRAW_BUFFER_ROWS);
    
    static lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res = SCREEN_WIDTH;
    disp_drv.ver_res = SCREEN_HEIGHT;
    disp_drv.flush_cb = my_disp_flush;
    disp_drv.draw_buf = &draw_buf;
    lv_disp_drv_register(&disp_drv);
    
    // Initialize sprite manager
    sprite_manager_init(&sprite_manager);
    
    createBongoCat();
    createMediaScreen();
    
    // Apply loaded settings to display visibility now that UI is created
    updateDisplayVisibility();
    
    Serial.println("✅ Bongo Cat Ready!");
    Serial.println("✨ BongoDesk Spotify features ready");
}

void createBongoCat() {
    screen = lv_scr_act();
    
    // Set white background
    lv_obj_set_style_bg_color(screen, lv_color_white(), 0);
    
    // Create cat canvas with proper sizing
    cat_canvas = lv_canvas_create(screen);
    
    // Use 64x64 base sprite size for the canvas buffer
    static lv_color_t canvas_buf[CAT_SIZE * CAT_SIZE];  // 64x64 buffer
    lv_canvas_set_buffer(cat_canvas, canvas_buf, CAT_SIZE, CAT_SIZE, LV_IMG_CF_TRUE_COLOR);
    
    // Apply 4x zoom to make 64x64 sprites appear as 256x256 on screen
    lv_img_set_zoom(cat_canvas, 1024);  // 4x zoom: 64x64 -> 256x256 pixels
    lv_img_set_antialias(cat_canvas, false);  // Keep pixels crisp and blocky
    
    // Position cat: original alignment method + 3 cat pixels right + a bit lower
    lv_obj_align(cat_canvas, LV_ALIGN_CENTER, 12, 50);  // 12px right (3 cat pixels), 50px lower
    
    // Create system stats labels (top left) with pixelated font
    cpu_label = lv_label_create(screen);
    lv_label_set_text(cpu_label, "CPU: 0%");
    lv_obj_set_style_text_font(cpu_label, &lv_font_unscii_16, 0);
    lv_obj_set_style_text_color(cpu_label, lv_color_black(), 0);
    lv_obj_align(cpu_label, LV_ALIGN_TOP_LEFT, 5, 5);
    
    ram_label = lv_label_create(screen);
    lv_label_set_text(ram_label, "RAM: 0%");
    lv_obj_set_style_text_font(ram_label, &lv_font_unscii_16, 0);
    lv_obj_set_style_text_color(ram_label, lv_color_black(), 0);
    lv_obj_align(ram_label, LV_ALIGN_TOP_LEFT, 5, 25);
    
    wpm_label = lv_label_create(screen);
    lv_label_set_text(wpm_label, "WPM: 0");
    lv_obj_set_style_text_font(wpm_label, &lv_font_unscii_16, 0);
    lv_obj_set_style_text_color(wpm_label, lv_color_black(), 0);
    lv_obj_align(wpm_label, LV_ALIGN_TOP_LEFT, 5, 45);
    
    // Create time label (top right) - bigger pixelated font
    time_label = lv_label_create(screen);
    lv_label_set_text(time_label, "00:00");
    lv_obj_set_style_text_font(time_label, &lv_font_unscii_16, 0);
    lv_obj_set_style_text_color(time_label, lv_color_black(), 0);
    lv_obj_align(time_label, LV_ALIGN_TOP_RIGHT, -5, 5);

    createFeatureOverlay();
    
    // Initial render
    sprite_render_layers(&sprite_manager, cat_canvas, millis());
}

void createFeatureOverlay() {
    feature_overlay = lv_obj_create(lv_layer_top());
    lv_obj_set_size(feature_overlay, 220, 244);
    lv_obj_align(feature_overlay, LV_ALIGN_CENTER, 0, 0);
    lv_obj_set_style_bg_color(feature_overlay, lv_color_hex(0x101419), 0);
    lv_obj_set_style_bg_opa(feature_overlay, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(feature_overlay, lv_color_hex(0x1ED760), 0);
    lv_obj_set_style_border_width(feature_overlay, 2, 0);
    lv_obj_set_style_radius(feature_overlay, 14, 0);
    lv_obj_set_style_pad_all(feature_overlay, 10, 0);
    lv_obj_clear_flag(feature_overlay, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(feature_overlay, LV_OBJ_FLAG_HIDDEN);

    feature_overlay_label = lv_label_create(feature_overlay);
    lv_obj_set_width(feature_overlay_label, 196);
    lv_obj_set_style_text_font(feature_overlay_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(feature_overlay_label, lv_color_hex(0x1ED760), 0);
    lv_obj_set_style_text_align(feature_overlay_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_label_set_text(feature_overlay_label, "PANELER");
    lv_obj_align(feature_overlay_label, LV_ALIGN_TOP_MID, 0, 0);

    feature_overlay_bongo_button = lv_obj_create(feature_overlay);
    lv_obj_set_pos(feature_overlay_bongo_button, 0, 26);
    lv_obj_set_size(feature_overlay_bongo_button, 196, 56);
    lv_obj_set_style_bg_opa(feature_overlay_bongo_button, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(feature_overlay_bongo_button, 10, 0);
    lv_obj_set_style_pad_all(feature_overlay_bongo_button, 0, 0);
    lv_obj_clear_flag(feature_overlay_bongo_button, LV_OBJ_FLAG_SCROLLABLE);
    feature_overlay_bongo_label = lv_label_create(feature_overlay_bongo_button);
    lv_obj_set_style_text_font(feature_overlay_bongo_label, &lv_font_montserrat_14, 0);
    lv_label_set_text(feature_overlay_bongo_label, "BONGO  AKTIV");
    lv_obj_center(feature_overlay_bongo_label);

    feature_overlay_player_button = lv_obj_create(feature_overlay);
    lv_obj_set_pos(feature_overlay_player_button, 0, 90);
    lv_obj_set_size(feature_overlay_player_button, 196, 56);
    lv_obj_set_style_bg_opa(feature_overlay_player_button, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(feature_overlay_player_button, 10, 0);
    lv_obj_set_style_pad_all(feature_overlay_player_button, 0, 0);
    lv_obj_clear_flag(feature_overlay_player_button, LV_OBJ_FLAG_SCROLLABLE);
    feature_overlay_player_label = lv_label_create(feature_overlay_player_button);
    lv_obj_set_style_text_font(feature_overlay_player_label, &lv_font_montserrat_14, 0);
    lv_label_set_text(feature_overlay_player_label, "SPELARE");
    lv_obj_center(feature_overlay_player_label);

    feature_overlay_stats_label = lv_label_create(feature_overlay);
    lv_obj_set_width(feature_overlay_stats_label, 196);
    lv_obj_set_style_text_font(feature_overlay_stats_label, &lv_font_montserrat_10, 0);
    lv_obj_set_style_text_color(feature_overlay_stats_label, lv_color_white(), 0);
    lv_label_set_text(feature_overlay_stats_label, "");
    lv_obj_set_pos(feature_overlay_stats_label, 0, 151);

    feature_overlay_media_label = lv_label_create(feature_overlay);
    lv_obj_set_width(feature_overlay_media_label, 196);
    lv_obj_set_style_text_font(feature_overlay_media_label, &lv_font_montserrat_10, 0);
    lv_obj_set_style_text_color(feature_overlay_media_label, lv_color_hex(0x1ED760), 0);
    lv_label_set_text(feature_overlay_media_label, "MEDIA  NO MEDIA");
    lv_obj_set_pos(feature_overlay_media_label, 0, 179);

    feature_overlay_title_label = lv_label_create(feature_overlay);
    lv_obj_set_size(feature_overlay_title_label, 196, 14);
    lv_label_set_long_mode(feature_overlay_title_label, LV_LABEL_LONG_DOT);
    lv_obj_set_style_text_font(feature_overlay_title_label, &lv_font_montserrat_10, 0);
    lv_obj_set_style_text_color(feature_overlay_title_label, lv_color_white(), 0);
    lv_label_set_text(feature_overlay_title_label, "Nothing playing");
    lv_obj_set_pos(feature_overlay_title_label, 0, 196);

    feature_overlay_hint_label = lv_label_create(feature_overlay);
    lv_obj_set_width(feature_overlay_hint_label, 130);
    lv_obj_set_style_text_font(feature_overlay_hint_label, &lv_font_montserrat_10, 0);
    lv_obj_set_style_text_color(feature_overlay_hint_label, lv_color_hex(0xD5D9DE), 0);
    lv_label_set_text(feature_overlay_hint_label, "HOLD  CLOSE");
    lv_obj_set_pos(feature_overlay_hint_label, 0, 218);

    feature_overlay_count_label = lv_label_create(feature_overlay);
    lv_label_set_text(feature_overlay_count_label, "BONKS  0");
    lv_obj_set_style_text_font(feature_overlay_count_label, &lv_font_montserrat_10, 0);
    lv_obj_set_style_text_color(feature_overlay_count_label, lv_color_hex(0x1ED760), 0);
    lv_obj_set_pos(feature_overlay_count_label, 136, 218);
}

lv_obj_t *createMediaControlButton(lv_obj_t *parent, const char *symbol,
                                   int x, int y, int size) {
    lv_obj_t *button = lv_obj_create(parent);
    lv_obj_set_pos(button, x, y);
    lv_obj_set_size(button, size, size);
    lv_obj_set_style_bg_color(button, lv_color_hex(0x171A1F), 0);
    lv_obj_set_style_bg_opa(button, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(button, 0, 0);
    lv_obj_set_style_radius(button, size / 2, 0);
    lv_obj_set_style_pad_all(button, 0, 0);
    lv_obj_clear_flag(button, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *label = lv_label_create(button);
    lv_label_set_text(label, symbol);
    lv_obj_set_style_text_font(label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(0xF7F7F7), 0);
    lv_obj_center(label);
    return label;
}

void createMediaScreen() {
    media_screen = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(media_screen, lv_color_hex(0x080A0C), 0);
    lv_obj_set_style_bg_opa(media_screen, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(media_screen, 0, 0);
    lv_obj_set_style_pad_all(media_screen, 0, 0);
    lv_obj_clear_flag(media_screen, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *brand = lv_label_create(media_screen);
    lv_label_set_text(brand, "BONGO DJ");
    lv_obj_set_style_text_font(brand, &lv_font_montserrat_10, 0);
    lv_obj_set_style_text_color(brand, lv_color_hex(0x1ED760), 0);
    lv_obj_set_pos(brand, 10, 4);

    media_source_label = lv_label_create(media_screen);
    lv_label_set_text(media_source_label, "WINDOWS");
    lv_obj_set_style_text_font(media_source_label, &lv_font_montserrat_10, 0);
    lv_obj_set_style_text_color(media_source_label, lv_color_hex(0xD5D9DE), 0);
    lv_obj_align(media_source_label, LV_ALIGN_TOP_RIGHT, -10, 4);

    media_art_box = lv_obj_create(media_screen);
    lv_obj_set_pos(media_art_box, 36, 17);
    lv_obj_set_size(media_art_box, 168, 168);
    lv_obj_set_style_bg_color(media_art_box, lv_color_hex(0x080A0C), 0);
    lv_obj_set_style_bg_opa(media_art_box, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(media_art_box, 1, 0);
    lv_obj_set_style_border_color(media_art_box, lv_color_hex(0x252A30), 0);
    lv_obj_set_style_radius(media_art_box, 84, 0);
    lv_obj_set_style_clip_corner(media_art_box, true, 0);
    lv_obj_set_style_pad_all(media_art_box, 0, 0);
    lv_obj_clear_flag(media_art_box, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_clear_flag(media_art_box, LV_OBJ_FLAG_OVERFLOW_VISIBLE);

    media_state_label = lv_label_create(media_art_box);
    lv_label_set_text(media_state_label, LV_SYMBOL_AUDIO "\nNOTHING PLAYING");
    lv_obj_set_style_text_font(media_state_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(media_state_label, lv_color_hex(0xD5D9DE), 0);
    lv_obj_set_style_text_align(media_state_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_center(media_state_label);

    media_art_image = lv_img_create(media_art_box);
    lv_obj_add_flag(media_art_image, LV_OBJ_FLAG_HIDDEN);

    media_cat_canvas = lv_canvas_create(media_art_box);
    lv_canvas_set_buffer(media_cat_canvas, media_cat_canvas_buffer,
                         CAT_SIZE, CAT_SIZE, LV_IMG_CF_TRUE_COLOR);
    lv_img_set_zoom(media_cat_canvas, MEDIA_CAT_ZOOM);
    lv_img_set_antialias(media_cat_canvas, false);
    lv_obj_center(media_cat_canvas);
    lv_obj_add_flag(media_cat_canvas, LV_OBJ_FLAG_HIDDEN);
    renderMediaCat();

    lv_obj_t *info_panel = lv_obj_create(media_screen);
    lv_obj_set_pos(info_panel, 6, 188);
    lv_obj_set_size(info_panel, 228, 64);
    lv_obj_set_style_bg_color(info_panel, lv_color_hex(0x15191E), 0);
    lv_obj_set_style_bg_opa(info_panel, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(info_panel, 1, 0);
    lv_obj_set_style_border_color(info_panel, lv_color_hex(0x292E35), 0);
    lv_obj_set_style_radius(info_panel, 10, 0);
    lv_obj_set_style_pad_all(info_panel, 0, 0);
    lv_obj_clear_flag(info_panel, LV_OBJ_FLAG_SCROLLABLE);

    media_title_label = lv_label_create(info_panel);
    lv_label_set_text(media_title_label, "Nothing playing");
    lv_obj_set_pos(media_title_label, 8, 5);
    lv_obj_set_width(media_title_label, 212);
    lv_label_set_long_mode(media_title_label, LV_LABEL_LONG_SCROLL_CIRCULAR);
    lv_obj_set_style_text_font(media_title_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(media_title_label, lv_color_hex(0xFFFFFF), 0);

    media_artist_label = lv_label_create(info_panel);
    lv_label_set_text(media_artist_label, "Start Spotify on this PC");
    lv_obj_set_pos(media_artist_label, 8, 25);
    lv_obj_set_width(media_artist_label, 212);
    lv_label_set_long_mode(media_artist_label, LV_LABEL_LONG_SCROLL_CIRCULAR);
    lv_obj_set_style_text_font(media_artist_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(media_artist_label, lv_color_hex(0xD7DBE0), 0);

    media_progress_bar = lv_bar_create(info_panel);
    lv_obj_set_pos(media_progress_bar, 8, 50);
    lv_obj_set_size(media_progress_bar, 212, 6);
    lv_bar_set_range(media_progress_bar, 0, 1000);
    lv_bar_set_value(media_progress_bar, 0, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(media_progress_bar, lv_color_hex(0x343940), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(media_progress_bar, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_bg_color(media_progress_bar, lv_color_hex(0x1ED760), LV_PART_INDICATOR);
    lv_obj_set_style_radius(media_progress_bar, 3, LV_PART_MAIN);
    lv_obj_set_style_radius(media_progress_bar, 3, LV_PART_INDICATOR);

    media_elapsed_label = lv_label_create(media_screen);
    lv_label_set_text(media_elapsed_label, "0:00");
    lv_obj_set_pos(media_elapsed_label, 12, 255);
    media_duration_label = lv_label_create(media_screen);
    lv_label_set_text(media_duration_label, "0:00");
    lv_obj_align(media_duration_label, LV_ALIGN_TOP_RIGHT, -12, 255);
    for (lv_obj_t *time_label_item : {media_elapsed_label, media_duration_label}) {
        lv_obj_set_style_text_font(time_label_item, &lv_font_montserrat_10, 0);
        lv_obj_set_style_text_color(time_label_item, lv_color_hex(0xC7CCD2), 0);
    }

    media_playback_status_label = lv_label_create(media_screen);
    lv_label_set_text(media_playback_status_label, "NO MEDIA");
    lv_obj_set_width(media_playback_status_label, 224);
    lv_obj_set_style_text_font(media_playback_status_label, &lv_font_montserrat_10, 0);
    lv_obj_set_style_text_color(media_playback_status_label, lv_color_hex(0x1ED760), 0);
    lv_obj_set_style_text_align(media_playback_status_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_pos(media_playback_status_label, 8, 268);

    media_gesture_hint_label = lv_label_create(media_screen);
    lv_obj_set_size(media_gesture_hint_label, 224, 28);
    lv_obj_set_style_text_font(media_gesture_hint_label, &lv_font_montserrat_10, 0);
    lv_obj_set_style_text_color(media_gesture_hint_label, lv_color_hex(0x747B84), 0);
    lv_obj_set_style_text_align(media_gesture_hint_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(media_gesture_hint_label, LV_ALIGN_BOTTOM_MID, 0, -13);

    loadGenericVinyl();
    refreshMediaUi();
}

void showMediaScreen() {
    if (!media_screen || spotify_screen_active) return;
    spotify_screen_active = true;
    lv_scr_load_anim(media_screen, LV_SCR_LOAD_ANIM_FADE_ON, 220, 0, false);
}

void showBongoScreen() {
    if (!screen || !spotify_screen_active) return;
    spotify_screen_active = false;
    lv_scr_load_anim(screen, LV_SCR_LOAD_ANIM_FADE_ON, 220, 0, false);
}

void cancelTouchBonk() {
    if (!touch_bonk_active) return;
    touch_bonk_active = false;
    sprite_manager.is_streak_mode = false;
}

bool cpuIdleHookCore0() {
    if (cpu_diagnostics_enabled) cpu_idle_ticks_core0++;
    return true;
}

bool cpuIdleHookCore1() {
    if (cpu_diagnostics_enabled) cpu_idle_ticks_core1++;
    return true;
}

void setCpuDiagnostics(bool enabled, uint32_t current_time) {
    cpu_diagnostics_enabled = enabled && cpu_diagnostics_hooks_ready;
    cpu_diagnostics_last_time = current_time;
    cpu_diagnostics_last_idle0 = cpu_idle_ticks_core0;
    cpu_diagnostics_last_idle1 = cpu_idle_ticks_core1;
    cpu_diagnostics_estimate = -1;
    cpu_diagnostics_sample_ms = 0;
}

void reportDeviceStatus(uint32_t current_time) {
    static uint32_t last_report_time = 0;
    if (current_time - last_report_time < 5000) return;
    last_report_time = current_time;

    if (cpu_diagnostics_enabled) {
        uint32_t elapsed = current_time - cpu_diagnostics_last_time;
        uint32_t expected_ticks = elapsed / portTICK_PERIOD_MS;
        if (expected_ticks == 0) expected_ticks = 1;
        uint32_t idle0 = cpu_idle_ticks_core0;
        uint32_t idle1 = cpu_idle_ticks_core1;
        uint32_t observed_idle = (idle0 - cpu_diagnostics_last_idle0) +
                                 (idle1 - cpu_diagnostics_last_idle1);
        float idle_fraction = (float)observed_idle / (float)(expected_ticks * 2UL);
        idle_fraction = constrain(idle_fraction, 0.0f, 1.0f);
        cpu_diagnostics_estimate = (int)roundf((1.0f - idle_fraction) * 100.0f);
        cpu_diagnostics_sample_ms = elapsed;
        cpu_diagnostics_last_time = current_time;
        cpu_diagnostics_last_idle0 = idle0;
        cpu_diagnostics_last_idle1 = idle1;
    }

    // This is a low-resolution activity estimate: it observes whether each
    // FreeRTOS core had an idle tick during the five-second sample. It avoids
    // the invasive task profiler required for exact per-task CPU time.
    Serial.printf("ESP32_STATUS:HEAP:%u,HEAP_TOTAL:%u,MIN_HEAP:%u,PSRAM:%u,PSRAM_TOTAL:%u,CPU_ENABLED:%u,CPU_ESTIMATE:%d,CPU_SAMPLE_MS:%lu,UPTIME:%lu\n",
                  ESP.getFreeHeap(),
                  ESP.getHeapSize(),
                  ESP.getMinFreeHeap(),
                  ESP.getFreePsram(),
                  ESP.getPsramSize(),
                  cpu_diagnostics_enabled ? 1 : 0,
                  cpu_diagnostics_estimate,
                  (unsigned long)cpu_diagnostics_sample_ms,
                  (unsigned long)(current_time / 1000));
}

void triggerTouchBonk(uint32_t current_time) {
    touch_bonk_count++;
    touch_bonk_active = true;
    touch_bonk_until = current_time + TOUCH_BONK_DURATION_MS;
    sprite_manager.is_streak_mode = true;
    sprite_manager.animation_speed_ms = 85;
    sprite_manager_set_state(&sprite_manager, ANIM_STATE_TYPING_FAST, current_time);

    if (feature_overlay_count_label) {
        lv_label_set_text_fmt(feature_overlay_count_label,
                              "BONKS  %lu",
                              (unsigned long)touch_bonk_count);
    }
    Serial.printf("BONK:%lu\n", (unsigned long)touch_bonk_count);
}

void hideFeatureOverlay() {
    if (!feature_overlay) return;
    lv_obj_add_flag(feature_overlay, LV_OBJ_FLAG_HIDDEN);
    overlay_hide_time = 0;
}

void toggleFeatureOverlay(uint32_t current_time) {
    if (!feature_overlay) return;
    if (lv_obj_has_flag(feature_overlay, LV_OBJ_FLAG_HIDDEN)) {
        // A media tap preceding this long press must not fire after opening.
        media_tap_count = 0;
        media_tap_deadline = 0;
        lv_obj_clear_flag(feature_overlay, LV_OBJ_FLAG_HIDDEN);
        lv_obj_move_foreground(feature_overlay);
        overlay_hide_time = current_time + 6000;
        updateTimeDisplay();
        refreshFeatureOverlay();
    } else {
        hideFeatureOverlay();
    }
}

bool touchWithinMenuButton(lv_obj_t *button, uint16_t raw_x, uint16_t raw_y) {
    int bounded_x = constrain((int)raw_x, TOUCH_RAW_TOP, TOUCH_RAW_BOTTOM);
    int bounded_y = constrain((int)raw_y, TOUCH_RAW_SIDE_MIN, TOUCH_RAW_SIDE_MAX);
    int screen_y = (bounded_x - TOUCH_RAW_TOP) * SCREEN_HEIGHT /
                   (TOUCH_RAW_BOTTOM - TOUCH_RAW_TOP);
    int screen_x = (bounded_y - TOUCH_RAW_SIDE_MIN) * SCREEN_WIDTH /
                   (TOUCH_RAW_SIDE_MAX - TOUCH_RAW_SIDE_MIN);
    // Horizontal direction is uncalibrated. Both buttons are centered, so
    // mirroring X gives the same hit result; the real ranges need device test.
    lv_area_t area;
    lv_obj_get_coords(button, &area);
    return screen_x >= area.x1 && screen_x <= area.x2 &&
           screen_y >= area.y1 && screen_y <= area.y2;
}

void selectFeaturePanel() {
    // A menu swipe is consumed. A tap must start and end inside one button.
    if (abs((int)touch_last_x - (int)touch_start_x) >= MEDIA_SWIPE_THRESHOLD ||
        abs((int)touch_last_y - (int)touch_start_y) >= MEDIA_SWIPE_THRESHOLD) return;
    lv_obj_update_layout(feature_overlay);
    bool choose_player;
    if (touchWithinMenuButton(feature_overlay_bongo_button, touch_start_x, touch_start_y) &&
        touchWithinMenuButton(feature_overlay_bongo_button, touch_last_x, touch_last_y)) {
        choose_player = false;
    } else if (touchWithinMenuButton(feature_overlay_player_button, touch_start_x, touch_start_y) &&
               touchWithinMenuButton(feature_overlay_player_button, touch_last_x, touch_last_y)) {
        choose_player = true;
    } else {
        return;
    }
    hideFeatureOverlay();
    if (choose_player && !spotify_screen_active) showMediaScreen();
    if (!choose_player && spotify_screen_active) showBongoScreen();
}

void handleTouchFeature(uint32_t current_time) {
    static uint32_t last_touch_poll = 0;
    if (current_time - last_touch_poll < 15) return;
    last_touch_poll = current_time;

    bool pressed = tft.getTouchRawZ() > TOUCH_PRESSURE_THRESHOLD;

    if (pressed && !touch_is_down) {
        touch_is_down = true;
        touch_long_press_fired = false;
        touch_started_in_menu = feature_overlay &&
                                !lv_obj_has_flag(feature_overlay, LV_OBJ_FLAG_HIDDEN);
        touch_down_time = current_time;
        tft.getTouchRaw(&touch_start_x, &touch_start_y);
        touch_last_x = touch_start_x;
        touch_last_y = touch_start_y;
    } else if (pressed && touch_is_down) {
        tft.getTouchRaw(&touch_last_x, &touch_last_y);
        if (!touch_long_press_fired &&
            current_time - touch_down_time >= TOUCH_LONG_PRESS_MS) {
            touch_long_press_fired = true;
            toggleFeatureOverlay(current_time);
        }
    } else if (!pressed && touch_is_down) {
        uint32_t press_duration = current_time - touch_down_time;
        touch_is_down = false;
        if (!touch_long_press_fired && press_duration >= 35) {
            if (touch_started_in_menu) {
                if (feature_overlay &&
                    !lv_obj_has_flag(feature_overlay, LV_OBJ_FLAG_HIDDEN)) {
                    selectFeaturePanel();
                }
            } else if (spotify_screen_active) {
                int delta_x = (int)touch_last_x - (int)touch_start_x;
                int delta_y = (int)touch_last_y - (int)touch_start_y;
                // The touch controller's raw axes are rotated relative to
                // the landscape display: raw X increasing is a physical
                // swipe down, and raw Y is the physical left/right axis.
                if (delta_x >= MEDIA_SWIPE_THRESHOLD &&
                    abs(delta_x) > abs(delta_y)) {
                    media_tap_count = 0;
                    media_tap_deadline = 0;
                    toggleMediaCatMode();
                } else if (abs(delta_y) >= MEDIA_SWIPE_THRESHOLD &&
                           abs(delta_y) >= abs(delta_x)) {
                    media_tap_count = 0;
                    media_tap_deadline = 0;
                    Serial.println(delta_y > 0 ? "MEDIA_CMD:NEXT"
                                                : "MEDIA_CMD:PREVIOUS");
                } else {
                    queueMediaTap(current_time);
                }
            } else {
                triggerTouchBonk(current_time);
            }
        }
        touch_started_in_menu = false;
    }

    if (overlay_hide_time && current_time >= overlay_hide_time) {
        hideFeatureOverlay();
    }

    if (touch_bonk_active && current_time >= touch_bonk_until) {
        touch_bonk_active = false;
        sprite_manager.is_streak_mode = false;
        sprite_manager_set_state(&sprite_manager, ANIM_STATE_IDLE_STAGE1, current_time);
    }
}

void loop() {
    handleSerialCommands();
    
    uint32_t current_time = millis();
    reportDeviceStatus(current_time);
    handleTouchFeature(current_time);
    serviceMediaTaps(current_time);
    updateMediaProgressClock(current_time);
    updateMediaVinyl(current_time);
    updateMediaCat(current_time);
    
    // Update animations - removed fixed frame rate to prevent conflicts
    static uint32_t last_animation_update = 0;
    if (current_time - last_animation_update >= 10) {  // React quickly to touch and serial state changes
        sprite_manager_update(&sprite_manager, current_time);
        
        // Only render if sprites actually changed to reduce canvas operations
        static uint32_t last_sprite_hash = 0;
        uint32_t current_sprite_hash = 0;
        
        // Calculate simple hash of current sprites to detect changes (optimized)
        for (int i = 0; i < NUM_LAYERS; i++) {
            current_sprite_hash += (uint32_t)sprite_manager.current_sprites[i];
        }
        
        // Only re-render if sprites changed or it's been too long (forced refresh)
        if (current_sprite_hash != last_sprite_hash || (current_time - last_animation_update) > 200) {
            sprite_render_layers(&sprite_manager, cat_canvas, current_time);
            last_sprite_hash = current_sprite_hash;
        }
        
        last_animation_update = current_time;
    }
    
    // Update time display every second
    static uint32_t last_time_update = 0;
    if (current_time - last_time_update >= 1000) {
        updateTimeDisplay();
        refreshFeatureOverlay();
        last_time_update = current_time;
    }
    
    // Reduce LVGL timer handler frequency to prevent system overload
    static uint32_t last_lvgl_update = 0;
    if (current_time - last_lvgl_update >= 5) {  // Flush LVGL invalidations with lower latency
        lv_timer_handler();
        last_lvgl_update = current_time;
    }
    
    delay(2);  // Reduced from 5ms for better responsiveness
} 
