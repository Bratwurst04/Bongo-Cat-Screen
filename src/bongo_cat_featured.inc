#include <lvgl.h>
#include <TFT_eSPI.h>
#include <WiFi.h>
#include <EEPROM.h>
#include <Preferences.h>
#include <esp_freertos_hooks.h>
#include <esp_sleep.h>
#include <driver/rtc_io.h>
#include <mbedtls/base64.h>
#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include "Free_Fonts.h"
#include "animations_sprites.h"
#include "focus_logic.h"
#include "media_art_v2.h"

// Display settings
#define SCREEN_WIDTH 240
#define SCREEN_HEIGHT 320
#define DRAW_BUFFER_ROWS 40
#define TOUCH_PRESSURE_THRESHOLD 350
#define TOUCH_BONK_DURATION_MS 1400
#define MEDIA_MULTI_TAP_WINDOW_MS 320
#define MEDIA_ART_SIZE 112
#define MEDIA_ART_LV_BYTES (MEDIA_ART_SIZE * MEDIA_ART_SIZE * 2)
#define MEDIA_ART_RGB_BYTES (MEDIA_ART_SIZE * MEDIA_ART_SIZE * 3)
#define MEDIA_SWIPE_THRESHOLD 420
#define FOCUS_TAP_MOVE_MAX_RAW 180
#define FOCUS_LED_GREEN_PIN 16  // ESP32-2432S024R RGB green, active low
#define MEDIA_VINYL_FRAME_MS 60
#define MEDIA_VINYL_ANGLE_STEP 18
#define MEDIA_CAT_FRAME_MS 450
#define MEDIA_CAT_ZOOM 672
#define COMPANION_IDLE_MS 600000UL
#define COMPANION_PROBE_MS 8000UL
#define COMPANION_PROBE_GRACE_MS 4000UL
#define COMPANION_PROBE_DRAIN_MS 50UL
#define COMPANION_PROBE_INTERVAL_US 25000000ULL
#define MEDIA_ART_STALL_MS 15000UL
#define MEDIA_ART2_STALL_MS 3000UL
#define MEDIA_ART2_MAX_MS 20000UL
constexpr bool companionIdleExpired(uint32_t now, uint32_t last) {
    return uint32_t(now - last) >= COMPANION_IDLE_MS;
}
static_assert(!companionIdleExpired(599999, 0), "companion idle boundary");
static_assert(companionIdleExpired(600000, 0), "companion idle boundary");
static_assert(COMPANION_PROBE_INTERVAL_US / 1000 + COMPANION_PROBE_MS +
                  MEDIA_ART_STALL_MS + COMPANION_PROBE_GRACE_MS < 60000,
              "timer probe must fit within the wake target");
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
uint32_t last_companion_stats_ms = 0;  // Independent of the cat's idle stages
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
lv_obj_t * feature_overlay_backdrop = NULL;
lv_obj_t * feature_overlay_label = NULL;
lv_obj_t * feature_overlay_bongo_button = NULL;
lv_obj_t * feature_overlay_player_button = NULL;
lv_obj_t * feature_overlay_focus_button = NULL;
lv_obj_t * feature_overlay_settings_button = NULL;
lv_obj_t * feature_overlay_bongo_label = NULL;
lv_obj_t * feature_overlay_player_label = NULL;
lv_obj_t * feature_overlay_focus_label = NULL;
lv_obj_t * feature_overlay_settings_label = NULL;
lv_obj_t * feature_overlay_hint_label = NULL;
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
lv_obj_t *touch_feedback_button = NULL;
bool touch_button_cancelled = false;
PanelId touch_start_panel = PanelId::Bongo;
bool touch_start_times_open = false;

// Bongo DJ / Windows media screen. Artwork arrives as RGB888 so the ESP32 can
// convert through LVGL itself without any controller-specific byte ordering.
lv_obj_t * media_screen = NULL;
lv_obj_t * media_art_box = NULL;
lv_obj_t * media_art_image = NULL;
lv_obj_t * media_source_label = NULL;
lv_obj_t * media_brand_label = NULL;
lv_obj_t * media_playback_status_label = NULL;
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
uint32_t media_art_last_byte_ms = 0;
uint8_t media_art_rgb_triplet[3] = {0, 0, 0};
uint8_t media_art_rgb_triplet_used = 0;
bool media_art_valid = false;
MediaArtV2Transfer media_art_v2(MEDIA_ART_RGB_BYTES);
uint32_t media_art_v2_started_ms = 0;
uint32_t media_art_v2_last_chunk_ms = 0;
PanelId active_panel = PanelId::Bongo;
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

// Only selected durations persist; the active cycle is volatile.
FocusDurations focus_durations = focusDefaultDurations();
FocusDurations focus_draft_durations = focusDefaultDurations();
FocusUiSettings focus_ui_settings = focusDefaultUiSettings();
FocusState focus_state = focusInitial();
lv_obj_t * focus_screen = NULL;
lv_obj_t * focus_progress_ring = NULL;
lv_obj_t * focus_phase_label = NULL;
lv_obj_t * focus_time_label = NULL;
lv_obj_t * focus_status_label = NULL;
lv_obj_t * focus_next_label = NULL;
lv_obj_t * focus_start_button = NULL;
lv_obj_t * focus_start_label = NULL;
lv_obj_t * focus_reset_button = NULL;
lv_obj_t * focus_settings_button = NULL;
lv_obj_t * focus_settings_screen = NULL;
lv_obj_t * focus_settings_heading = NULL;
lv_obj_t * focus_settings_focus_card = NULL;
lv_obj_t * focus_settings_break_card = NULL;
lv_obj_t * focus_settings_focus_label = NULL;
lv_obj_t * focus_settings_break_label = NULL;
lv_obj_t * focus_settings_info_label = NULL;
lv_obj_t * focus_settings_focus_minus = NULL;
lv_obj_t * focus_settings_focus_plus = NULL;
lv_obj_t * focus_settings_break_minus = NULL;
lv_obj_t * focus_settings_break_plus = NULL;
lv_obj_t * focus_settings_save = NULL;
bool focus_settings_open = false;
lv_obj_t * local_settings_screen = NULL;
lv_obj_t * local_settings_heading = NULL;
lv_obj_t * local_settings_theme_button = NULL;
lv_obj_t * local_settings_auto_button = NULL;
lv_obj_t * local_settings_led_button = NULL;
lv_obj_t * local_settings_back_button = NULL;
lv_obj_t * local_settings_theme_label = NULL;
lv_obj_t * local_settings_auto_label = NULL;
lv_obj_t * local_settings_led_label = NULL;
lv_obj_t * local_settings_info_label = NULL;
PanelId panel_before_settings = PanelId::Bongo;
lv_obj_t * focus_completion_banner = NULL;
lv_obj_t * focus_completion_label = NULL;
lv_obj_t * focus_completion_sub_label = NULL;
int32_t focus_last_display_seconds = -1;
int32_t focus_last_progress = -1;
FocusMode focus_last_display_mode = FocusMode::Completed;
FocusPhase focus_last_display_phase = FocusPhase::Break;
FocusCueState focus_cue = focusCueInitial();
bool focus_banner_visible = false;
bool focus_banner_compact = false;
FocusCueKind focus_banner_kind = FocusCueKind::None;
PanelId focus_banner_panel = PanelId::Bongo;
bool focus_led_on = false;

void focusLedOff() {
    // Preload the inactive HIGH level before enabling the output. During reset
    // the pad floats high through the LED to 3.3 V on this active-low board.
    digitalWrite(FOCUS_LED_GREEN_PIN, HIGH);
    pinMode(FOCUS_LED_GREEN_PIN, OUTPUT);
    focus_led_on = false;
}

void driveFocusLed(bool on) {
    if (focus_led_on == on) return;
    digitalWrite(FOCUS_LED_GREEN_PIN, on ? LOW : HIGH);
    focus_led_on = on;
}

FocusDurations loadFocusDurations() {
    Preferences prefs;
    if (!prefs.begin("bongofocus", true)) return focusDefaultDurations();
    uint32_t packed = prefs.getUInt("durations",
                                   focusPackDurations(focusDefaultDurations()));
    prefs.end();
    return focusDurationsFromPacked(packed);
}

bool saveFocusDurations(FocusDurations values) {
    if (!focusDurationsValid(values)) return false;
    Preferences prefs;
    if (!prefs.begin("bongofocus", false)) return false;
    bool saved = prefs.putUInt("durations", focusPackDurations(values)) ==
                 sizeof(uint32_t);
    prefs.end();
    return saved;
}

FocusUiSettings loadFocusUiSettings() {
    Preferences prefs;
    if (!prefs.begin("bongofocus", true)) return focusDefaultUiSettings();
    uint32_t packed = prefs.getUInt("ui", focusPackUiSettings(focusDefaultUiSettings()));
    prefs.end();
    return focusUiSettingsFromPacked(packed);
}

bool saveFocusUiSettings(FocusUiSettings values) {
    if (!focusUiSettingsValid(values)) return false;
    Preferences prefs;
    if (!prefs.begin("bongofocus", false)) return false;
    bool saved = prefs.putUInt("ui", focusPackUiSettings(values)) == sizeof(uint32_t);
    prefs.end();
    return saved;
}

// Stats data
int cpu_usage = 0;
int ram_usage = 0;
int wpm_speed = 0;
String current_time_str = "00:00";
bool time_initialized = false;  // Track if we've received time from Python

uint32_t focusAccentHex() {
    switch (focus_ui_settings.theme) {
        case AccentTheme::Cyan: return 0x26D4E4;
        case AccentTheme::Amber: return 0xFFC14D;
        default: return 0x1ED760;
    }
}

uint32_t focusDarkAccentHex() {
    switch (focus_ui_settings.theme) {
        case AccentTheme::Cyan: return 0x15343A;
        case AccentTheme::Amber: return 0x3B2F1C;
        default: return 0x1B3025;
    }
}

uint32_t focusPressedHex() {
    switch (focus_ui_settings.theme) {
        case AccentTheme::Cyan: return 0x285E66;
        case AccentTheme::Amber: return 0x66502D;
        default: return 0x2E6140;
    }
}

void refreshFeatureOverlay() {
    if (!feature_overlay || lv_obj_has_flag(feature_overlay, LV_OBJ_FLAG_HIDDEN)) return;
    lv_obj_t *buttons[] = {feature_overlay_bongo_button,
                           feature_overlay_player_button,
                           feature_overlay_focus_button,
                           feature_overlay_settings_button};
    lv_obj_t *labels[] = {feature_overlay_bongo_label,
                          feature_overlay_player_label,
                          feature_overlay_focus_label,
                          feature_overlay_settings_label};
    const char *names[] = {"BONGO", "SPELARE", "FOKUS", "INSTALLNINGAR"};
    for (uint8_t i = 0; i < 4; ++i) {
        bool active = static_cast<uint8_t>(active_panel) == i;
        lv_obj_t *button = buttons[i];
        lv_obj_set_style_bg_color(button,
                                  lv_color_hex(active ? focusDarkAccentHex() : 0x171A1F), 0);
        lv_obj_set_style_border_color(button,
                                      lv_color_hex(active ? focusAccentHex() : 0x4C555D), 0);
        lv_obj_set_style_border_width(button, active ? 2 : 1, 0);
        lv_obj_set_style_text_color(labels[i],
                                    active ? lv_color_hex(focusAccentHex()) : lv_color_white(), 0);
        lv_label_set_text_fmt(labels[i], "%s%s", names[i], active ? "  AKTIV" : "");
    }
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
            media_art_last_byte_ms = millis();
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
    } else if (millis() - media_art_last_byte_ms >= MEDIA_ART_STALL_MS) {
        // A broken upload must not prevent the ten-minute power timeout forever.
        media_art_receiving = false;
        Serial.println("MEDIA_ART_ERROR");
    }
    return true;
}

bool parseMediaArt2Number(const String &text, uint32_t *value, int base = 10) {
    if (text.length() == 0 || text.length() > 10) return false;
    for (size_t index = 0; index < text.length(); ++index) {
        char ch = text[index];
        if (base == 10 && (ch < '0' || ch > '9')) return false;
        if (base == 16 && !isxdigit(static_cast<unsigned char>(ch))) return false;
    }
    char *end = nullptr;
    unsigned long parsed = strtoul(text.c_str(), &end, base);
    if (!end || *end != '\0') return false;
    *value = static_cast<uint32_t>(parsed);
    return true;
}

void failMediaArt2(uint16_t id) {
    media_art_v2.abort();
    Serial.printf("MEDIA_ART2_ERROR:%u\n", id);
}

void serviceMediaArt2Timeout(uint32_t now) {
    if (media_art_v2.active &&
        (now - media_art_v2_last_chunk_ms >= MEDIA_ART2_STALL_MS ||
         now - media_art_v2_started_ms >= MEDIA_ART2_MAX_MS)) {
        failMediaArt2(media_art_v2.id);
    }
}

bool handleMediaArt2Command(const String &command, uint32_t now) {
    if (!command.startsWith("MEDIA_ART2_")) return false;
    if (command.length() > 225) {
        if (media_art_v2.active) failMediaArt2(media_art_v2.id);
        return true;
    }
    if (command.startsWith("MEDIA_ART2_BEGIN:")) {
        String args = command.substring(17);
        String fields[5];
        int start = 0;
        for (int index = 0; index < 4; ++index) {
            int separator = args.indexOf(':', start);
            if (separator < 0) return true;
            fields[index] = args.substring(start, separator);
            start = separator + 1;
        }
        fields[4] = args.substring(start);
        uint32_t id, width, height, length, crc;
        if (!parseMediaArt2Number(fields[0], &id) ||
            !parseMediaArt2Number(fields[1], &width) ||
            !parseMediaArt2Number(fields[2], &height) ||
            !parseMediaArt2Number(fields[3], &length) ||
            fields[4].length() != 8 ||
            !parseMediaArt2Number(fields[4], &crc, 16) ||
            id == 0 || id > UINT16_MAX || width != MEDIA_ART_SIZE ||
            height != MEDIA_ART_SIZE || length != MEDIA_ART_RGB_BYTES) return true;
        media_art_receiving = false;
        media_art_v2.begin(static_cast<uint16_t>(id), length, crc);
        media_art_receiving_buffer = 1 - media_art_active_buffer;
        media_art_pixels_received = 0;
        media_art_rgb_triplet_used = 0;
        media_art_v2_started_ms = now;
        media_art_v2_last_chunk_ms = now;
        return true;
    }
    if (command.startsWith("MEDIA_ART2_CHUNK:")) {
        String args = command.substring(17);
        int first = args.indexOf(':');
        int second = first < 0 ? -1 : args.indexOf(':', first + 1);
        uint32_t id, offset;
        if (second < 0 ||
            !parseMediaArt2Number(args.substring(0, first), &id) ||
            !parseMediaArt2Number(args.substring(first + 1, second), &offset) ||
            id == 0 || id > UINT16_MAX ||
            !media_art_v2.active || id != media_art_v2.id) return true;
        const char *encoded = args.c_str() + second + 1;
        size_t encoded_length = args.length() - second - 1;
        uint8_t bytes[128];
        size_t decoded = 0;
        if (encoded_length != 172 ||
            mbedtls_base64_decode(bytes, sizeof(bytes), &decoded,
                                  reinterpret_cast<const unsigned char *>(encoded),
                                  encoded_length) != 0 ||
            decoded != sizeof(bytes) ||
            !media_art_v2.accept(static_cast<uint16_t>(id), offset, bytes, decoded)) {
            failMediaArt2(static_cast<uint16_t>(id));
            return true;
        }
        media_art_v2_last_chunk_ms = now;
        for (size_t index = 0; index < decoded; ++index) {
            media_art_rgb_triplet[media_art_rgb_triplet_used++] = bytes[index];
            if (media_art_rgb_triplet_used == 3) {
                if (media_art_pixels_received < MEDIA_ART_SIZE * MEDIA_ART_SIZE) {
                    media_art_buffers[media_art_receiving_buffer]
                                     [media_art_pixels_received++] = lv_color_make(
                        media_art_rgb_triplet[0], media_art_rgb_triplet[1],
                        media_art_rgb_triplet[2]);
                }
                media_art_rgb_triplet_used = 0;
            }
        }
        return true;
    }
    if (command.startsWith("MEDIA_ART2_END:")) {
        uint32_t id;
        if (!parseMediaArt2Number(command.substring(15), &id) ||
            id == 0 || id > UINT16_MAX) return true;
        if (media_art_v2.active && id == media_art_v2.id) {
            if (media_art_v2.complete(static_cast<uint16_t>(id)) &&
                media_art_pixels_received == MEDIA_ART_SIZE * MEDIA_ART_SIZE &&
                media_art_rgb_triplet_used == 0) {
                media_art_v2.abort();
                activateMediaArtwork(media_art_receiving_buffer, false);
                Serial.printf("MEDIA_ART2_OK:%u\n", static_cast<unsigned int>(id));
            } else {
                failMediaArt2(static_cast<uint16_t>(id));
            }
        }
        return true;
    }
    if (command.startsWith("MEDIA_ART2_ABORT:")) {
        uint32_t id;
        if (parseMediaArt2Number(command.substring(17), &id) &&
            media_art_v2.active && id == media_art_v2.id) {
            media_art_v2.abort();
        }
        return true;
    }
    return true;
}

void updateMediaVinyl(uint32_t current_time) {
    if (active_panel != PanelId::Player || media_cat_mode || !media_art_valid || !media_is_playing ||
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
    if (active_panel != PanelId::Player || !media_cat_mode || !media_cat_canvas) return;
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

bool parseCompanionStats(const String &command, int *cpu, int *ram, int *wpm) {
    int parsed_length = -1;
    float cpu_percent;
    // The existing companion sends CPU with one decimal place. Keep the
    // display's integer value while validating the complete wire packet.
    if (sscanf(command.c_str(), "STATS:CPU:%f,RAM:%d,WPM:%d%n",
               &cpu_percent, ram, wpm, &parsed_length) != 3 ||
        parsed_length != (int)command.length()) return false;
    if (!isfinite(cpu_percent) || cpu_percent < 0 || cpu_percent > 100 ||
        *ram < 0 || *ram > 100 || *wpm < 0 || *wpm > 2000) return false;
    *cpu = (int)cpu_percent;
    return true;
}

// Hold the active-high backlight low across deep sleep and timer resets. GPIO27
// is an RTC-capable pad on this ESP32 board.
void holdBacklightOff() {
    digitalWrite(TFT_BL, LOW);
    pinMode(TFT_BL, OUTPUT);
    rtc_gpio_init(GPIO_NUM_27);
    rtc_gpio_set_level(GPIO_NUM_27, 0);
    rtc_gpio_set_direction(GPIO_NUM_27, RTC_GPIO_MODE_OUTPUT_ONLY);
    rtc_gpio_hold_en(GPIO_NUM_27);
}

void releaseBacklightHold() {
    // TFT_eSPI sets TFT_BL high in init(). Prepare both muxes at LOW before
    // releasing the RTC latch so its library write cannot flash the panel.
    digitalWrite(TFT_BL, LOW);
    rtc_gpio_set_level(GPIO_NUM_27, 0);
    rtc_gpio_hold_dis(GPIO_NUM_27);
    rtc_gpio_deinit(GPIO_NUM_27);
    pinMode(TFT_BL, OUTPUT);
    digitalWrite(TFT_BL, LOW);
}

void enterCompanionDeepSleep(bool display_initialized) {
    focus_cue = focusCueInitial();
    focusLedOff();
    if (focus_completion_banner) {
        lv_obj_add_flag(focus_completion_banner, LV_OBJ_FLAG_HIDDEN);
        focus_banner_visible = false;
    }
    digitalWrite(TFT_BL, LOW);
    if (display_initialized) {
        // ILI9341 Display OFF followed by Sleep IN. The backlight is already
        // electrically off while the controller finishes entering sleep.
        tft.writecommand(0x28);
        delay(20);
        tft.writecommand(0x10);
        delay(120);
        if (Serial.available()) {
            // A new packet arrived while the controller entered sleep. Keep
            // the UART session and restore the LCD instead of discarding it.
            tft.writecommand(0x11);
            delay(120);
            tft.writecommand(0x29);
            digitalWrite(TFT_BL, HIGH);
            return;
        }
    }
    holdBacklightOff();
    esp_sleep_enable_timer_wakeup(COMPANION_PROBE_INTERVAL_US);
    esp_deep_sleep_start();
}

bool probeForCompanion() {
    uint32_t started = millis();
    uint32_t first_stats_ms = 0;
    bool saw_first_stats = false;
    size_t artwork_bytes_left = 0;
    uint32_t artwork_last_byte_ms = 0;
    String line;
    line.reserve(96);
    while (millis() - started < COMPANION_PROBE_MS ||
           (saw_first_stats &&
            millis() - first_stats_ms < COMPANION_PROBE_GRACE_MS) ||
           (artwork_bytes_left &&
            millis() - artwork_last_byte_ms < MEDIA_ART_STALL_MS) ||
           (artwork_last_byte_ms &&
            millis() - artwork_last_byte_ms < COMPANION_PROBE_GRACE_MS) ||
           (Serial.available() &&
            millis() - started < COMPANION_PROBE_MS + COMPANION_PROBE_DRAIN_MS)) {
        while (Serial.available()) {
            int incoming = Serial.read();
            if (artwork_bytes_left) {
                --artwork_bytes_left;
                artwork_last_byte_ms = millis();
                continue;
            }
            if (incoming == '\n') {
                line.trim();
                if (line == "PING") Serial.println("PONG");
                if (line == "MEDIA_ART_RGB:112:112:37632") {
                    artwork_bytes_left = MEDIA_ART_RGB_BYTES;
                    artwork_last_byte_ms = millis();
                }
                int cpu, ram, wpm;
                if (parseCompanionStats(line, &cpu, &ram, &wpm)) {
                    uint32_t now = millis();
                    if (saw_first_stats && now - first_stats_ms >= 1000) {
                        return true;
                    }
                    if (!saw_first_stats) {
                        saw_first_stats = true;
                        first_stats_ms = now;
                    }
                }
                line = "";
            } else if (incoming >= 32 && incoming <= 126 && line.length() < 95) {
                line += (char)incoming;
            } else {
                line = "";
            }
        }
        delay(5);
    }
    return false;
}

// Handle serial commands from Python script
void handleSerialCommands() {
    serviceMediaArt2Timeout(millis());
    if (serviceMediaArtworkReceive()) return;
    if (Serial.available()) {
        String command = Serial.readStringUntil('\n');
        command.trim();
        
        uint32_t current_time = millis();
        last_command_time = current_time;  // Update command timestamp
        python_control_mode = true;        // Ensure Python control is active

        if (handleMediaArt2Command(command, current_time)) return;
        
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
            bool next_playing = state == "PLAYING";
            // A periodic repeat of PLAYING must not discard the fractional
            // second already accumulated by the local progress clock.
            if (media_is_playing != next_playing) {
                media_position_anchor_ms = current_time;
            }
            media_is_playing = next_playing;
            media_has_track = state != "NONE";
            if (state == "NONE") {
                media_art_v2.abort();
                loadGenericVinyl();
            }
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
                media_art_v2.abort();
                media_art_receiving_buffer = 1 - media_art_active_buffer;
                media_art_expected = incoming_size;
                media_art_received = 0;
                media_art_pixels_received = 0;
                media_art_rgb_triplet_used = 0;
                media_art_last_byte_ms = current_time;
                media_art_receiving = true;
            }
        } else if (command == "MEDIA_ART_DEFAULT") {
            media_art_v2.abort();
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
            int cpu, ram, wpm;
            if (parseCompanionStats(command, &cpu, &ram, &wpm)) {
                last_companion_stats_ms = current_time;
                updateSystemStats(cpu, ram, wpm);
            }
            
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
        } else if (command.startsWith("CAPS?:")) {
            String challenge = command.substring(6);
            bool valid = challenge.length() == 16;
            for (size_t index = 0; valid && index < challenge.length(); ++index) {
                valid = isxdigit(static_cast<unsigned char>(challenge[index]));
            }
            if (valid) Serial.println("CAPS:MEDIA_ART2:" + challenge);
            
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
    // On every reset, including timer wakeups, keep the backlight dark until
    // fresh companion traffic has been proved and the first frame is drawn.
    focusLedOff();
    holdBacklightOff();
    // Covers arrive over the same UART as commands. Keep enough headroom for
    // a chunk while LVGL is rendering a frame, otherwise one lost RGB byte
    // shifts the remaining image into a scrambled pattern.
    Serial.setRxBufferSize(8192);
#ifndef BONGO_SERIAL_BAUD
#define BONGO_SERIAL_BAUD 115200
#endif
    Serial.begin(BONGO_SERIAL_BAUD);
    Serial.setTimeout(10);
    if (!probeForCompanion()) enterCompanionDeepSleep(false);
    last_companion_stats_ms = millis();
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
    focus_durations = loadFocusDurations();
    focus_ui_settings = loadFocusUiSettings();
    focus_state = focusInitial(focus_durations);
    
    // Initialize random seed for animations
    randomSeed(analogRead(0));
    
    tft.init();
    tft.setRotation(0);
    tft.fillScreen(TFT_BLACK);
    
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
    createFocusScreen();
    createFocusSettingsScreen();
    createLocalSettingsScreen();
    refreshAccentTheme();
    
    // Apply loaded settings to display visibility now that UI is created
    updateDisplayVisibility();

    lv_timer_handler();
    releaseBacklightHold();
    digitalWrite(TFT_BL, HIGH);
    // A reset loses RAM state, including the cover. The companion resends its
    // current snapshot and cached artwork without waiting for a song change.
    Serial.println("SYNC_REQUEST");
    
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
    // Cover the full display behind the centered menu so edge controls from
    // the active panel cannot peek through above or beside it.
    feature_overlay_backdrop = lv_obj_create(lv_layer_top());
    lv_obj_set_pos(feature_overlay_backdrop, 0, 0);
    lv_obj_set_size(feature_overlay_backdrop, SCREEN_WIDTH, SCREEN_HEIGHT);
    lv_obj_set_style_bg_color(feature_overlay_backdrop, lv_color_hex(0x101419), 0);
    lv_obj_set_style_bg_opa(feature_overlay_backdrop, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(feature_overlay_backdrop, 0, 0);
    lv_obj_set_style_pad_all(feature_overlay_backdrop, 0, 0);
    lv_obj_clear_flag(feature_overlay_backdrop, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_clear_flag(feature_overlay_backdrop, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(feature_overlay_backdrop, LV_OBJ_FLAG_HIDDEN);

    feature_overlay = lv_obj_create(lv_layer_top());
    lv_obj_set_size(feature_overlay, 220, 304);
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
    lv_obj_set_pos(feature_overlay_bongo_button, 0, 27);
    lv_obj_set_size(feature_overlay_bongo_button, 196, 50);
    lv_obj_set_style_bg_opa(feature_overlay_bongo_button, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(feature_overlay_bongo_button, 10, 0);
    lv_obj_set_style_pad_all(feature_overlay_bongo_button, 0, 0);
    lv_obj_clear_flag(feature_overlay_bongo_button, LV_OBJ_FLAG_SCROLLABLE);
    feature_overlay_bongo_label = lv_label_create(feature_overlay_bongo_button);
    lv_obj_set_style_text_font(feature_overlay_bongo_label, &lv_font_montserrat_14, 0);
    lv_label_set_text(feature_overlay_bongo_label, "BONGO  AKTIV");
    lv_obj_center(feature_overlay_bongo_label);

    feature_overlay_player_button = lv_obj_create(feature_overlay);
    lv_obj_set_pos(feature_overlay_player_button, 0, 88);
    lv_obj_set_size(feature_overlay_player_button, 196, 50);
    lv_obj_set_style_bg_opa(feature_overlay_player_button, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(feature_overlay_player_button, 10, 0);
    lv_obj_set_style_pad_all(feature_overlay_player_button, 0, 0);
    lv_obj_clear_flag(feature_overlay_player_button, LV_OBJ_FLAG_SCROLLABLE);
    feature_overlay_player_label = lv_label_create(feature_overlay_player_button);
    lv_obj_set_style_text_font(feature_overlay_player_label, &lv_font_montserrat_14, 0);
    lv_label_set_text(feature_overlay_player_label, "SPELARE");
    lv_obj_center(feature_overlay_player_label);

    feature_overlay_focus_button = lv_obj_create(feature_overlay);
    lv_obj_set_pos(feature_overlay_focus_button, 0, 149);
    lv_obj_set_size(feature_overlay_focus_button, 196, 50);
    lv_obj_set_style_bg_opa(feature_overlay_focus_button, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(feature_overlay_focus_button, 10, 0);
    lv_obj_set_style_pad_all(feature_overlay_focus_button, 0, 0);
    lv_obj_clear_flag(feature_overlay_focus_button, LV_OBJ_FLAG_SCROLLABLE);
    feature_overlay_focus_label = lv_label_create(feature_overlay_focus_button);
    lv_obj_set_style_text_font(feature_overlay_focus_label, &lv_font_montserrat_14, 0);
    lv_label_set_text(feature_overlay_focus_label, "FOKUS");
    lv_obj_center(feature_overlay_focus_label);

    feature_overlay_settings_button = lv_obj_create(feature_overlay);
    lv_obj_set_pos(feature_overlay_settings_button, 0, 210);
    lv_obj_set_size(feature_overlay_settings_button, 196, 50);
    lv_obj_set_style_bg_opa(feature_overlay_settings_button, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(feature_overlay_settings_button, 10, 0);
    lv_obj_set_style_pad_all(feature_overlay_settings_button, 0, 0);
    lv_obj_clear_flag(feature_overlay_settings_button, LV_OBJ_FLAG_SCROLLABLE);
    feature_overlay_settings_label = lv_label_create(feature_overlay_settings_button);
    lv_obj_set_style_text_font(feature_overlay_settings_label, &lv_font_montserrat_14, 0);
    lv_label_set_text(feature_overlay_settings_label, "INSTALLNINGAR");
    lv_obj_center(feature_overlay_settings_label);

    feature_overlay_hint_label = lv_label_create(feature_overlay);
    lv_obj_set_width(feature_overlay_hint_label, 196);
    lv_obj_set_style_text_font(feature_overlay_hint_label, &lv_font_montserrat_10, 0);
    lv_obj_set_style_text_color(feature_overlay_hint_label, lv_color_hex(0xD5D9DE), 0);
    lv_obj_set_style_text_align(feature_overlay_hint_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_label_set_text(feature_overlay_hint_label, "HOLD  CLOSE");
    lv_obj_set_pos(feature_overlay_hint_label, 0, 269);
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

    media_brand_label = lv_label_create(media_screen);
    lv_label_set_text(media_brand_label, "BONGO DJ");
    lv_obj_set_style_text_font(media_brand_label, &lv_font_montserrat_10, 0);
    lv_obj_set_style_text_color(media_brand_label, lv_color_hex(0x1ED760), 0);
    lv_obj_set_pos(media_brand_label, 10, 4);

    media_source_label = lv_label_create(media_screen);
    lv_label_set_text(media_source_label, "WINDOWS");
    lv_obj_set_style_text_font(media_source_label, &lv_font_montserrat_10, 0);
    lv_obj_set_style_text_color(media_source_label, lv_color_hex(0xD5D9DE), 0);
    lv_obj_align(media_source_label, LV_ALIGN_TOP_RIGHT, -10, 4);

    media_art_box = lv_obj_create(media_screen);
    lv_obj_set_pos(media_art_box, 34, 26);
    lv_obj_set_size(media_art_box, 172, 172);
    lv_obj_set_style_bg_color(media_art_box, lv_color_hex(0x080A0C), 0);
    lv_obj_set_style_bg_opa(media_art_box, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(media_art_box, 1, 0);
    lv_obj_set_style_border_color(media_art_box, lv_color_hex(0x252A30), 0);
    lv_obj_set_style_radius(media_art_box, 86, 0);
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
    lv_obj_set_pos(info_panel, 8, 205);
    lv_obj_set_size(info_panel, 224, 90);
    lv_obj_set_style_bg_color(info_panel, lv_color_hex(0x15191E), 0);
    lv_obj_set_style_bg_opa(info_panel, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(info_panel, 1, 0);
    lv_obj_set_style_border_color(info_panel, lv_color_hex(0x292E35), 0);
    lv_obj_set_style_radius(info_panel, 10, 0);
    lv_obj_set_style_pad_all(info_panel, 0, 0);
    lv_obj_clear_flag(info_panel, LV_OBJ_FLAG_SCROLLABLE);

    media_title_label = lv_label_create(info_panel);
    lv_label_set_text(media_title_label, "Nothing playing");
    lv_obj_set_pos(media_title_label, 10, 7);
    lv_obj_set_width(media_title_label, 204);
    lv_label_set_long_mode(media_title_label, LV_LABEL_LONG_SCROLL_CIRCULAR);
    lv_obj_set_style_text_font(media_title_label, &lv_font_montserrat_16, 0);
    lv_obj_set_style_text_color(media_title_label, lv_color_hex(0xFFFFFF), 0);

    media_artist_label = lv_label_create(info_panel);
    lv_label_set_text(media_artist_label, "Start Spotify on this PC");
    lv_obj_set_pos(media_artist_label, 10, 32);
    lv_obj_set_width(media_artist_label, 204);
    lv_label_set_long_mode(media_artist_label, LV_LABEL_LONG_SCROLL_CIRCULAR);
    lv_obj_set_style_text_font(media_artist_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(media_artist_label, lv_color_hex(0xD7DBE0), 0);

    media_progress_bar = lv_bar_create(info_panel);
    lv_obj_set_pos(media_progress_bar, 10, 58);
    lv_obj_set_size(media_progress_bar, 204, 6);
    lv_bar_set_range(media_progress_bar, 0, 1000);
    lv_bar_set_value(media_progress_bar, 0, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(media_progress_bar, lv_color_hex(0x343940), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(media_progress_bar, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_bg_color(media_progress_bar, lv_color_hex(0x1ED760), LV_PART_INDICATOR);
    lv_obj_set_style_radius(media_progress_bar, 3, LV_PART_MAIN);
    lv_obj_set_style_radius(media_progress_bar, 3, LV_PART_INDICATOR);

    media_elapsed_label = lv_label_create(info_panel);
    lv_label_set_text(media_elapsed_label, "0:00");
    lv_obj_set_pos(media_elapsed_label, 10, 72);
    media_duration_label = lv_label_create(info_panel);
    lv_label_set_text(media_duration_label, "0:00");
    lv_obj_align(media_duration_label, LV_ALIGN_TOP_RIGHT, -10, 72);
    for (lv_obj_t *time_label_item : {media_elapsed_label, media_duration_label}) {
        lv_obj_set_style_text_font(time_label_item, &lv_font_montserrat_10, 0);
        lv_obj_set_style_text_color(time_label_item, lv_color_hex(0xC7CCD2), 0);
    }

    media_playback_status_label = lv_label_create(media_screen);
    lv_label_set_text(media_playback_status_label, "NO MEDIA");
    lv_obj_set_width(media_playback_status_label, 224);
    lv_obj_set_style_text_font(media_playback_status_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(media_playback_status_label, lv_color_hex(0x1ED760), 0);
    lv_obj_set_style_text_align(media_playback_status_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_pos(media_playback_status_label, 8, 300);

    loadGenericVinyl();
    refreshMediaUi();
}

void refreshFocusUi(bool force = false) {
    if (!focus_time_label ||
        ((active_panel != PanelId::Focus || focus_settings_open) && !force)) return;
    int32_t seconds = (int32_t)focusDisplaySeconds(focus_state);
    int32_t progress = (int32_t)focusProgressPermille(focus_state);
    if (!force && seconds == focus_last_display_seconds &&
        focus_state.mode == focus_last_display_mode &&
        focus_state.phase == focus_last_display_phase &&
        progress == focus_last_progress) return;
    focus_last_display_seconds = seconds;
    if (progress != focus_last_progress || force) {
        lv_arc_set_value(focus_progress_ring, progress);
        focus_last_progress = progress;
    }
    focus_last_display_mode = focus_state.mode;
    focus_last_display_phase = focus_state.phase;
    lv_label_set_text(focus_phase_label,
                      focus_state.phase == FocusPhase::Focus ? "FOKUS" : "PAUS");
    lv_label_set_text_fmt(focus_time_label, "%02ld:%02ld",
                          (long)(seconds / 60), (long)(seconds % 60));
    const char *status = focus_state.mode == FocusMode::Completed ? "PAUS KLAR" :
                         focus_state.phase == FocusPhase::Break ?
                             (focus_state.mode == FocusMode::Running ? "PAUS AKTIV" :
                                                                      "PAUS PAUSAD") :
                         focus_state.mode == FocusMode::Running ? "FOKUS AKTIV" :
                         focus_state.mode == FocusMode::Paused ? "FOKUS PAUSAD" :
                                                                  "REDO FOR FOKUS";
    lv_label_set_text(focus_status_label, status);
    lv_obj_set_style_text_font(focus_status_label,
                               focus_state.mode == FocusMode::Completed ?
                                   &lv_font_montserrat_20 : &lv_font_montserrat_14, 0);
    lv_label_set_text(focus_start_label,
                      focus_state.mode == FocusMode::Running ? "PAUS" :
                      focus_state.mode == FocusMode::Completed ? "START FOKUS" : "START");
    lv_label_set_text_fmt(focus_next_label, "VALT %u / %u MIN",
                          unsigned(focus_durations.focus_minutes),
                          unsigned(focus_durations.break_minutes));
}

void createFocusScreen() {
    focus_screen = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(focus_screen, lv_color_hex(0x101419), 0);
    lv_obj_set_style_bg_opa(focus_screen, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(focus_screen, 0, 0);
    lv_obj_set_style_pad_all(focus_screen, 0, 0);
    lv_obj_clear_flag(focus_screen, LV_OBJ_FLAG_SCROLLABLE);

    focus_progress_ring = lv_arc_create(focus_screen);
    lv_obj_set_pos(focus_progress_ring, 43, 53);
    lv_obj_set_size(focus_progress_ring, 154, 154);
    lv_arc_set_rotation(focus_progress_ring, 270);
    lv_arc_set_bg_angles(focus_progress_ring, 0, 360);
    lv_arc_set_range(focus_progress_ring, 0, 1000);
    lv_arc_set_value(focus_progress_ring, 0);
    lv_obj_set_style_bg_opa(focus_progress_ring, LV_OPA_TRANSP, 0);
    lv_obj_set_style_arc_color(focus_progress_ring, lv_color_hex(0x303A42), LV_PART_MAIN);
    lv_obj_set_style_arc_width(focus_progress_ring, 5, LV_PART_MAIN);
    lv_obj_set_style_arc_width(focus_progress_ring, 6, LV_PART_INDICATOR);
    lv_obj_set_style_bg_opa(focus_progress_ring, LV_OPA_TRANSP, LV_PART_KNOB);
    lv_obj_clear_flag(focus_progress_ring, LV_OBJ_FLAG_CLICKABLE);

    focus_phase_label = lv_label_create(focus_screen);
    lv_obj_set_style_text_font(focus_phase_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(focus_phase_label, lv_color_hex(0x1ED760), 0);
    lv_label_set_text(focus_phase_label, "FOKUS");
    lv_obj_set_pos(focus_phase_label, 12, 12);

    focus_time_label = lv_label_create(focus_screen);
    lv_obj_set_size(focus_time_label, 224, 60);
    lv_obj_set_style_text_font(focus_time_label, &lv_font_montserrat_40, 0);
    lv_obj_set_style_text_color(focus_time_label, lv_color_white(), 0);
    lv_obj_set_style_text_align(focus_time_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(focus_time_label, LV_ALIGN_TOP_MID, 0, 102);

    focus_status_label = lv_label_create(focus_screen);
    lv_obj_set_width(focus_status_label, 220);
    lv_obj_set_style_text_font(focus_status_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(focus_status_label, lv_color_hex(0x1ED760), 0);
    lv_obj_set_style_text_align(focus_status_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(focus_status_label, LV_ALIGN_TOP_MID, 0, 208);

    focus_start_button = lv_obj_create(focus_screen);
    lv_obj_set_pos(focus_start_button, 22, 229);
    lv_obj_set_size(focus_start_button, 196, 44);
    lv_obj_set_style_bg_color(focus_start_button, lv_color_hex(0x1B3025), 0);
    lv_obj_set_style_border_color(focus_start_button, lv_color_hex(0x1ED760), 0);
    lv_obj_set_style_border_width(focus_start_button, 2, 0);
    lv_obj_set_style_radius(focus_start_button, 10, 0);
    lv_obj_set_style_pad_all(focus_start_button, 0, 0);
    lv_obj_clear_flag(focus_start_button, LV_OBJ_FLAG_SCROLLABLE);
    focus_start_label = lv_label_create(focus_start_button);
    lv_obj_set_style_text_font(focus_start_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(focus_start_label, lv_color_hex(0x1ED760), 0);
    lv_obj_center(focus_start_label);

    focus_reset_button = lv_obj_create(focus_screen);
    lv_obj_set_pos(focus_reset_button, 22, 276);
    lv_obj_set_size(focus_reset_button, 196, 44);
    lv_obj_set_style_bg_color(focus_reset_button, lv_color_hex(0x171A1F), 0);
    lv_obj_set_style_border_color(focus_reset_button, lv_color_hex(0x4C555D), 0);
    lv_obj_set_style_border_width(focus_reset_button, 1, 0);
    lv_obj_set_style_radius(focus_reset_button, 10, 0);
    lv_obj_set_style_pad_all(focus_reset_button, 0, 0);
    lv_obj_clear_flag(focus_reset_button, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_t *reset_label = lv_label_create(focus_reset_button);
    lv_obj_set_style_text_font(reset_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(reset_label, lv_color_white(), 0);
    lv_label_set_text(reset_label, "NOLLA");
    lv_obj_center(reset_label);

    focus_settings_button = lv_obj_create(focus_screen);
    lv_obj_set_pos(focus_settings_button, 158, 4);
    lv_obj_set_size(focus_settings_button, 74, 44);
    lv_obj_set_style_bg_color(focus_settings_button, lv_color_hex(0x171A1F), 0);
    lv_obj_set_style_border_color(focus_settings_button, lv_color_hex(0x1ED760), 0);
    lv_obj_set_style_border_width(focus_settings_button, 1, 0);
    lv_obj_set_style_radius(focus_settings_button, 8, 0);
    lv_obj_set_style_pad_all(focus_settings_button, 0, 0);
    lv_obj_clear_flag(focus_settings_button, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_t *settings_label = lv_label_create(focus_settings_button);
    lv_obj_set_style_text_font(settings_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(settings_label, lv_color_hex(0x1ED760), 0);
    lv_label_set_text(settings_label, "TIDER");
    lv_obj_center(settings_label);

    focus_next_label = lv_label_create(focus_screen);
    lv_obj_set_width(focus_next_label, 132);
    lv_obj_set_style_text_font(focus_next_label, &lv_font_montserrat_10, 0);
    lv_obj_set_style_text_color(focus_next_label, lv_color_hex(0x747B84), 0);
    lv_obj_set_style_text_align(focus_next_label, LV_TEXT_ALIGN_LEFT, 0);
    lv_obj_set_pos(focus_next_label, 12, 39);

    // A central focus-complete cue becomes a small reminder after ten seconds.
    // Raw touch handling and non-clickable LVGL objects leave both inert.
    focus_completion_banner = lv_obj_create(lv_layer_top());
    lv_obj_set_pos(focus_completion_banner, 10, 84);
    lv_obj_set_size(focus_completion_banner, 220, 104);
    lv_obj_set_style_bg_color(focus_completion_banner, lv_color_hex(0x1ED760), 0);
    lv_obj_set_style_bg_opa(focus_completion_banner, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(focus_completion_banner, 0, 0);
    lv_obj_set_style_radius(focus_completion_banner, 12, 0);
    lv_obj_set_style_pad_all(focus_completion_banner, 0, 0);
    lv_obj_clear_flag(focus_completion_banner, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_clear_flag(focus_completion_banner, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(focus_completion_banner, LV_OBJ_FLAG_HIDDEN);
    focus_completion_label = lv_label_create(focus_completion_banner);
    lv_obj_set_style_text_font(focus_completion_label, &lv_font_montserrat_28, 0);
    lv_obj_set_style_text_color(focus_completion_label, lv_color_hex(0x101419), 0);
    lv_label_set_text(focus_completion_label, "FOKUS KLART");
    lv_obj_align(focus_completion_label, LV_ALIGN_TOP_MID, 0, 20);
    focus_completion_sub_label = lv_label_create(focus_completion_banner);
    lv_obj_set_style_text_font(focus_completion_sub_label, &lv_font_montserrat_14, 0);
    lv_obj_set_style_text_color(focus_completion_sub_label, lv_color_hex(0x101419), 0);
    lv_label_set_text(focus_completion_sub_label, "PAUSEN HAR STARTAT");
    lv_obj_align(focus_completion_sub_label, LV_ALIGN_TOP_MID, 0, 72);
    refreshFocusUi(true);
}

lv_obj_t *createFocusSettingsButton(lv_obj_t *parent, const char *caption,
                                     int x, int y, int width, int height) {
    lv_obj_t *button = lv_obj_create(parent);
    lv_obj_set_pos(button, x, y);
    lv_obj_set_size(button, width, height);
    lv_obj_set_style_bg_color(button, lv_color_hex(0x1B3025), 0);
    lv_obj_set_style_border_color(button, lv_color_hex(0x1ED760), 0);
    lv_obj_set_style_border_width(button, 1, 0);
    lv_obj_set_style_radius(button, 9, 0);
    lv_obj_set_style_pad_all(button, 0, 0);
    lv_obj_clear_flag(button, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_t *label = lv_label_create(button);
    lv_label_set_text(label, caption);
    lv_obj_set_style_text_font(label, &lv_font_montserrat_20, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(0x1ED760), 0);
    lv_obj_center(label);
    return button;
}

void refreshFocusSettingsUi() {
    if (!focus_settings_focus_label) return;
    lv_label_set_text_fmt(focus_settings_focus_label, "FOKUS  %u MIN",
                          unsigned(focus_draft_durations.focus_minutes));
    lv_label_set_text_fmt(focus_settings_break_label, "PAUS  %u MIN",
                          unsigned(focus_draft_durations.break_minutes));
}

void createFocusSettingsScreen() {
    focus_settings_screen = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(focus_settings_screen, lv_color_hex(0x101419), 0);
    lv_obj_set_style_bg_opa(focus_settings_screen, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(focus_settings_screen, 0, 0);
    lv_obj_set_style_pad_all(focus_settings_screen, 0, 0);
    lv_obj_clear_flag(focus_settings_screen, LV_OBJ_FLAG_SCROLLABLE);

    focus_settings_heading = lv_label_create(focus_settings_screen);
    lv_label_set_text(focus_settings_heading, "TIDER");
    lv_obj_set_style_text_font(focus_settings_heading, &lv_font_montserrat_20, 0);
    lv_obj_set_style_text_color(focus_settings_heading, lv_color_hex(0x1ED760), 0);
    lv_obj_set_pos(focus_settings_heading, 14, 3);

    focus_settings_info_label = lv_label_create(focus_settings_screen);
    lv_obj_set_width(focus_settings_info_label, 148);
    lv_obj_set_style_text_font(focus_settings_info_label, &lv_font_montserrat_10, 0);
    lv_obj_set_style_text_color(focus_settings_info_label, lv_color_hex(0xD5D9DE), 0);
    lv_obj_set_style_text_align(focus_settings_info_label, LV_TEXT_ALIGN_RIGHT, 0);
    lv_label_set_text(focus_settings_info_label, "AKTIV TIMER BEHALLS");
    lv_obj_set_pos(focus_settings_info_label, 78, 9);

    focus_settings_focus_card = lv_obj_create(focus_settings_screen);
    lv_obj_set_pos(focus_settings_focus_card, 12, 31);
    lv_obj_set_size(focus_settings_focus_card, 216, 115);
    lv_obj_set_style_bg_color(focus_settings_focus_card, lv_color_hex(0x171A1F), 0);
    lv_obj_set_style_border_color(focus_settings_focus_card, lv_color_hex(0x4C555D), 0);
    lv_obj_set_style_border_width(focus_settings_focus_card, 1, 0);
    lv_obj_set_style_radius(focus_settings_focus_card, 9, 0);
    lv_obj_set_style_pad_all(focus_settings_focus_card, 0, 0);
    lv_obj_clear_flag(focus_settings_focus_card, LV_OBJ_FLAG_SCROLLABLE);
    focus_settings_focus_label = lv_label_create(focus_settings_focus_card);
    lv_obj_set_width(focus_settings_focus_label, 200);
    lv_obj_set_style_text_font(focus_settings_focus_label, &lv_font_montserrat_16, 0);
    lv_obj_set_style_text_color(focus_settings_focus_label, lv_color_white(), 0);
    lv_obj_set_style_text_align(focus_settings_focus_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_pos(focus_settings_focus_label, 8, 4);
    focus_settings_focus_plus = createFocusSettingsButton(
        focus_settings_focus_card, "+ 5 MIN", 8, 26, 200, 44);
    focus_settings_focus_minus = createFocusSettingsButton(
        focus_settings_focus_card, "- 5 MIN", 8, 70, 200, 44);

    focus_settings_break_card = lv_obj_create(focus_settings_screen);
    lv_obj_set_pos(focus_settings_break_card, 12, 149);
    lv_obj_set_size(focus_settings_break_card, 216, 115);
    lv_obj_set_style_bg_color(focus_settings_break_card, lv_color_hex(0x171A1F), 0);
    lv_obj_set_style_border_color(focus_settings_break_card, lv_color_hex(0x4C555D), 0);
    lv_obj_set_style_border_width(focus_settings_break_card, 1, 0);
    lv_obj_set_style_radius(focus_settings_break_card, 9, 0);
    lv_obj_set_style_pad_all(focus_settings_break_card, 0, 0);
    lv_obj_clear_flag(focus_settings_break_card, LV_OBJ_FLAG_SCROLLABLE);
    focus_settings_break_label = lv_label_create(focus_settings_break_card);
    lv_obj_set_width(focus_settings_break_label, 200);
    lv_obj_set_style_text_font(focus_settings_break_label, &lv_font_montserrat_16, 0);
    lv_obj_set_style_text_color(focus_settings_break_label, lv_color_white(), 0);
    lv_obj_set_style_text_align(focus_settings_break_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_pos(focus_settings_break_label, 8, 4);
    focus_settings_break_plus = createFocusSettingsButton(
        focus_settings_break_card, "+ 1 MIN", 8, 26, 200, 44);
    focus_settings_break_minus = createFocusSettingsButton(
        focus_settings_break_card, "- 1 MIN", 8, 70, 200, 44);
    focus_settings_save = createFocusSettingsButton(
        focus_settings_screen, "SPARA / TILLBAKA", 22, 269, 196, 48);
    lv_obj_t *save_label = lv_obj_get_child(focus_settings_save, 0);
    lv_obj_set_style_text_font(save_label, &lv_font_montserrat_14, 0);
    refreshFocusSettingsUi();
}

lv_obj_t *createLocalSettingsButton(const char *caption, int y, int height,
                                    lv_obj_t **caption_label) {
    lv_obj_t *button = createFocusSettingsButton(
        local_settings_screen, caption, 16, y, 208, height);
    *caption_label = lv_obj_get_child(button, 0);
    lv_obj_set_width(*caption_label, 194);
    lv_obj_set_style_text_align(*caption_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_font(*caption_label, &lv_font_montserrat_14, 0);
    lv_obj_center(*caption_label);
    return button;
}

void refreshLocalSettingsUi() {
    if (!local_settings_theme_label) return;
    const char *theme = focus_ui_settings.theme == AccentTheme::Cyan ? "CYAN" :
                        focus_ui_settings.theme == AccentTheme::Amber ? "AMBER" :
                                                                    "GRON";
    lv_label_set_text_fmt(local_settings_theme_label, "TEMA: %s  >", theme);
    lv_label_set_text_fmt(local_settings_auto_label, "VISA FOKUS VID FASSLUT\n%s",
                          focus_ui_settings.auto_show_focus ? "PA" : "AV");
    lv_label_set_text_fmt(local_settings_led_label, "LED VID FASSLUT\n%s",
                          focus_ui_settings.led_at_phase_end ? "PA" : "AV");
    lv_obj_center(local_settings_theme_label);
    lv_obj_center(local_settings_auto_label);
    lv_obj_center(local_settings_led_label);
}

void createLocalSettingsScreen() {
    local_settings_screen = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(local_settings_screen, lv_color_hex(0x101419), 0);
    lv_obj_set_style_bg_opa(local_settings_screen, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(local_settings_screen, 0, 0);
    lv_obj_set_style_pad_all(local_settings_screen, 0, 0);
    lv_obj_clear_flag(local_settings_screen, LV_OBJ_FLAG_SCROLLABLE);

    local_settings_heading = lv_label_create(local_settings_screen);
    lv_label_set_text(local_settings_heading, "INSTALLNINGAR");
    lv_obj_set_style_text_font(local_settings_heading, &lv_font_montserrat_20, 0);
    lv_obj_set_style_text_color(local_settings_heading, lv_color_hex(0x1ED760), 0);
    lv_obj_align(local_settings_heading, LV_ALIGN_TOP_MID, 0, 9);

    local_settings_theme_button = createLocalSettingsButton(
        "TEMA: GRON  >", 48, 48, &local_settings_theme_label);
    local_settings_auto_button = createLocalSettingsButton(
        "VISA FOKUS VID FASSLUT\nAV", 105, 58, &local_settings_auto_label);
    local_settings_led_button = createLocalSettingsButton(
        "LED VID FASSLUT\nPA", 171, 58, &local_settings_led_label);
    local_settings_info_label = lv_label_create(local_settings_screen);
    lv_obj_set_width(local_settings_info_label, 208);
    lv_obj_set_style_text_font(local_settings_info_label, &lv_font_montserrat_10, 0);
    lv_obj_set_style_text_color(local_settings_info_label, lv_color_hex(0xD5D9DE), 0);
    lv_obj_set_style_text_align(local_settings_info_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_pos(local_settings_info_label, 16, 237);
    lv_label_set_text(local_settings_info_label, "TRYCK FOR ATT ANDRA");
    local_settings_back_button = createFocusSettingsButton(
        local_settings_screen, "TILLBAKA", 16, 259, 208, 48);
    refreshLocalSettingsUi();
}

void refreshAccentTheme() {
    lv_color_t accent = lv_color_hex(focusAccentHex());
    lv_color_t dark = lv_color_hex(focusDarkAccentHex());
    lv_color_t pressed = lv_color_hex(focusPressedHex());
    if (feature_overlay) {
        lv_obj_set_style_border_color(feature_overlay, accent, 0);
        lv_obj_set_style_text_color(feature_overlay_label, accent, 0);
    }
    lv_obj_t *menu_buttons[] = {feature_overlay_bongo_button,
                                feature_overlay_player_button,
                                feature_overlay_focus_button,
                                feature_overlay_settings_button};
    for (lv_obj_t *button : menu_buttons) {
        if (button) lv_obj_set_style_bg_color(button, pressed, LV_STATE_PRESSED);
    }
    if (feature_overlay) refreshFeatureOverlay();
    if (focus_progress_ring) {
        lv_obj_set_style_arc_color(focus_progress_ring, accent, LV_PART_INDICATOR);
    }
    if (media_brand_label) lv_obj_set_style_text_color(media_brand_label, accent, 0);
    if (media_playback_status_label)
        lv_obj_set_style_text_color(media_playback_status_label, accent, 0);
    if (media_progress_bar)
        lv_obj_set_style_bg_color(media_progress_bar, accent, LV_PART_INDICATOR);
    if (focus_phase_label) lv_obj_set_style_text_color(focus_phase_label, accent, 0);
    if (focus_status_label) lv_obj_set_style_text_color(focus_status_label, accent, 0);
    if (focus_start_label) lv_obj_set_style_text_color(focus_start_label, accent, 0);
    if (focus_settings_heading) lv_obj_set_style_text_color(focus_settings_heading, accent, 0);
    if (local_settings_heading) lv_obj_set_style_text_color(local_settings_heading, accent, 0);
    lv_obj_t *accent_buttons[] = {
        focus_start_button, focus_settings_button,
        focus_settings_focus_plus, focus_settings_focus_minus,
        focus_settings_break_plus, focus_settings_break_minus,
        focus_settings_save, local_settings_theme_button,
        local_settings_auto_button, local_settings_led_button,
        local_settings_back_button
    };
    for (lv_obj_t *button : accent_buttons) {
        if (!button) continue;
        lv_obj_set_style_bg_color(button, dark, 0);
        lv_obj_set_style_border_color(button, accent, 0);
        lv_obj_set_style_bg_color(button, pressed, LV_STATE_PRESSED);
        lv_obj_t *label = lv_obj_get_child(button, 0);
        if (label) lv_obj_set_style_text_color(label, accent, 0);
    }
    if (focus_reset_button) {
        lv_obj_set_style_bg_color(focus_reset_button, pressed, LV_STATE_PRESSED);
    }
    if (focus_completion_banner) {
        lv_obj_set_style_bg_color(focus_completion_banner,
                                  focus_banner_compact ? dark : accent, 0);
        lv_obj_set_style_text_color(focus_completion_label,
                                    focus_banner_compact ? accent : lv_color_hex(0x101419), 0);
    }
    refreshLocalSettingsUi();
}

void updateFocusCue(uint32_t now) {
    driveFocusLed(focus_ui_settings.led_at_phase_end &&
                  focusCueLedOn(focus_cue, now));
    if (!focus_completion_banner) return;
    bool visible = focusCueVisible(focus_cue, now, active_panel);
    bool compact = visible && !focusCueLarge(focus_cue, now);
    if (visible && (compact != focus_banner_compact || !focus_banner_visible ||
                    focus_banner_kind != focus_cue.kind ||
                    focus_banner_panel != active_panel)) {
        // The small badge fits between Bongo's CPU and clock, and between
        // Player's brand and source labels. It leaves their status visible.
        bool focus_done = focus_cue.kind == FocusCueKind::FocusDone;
        lv_obj_set_pos(focus_completion_banner,
                       compact ? 85 : focus_done ? 10 : 0,
                       compact ? (active_panel == PanelId::Settings ? 232 : 0) :
                       focus_done ? 84 : 0);
        lv_obj_set_size(focus_completion_banner,
                        compact ? 70 : focus_done ? 220 : SCREEN_WIDTH,
                        compact ? 22 : focus_done ? 104 : 46);
        lv_obj_set_style_bg_color(focus_completion_banner,
                                  lv_color_hex(compact ? focusDarkAccentHex() :
                                              focusAccentHex()), 0);
        lv_obj_set_style_radius(focus_completion_banner,
                                compact ? 7 : focus_done ? 12 : 0, 0);
        lv_obj_set_style_text_font(focus_completion_label,
                                   compact ? &lv_font_montserrat_10 :
                                   focus_done ? &lv_font_montserrat_28 :
                                                &lv_font_montserrat_20, 0);
        lv_obj_set_style_text_color(focus_completion_label,
                                    lv_color_hex(compact ? focusAccentHex() : 0x101419), 0);
        lv_label_set_text(focus_completion_label,
                          compact ? (focus_done ? "PAUS" : "START") :
                          focus_done ? "FOKUS KLART" : "PAUS KLAR");
        if (!compact && focus_done) {
            lv_obj_align(focus_completion_label, LV_ALIGN_TOP_MID, 0, 20);
            lv_obj_clear_flag(focus_completion_sub_label, LV_OBJ_FLAG_HIDDEN);
        } else {
            lv_obj_center(focus_completion_label);
            lv_obj_add_flag(focus_completion_sub_label, LV_OBJ_FLAG_HIDDEN);
        }
        lv_obj_clear_flag(focus_completion_banner, LV_OBJ_FLAG_HIDDEN);
        lv_obj_move_foreground(focus_completion_banner);
        if (feature_overlay && !lv_obj_has_flag(feature_overlay, LV_OBJ_FLAG_HIDDEN)) {
            lv_obj_move_foreground(feature_overlay_backdrop);
            lv_obj_move_foreground(feature_overlay);
        }
    } else if (!visible && focus_banner_visible) {
        lv_obj_add_flag(focus_completion_banner, LV_OBJ_FLAG_HIDDEN);
    }
    focus_banner_visible = visible;
    focus_banner_compact = compact;
    focus_banner_kind = focus_cue.kind;
    focus_banner_panel = active_panel;
    if (local_settings_info_label) {
        if (visible && compact && active_panel == PanelId::Settings)
            lv_obj_add_flag(local_settings_info_label, LV_OBJ_FLAG_HIDDEN);
        else lv_obj_clear_flag(local_settings_info_label, LV_OBJ_FLAG_HIDDEN);
    }
}

void setFocusState(FocusState next, uint32_t now) {
    FocusState before = focus_state;
    focus_cue = focusCueForTransition(focus_cue, before, next, now);
    focus_state = next;
    updateFocusCue(now);
    if (focusUiShouldAutoShow(focus_ui_settings, before, next)) {
        showFocusScreen(false);
    }
    refreshFocusUi();
}

void serviceFocusTimer(uint32_t now) {
    if (focus_state.mode == FocusMode::Running) {
        setFocusState(focusAdvance(focus_state, now, focus_durations), now);
    }
    updateFocusCue(now);
}

void showMediaScreen() {
    if (!media_screen || active_panel == PanelId::Player) return;
    focus_settings_open = false;
    active_panel = PanelId::Player;
    lv_scr_load_anim(media_screen, LV_SCR_LOAD_ANIM_FADE_ON, 220, 0, false);
}

void showBongoScreen() {
    if (!screen || active_panel == PanelId::Bongo) return;
    focus_settings_open = false;
    active_panel = PanelId::Bongo;
    lv_scr_load_anim(screen, LV_SCR_LOAD_ANIM_FADE_ON, 220, 0, false);
}

void showFocusScreen(bool acknowledge_cue) {
    if (!focus_screen) return;
    if (active_panel == PanelId::Focus && !focus_settings_open) return;
    if (!acknowledge_cue && touch_is_down) {
        if (touch_feedback_button)
            lv_obj_clear_state(touch_feedback_button, LV_STATE_PRESSED);
        touch_feedback_button = NULL;
        touch_button_cancelled = true;
    }
    active_panel = PanelId::Focus;
    focus_settings_open = false;
    if (acknowledge_cue && focus_cue.kind != FocusCueKind::None) {
        focus_cue = focusCueAfterPanelShow(focus_cue, true);
        updateFocusCue(millis());
    }
    media_tap_count = 0;
    media_tap_deadline = 0;
    focus_last_display_seconds = -1;
    focus_last_progress = -1;
    refreshFocusUi(true);
    lv_scr_load_anim(focus_screen, LV_SCR_LOAD_ANIM_FADE_ON, 220, 0, false);
}

void showFocusScreen() { showFocusScreen(true); }

void showFocusSettings() {
    if (!focus_settings_screen || active_panel != PanelId::Focus) return;
    focus_draft_durations = focus_durations;
    refreshFocusSettingsUi();
    lv_label_set_text(focus_settings_info_label, "AKTIV TIMER BEHALLS");
    focus_settings_open = true;
    lv_scr_load_anim(focus_settings_screen, LV_SCR_LOAD_ANIM_FADE_ON,
                     220, 0, false);
}

void closeFocusSettings() {
    focus_settings_open = false;
    refreshFocusUi(true);
    lv_scr_load_anim(focus_screen, LV_SCR_LOAD_ANIM_FADE_ON, 220, 0, false);
}

void showLocalSettingsScreen() {
    if (!local_settings_screen || active_panel == PanelId::Settings) return;
    panel_before_settings = active_panel;
    focus_settings_open = false;
    active_panel = PanelId::Settings;
    media_tap_count = 0;
    media_tap_deadline = 0;
    lv_label_set_text(local_settings_info_label, "TRYCK FOR ATT ANDRA");
    refreshLocalSettingsUi();
    lv_scr_load_anim(local_settings_screen, LV_SCR_LOAD_ANIM_FADE_ON, 220, 0, false);
}

void closeLocalSettingsScreen() {
    PanelId target = panel_before_settings;
    if (target == PanelId::Player) showMediaScreen();
    else if (target == PanelId::Focus) showFocusScreen();
    else showBongoScreen();
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

    Serial.printf("BONK:%lu\n", (unsigned long)touch_bonk_count);
}

void hideFeatureOverlay() {
    if (!feature_overlay) return;
    lv_obj_add_flag(feature_overlay, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(feature_overlay_backdrop, LV_OBJ_FLAG_HIDDEN);
    overlay_hide_time = 0;
}

void toggleFeatureOverlay(uint32_t current_time) {
    if (!feature_overlay) return;
    if (lv_obj_has_flag(feature_overlay, LV_OBJ_FLAG_HIDDEN)) {
        // A media tap preceding this long press must not fire after opening.
        media_tap_count = 0;
        media_tap_deadline = 0;
        lv_obj_clear_flag(feature_overlay_backdrop, LV_OBJ_FLAG_HIDDEN);
        lv_obj_move_foreground(feature_overlay_backdrop);
        lv_obj_clear_flag(feature_overlay, LV_OBJ_FLAG_HIDDEN);
        lv_obj_move_foreground(feature_overlay);
        overlay_hide_time = current_time + 6000;
        updateTimeDisplay();
        refreshFeatureOverlay();
    } else {
        hideFeatureOverlay();
    }
}

TouchRect touchButtonRect(lv_obj_t *button) {
    lv_area_t area;
    lv_obj_get_coords(button, &area);
    return {area.x1, area.y1, area.x2, area.y2};
}

void setTouchFeedback(lv_obj_t *button) {
    if (touch_feedback_button == button) return;
    if (touch_feedback_button) {
        lv_obj_clear_state(touch_feedback_button, LV_STATE_PRESSED);
    }
    touch_feedback_button = button;
    if (button) lv_obj_add_state(button, LV_STATE_PRESSED);
}

lv_obj_t *pressedButtonAt(uint16_t raw_x, uint16_t raw_y) {
    lv_obj_t *candidates[5] = {};
    uint8_t count = 0;
    if (touch_started_in_menu && feature_overlay &&
        !lv_obj_has_flag(feature_overlay, LV_OBJ_FLAG_HIDDEN)) {
        lv_obj_update_layout(feature_overlay);
        candidates[0] = feature_overlay_bongo_button;
        candidates[1] = feature_overlay_player_button;
        candidates[2] = feature_overlay_focus_button;
        candidates[3] = feature_overlay_settings_button;
        count = 4;
    } else if (active_panel == PanelId::Settings) {
        lv_obj_update_layout(local_settings_screen);
        candidates[0] = local_settings_theme_button;
        candidates[1] = local_settings_auto_button;
        candidates[2] = local_settings_led_button;
        candidates[3] = local_settings_back_button;
        count = 4;
    } else if (active_panel == PanelId::Focus && focus_settings_open) {
        lv_obj_update_layout(focus_settings_screen);
        candidates[0] = focus_settings_focus_plus;
        candidates[1] = focus_settings_focus_minus;
        candidates[2] = focus_settings_break_plus;
        candidates[3] = focus_settings_break_minus;
        candidates[4] = focus_settings_save;
        count = 5;
    } else if (active_panel == PanelId::Focus) {
        lv_obj_update_layout(focus_screen);
        candidates[0] = focus_start_button;
        candidates[1] = focus_reset_button;
        candidates[2] = focus_settings_button;
        count = 3;
    }
    for (uint8_t i = 0; i < count; ++i) {
        if (candidates[i] && rawPointInRect(touchButtonRect(candidates[i]),
                                            raw_x, raw_y)) {
            if (!touch_started_in_menu && focus_banner_visible &&
                focusCueLarge(focus_cue, millis()) &&
                rawPointInRect(touchButtonRect(focus_completion_banner),
                               raw_x, raw_y)) return NULL;
            return candidates[i];
        }
    }
    return NULL;
}

void selectFeaturePanel() {
    // A menu swipe is consumed. A tap must start and end inside one button.
    lv_obj_update_layout(feature_overlay);
    MenuChoice selected = menuChoiceForTap(
        touchButtonRect(feature_overlay_bongo_button),
        touchButtonRect(feature_overlay_player_button),
        touchButtonRect(feature_overlay_focus_button),
        touchButtonRect(feature_overlay_settings_button),
        touch_start_x, touch_start_y, touch_last_x, touch_last_y,
        MEDIA_SWIPE_THRESHOLD - 1);
    if (selected == MenuChoice::None) return;
    hideFeatureOverlay();
    if (selected == MenuChoice::Bongo) showBongoScreen();
    else if (selected == MenuChoice::Player) showMediaScreen();
    else if (selected == MenuChoice::Focus) showFocusScreen();
    else showLocalSettingsScreen();
}

void handleFocusTap(uint32_t current_time) {
    if (focus_settings_open) {
        lv_obj_update_layout(focus_settings_screen);
        // A central completion message temporarily covers the settings
        // controls. Raw touch must not act on obscured buttons.
        if (focusCueLarge(focus_cue, current_time) &&
            focus_cue.kind == FocusCueKind::FocusDone &&
            rawTapInRect(touchButtonRect(focus_completion_banner),
                         touch_start_x, touch_start_y, touch_last_x, touch_last_y,
                         FOCUS_TAP_MOVE_MAX_RAW)) return;
        FocusSettingsAction action = focusSettingsActionForTap(
            touchButtonRect(focus_settings_focus_minus),
            touchButtonRect(focus_settings_focus_plus),
            touchButtonRect(focus_settings_break_minus),
            touchButtonRect(focus_settings_break_plus),
            touchButtonRect(focus_settings_save),
            touch_start_x, touch_start_y, touch_last_x, touch_last_y,
            FOCUS_TAP_MOVE_MAX_RAW);
        if (action == FocusSettingsAction::Save) {
            if (focusPackDurations(focus_draft_durations) !=
                focusPackDurations(focus_durations)) {
                if (!saveFocusDurations(focus_draft_durations)) {
                    lv_label_set_text(focus_settings_info_label, "KUNDE INTE SPARA");
                    return;
                }
                focus_durations = focus_draft_durations;
                setFocusState(focusAfterSettingsSave(
                    focus_state, focus_durations, current_time), current_time);
            }
            closeFocusSettings();
        } else if (action != FocusSettingsAction::None) {
            bool adjust_focus = action == FocusSettingsAction::FocusMinus ||
                                action == FocusSettingsAction::FocusPlus;
            int direction = action == FocusSettingsAction::FocusMinus ||
                            action == FocusSettingsAction::BreakMinus ? -1 : 1;
            focus_draft_durations = focusAdjustDurations(
                focus_draft_durations, adjust_focus, direction);
            refreshFocusSettingsUi();
        }
        return;
    }
    lv_obj_update_layout(focus_screen);
    FocusAction action = focusActionForTap(
        touchButtonRect(focus_start_button), touchButtonRect(focus_reset_button),
        touchButtonRect(focus_settings_button),
        touch_start_x, touch_start_y, touch_last_x, touch_last_y,
        FOCUS_TAP_MOVE_MAX_RAW);
    if (action == FocusAction::Toggle) {
        setFocusState(focusToggle(focus_state, current_time, focus_durations),
                      current_time);
    } else if (action == FocusAction::Reset) {
        setFocusState(focusReset(current_time, focus_durations), current_time);
    } else if (action == FocusAction::Settings) {
        showFocusSettings();
    }
}

void handleLocalSettingsTap(uint32_t current_time) {
    lv_obj_update_layout(local_settings_screen);
    if (focus_banner_visible && focusCueLarge(focus_cue, current_time) &&
        rawTapInRect(touchButtonRect(focus_completion_banner),
                     touch_start_x, touch_start_y, touch_last_x, touch_last_y,
                     FOCUS_TAP_MOVE_MAX_RAW)) return;
    LocalSettingsAction action = localSettingsActionForTap(
        touchButtonRect(local_settings_theme_button),
        touchButtonRect(local_settings_auto_button),
        touchButtonRect(local_settings_led_button),
        touchButtonRect(local_settings_back_button),
        touch_start_x, touch_start_y, touch_last_x, touch_last_y,
        FOCUS_TAP_MOVE_MAX_RAW);
    if (action == LocalSettingsAction::Back) {
        closeLocalSettingsScreen();
        return;
    }
    FocusUiSettings next = focus_ui_settings;
    if (action == LocalSettingsAction::Theme) next = focusUiNextTheme(next);
    else if (action == LocalSettingsAction::AutoShow)
        next.auto_show_focus = !next.auto_show_focus;
    else if (action == LocalSettingsAction::Led)
        next.led_at_phase_end = !next.led_at_phase_end;
    else return;
    if (focusPackUiSettings(next) == focusPackUiSettings(focus_ui_settings)) return;
    if (!saveFocusUiSettings(next)) {
        lv_label_set_text(local_settings_info_label, "KUNDE INTE SPARA");
        return;
    }
    focus_ui_settings = next;
    lv_label_set_text(local_settings_info_label, "SPARAT");
    refreshAccentTheme();
    updateFocusCue(current_time);
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
        touch_start_panel = active_panel;
        touch_start_times_open = focus_settings_open;
        touch_down_time = current_time;
        tft.getTouchRaw(&touch_start_x, &touch_start_y);
        touch_last_x = touch_start_x;
        touch_last_y = touch_start_y;
        touch_button_cancelled = false;
        setTouchFeedback(pressedButtonAt(touch_start_x, touch_start_y));
    } else if (pressed && touch_is_down) {
        tft.getTouchRaw(&touch_last_x, &touch_last_y);
        if (touch_feedback_button &&
            !rawPointInRect(touchButtonRect(touch_feedback_button),
                            touch_last_x, touch_last_y)) {
            setTouchFeedback(NULL);
            touch_button_cancelled = true;
        }
        if (!touch_long_press_fired &&
            current_time - touch_down_time >= TOUCH_LONG_PRESS_MS) {
            touch_long_press_fired = true;
            setTouchFeedback(NULL);
            touch_button_cancelled = true;
            toggleFeatureOverlay(current_time);
        }
    } else if (!pressed && touch_is_down) {
        uint32_t press_duration = current_time - touch_down_time;
        touch_is_down = false;
        setTouchFeedback(NULL);
        if (!touch_long_press_fired && press_duration >= TOUCH_LONG_PRESS_MS) {
            touch_long_press_fired = true;
            touch_button_cancelled = true;
            toggleFeatureOverlay(current_time);
        }
        if (touchIsTap(press_duration, touch_long_press_fired)) {
            TouchRoute route = routeTouch(touch_start_panel, touch_started_in_menu);
            if (touchPanelChangedCancelsTap(touch_start_panel, active_panel,
                                            touch_started_in_menu) ||
                (route == TouchRoute::Focus &&
                 touch_start_times_open != focus_settings_open) ||
                ((route == TouchRoute::Menu || route == TouchRoute::Focus ||
                  route == TouchRoute::Settings) && touch_button_cancelled)) {
                // Dragging outside the pressed button cancels a short tap.
            } else if (route == TouchRoute::Menu) {
                if (feature_overlay &&
                    !lv_obj_has_flag(feature_overlay, LV_OBJ_FLAG_HIDDEN)) {
                    selectFeaturePanel();
                }
            } else if (route == TouchRoute::Focus) {
                handleFocusTap(current_time);
            } else if (route == TouchRoute::Settings) {
                handleLocalSettingsTap(current_time);
            } else if (route == TouchRoute::Media) {
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
            } else if (route == TouchRoute::Bongo) {
                triggerTouchBonk(current_time);
            }
        }
        touch_started_in_menu = false;
        touch_button_cancelled = false;
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
    if (companionIdleExpired(current_time, last_companion_stats_ms) &&
        !media_art_receiving && !media_art_v2.active && Serial.available() == 0) {
        enterCompanionDeepSleep(true);
    }
    reportDeviceStatus(current_time);
    handleTouchFeature(current_time);
    serviceFocusTimer(current_time);
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
