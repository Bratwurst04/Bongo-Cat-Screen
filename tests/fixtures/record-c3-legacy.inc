#define MEDIA_SWIPE_THRESHOLD 420
#define MEDIA_MULTI_TAP_WINDOW_MS 320
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
    media_art_valid = true;
    media_record_flip.artwork(millis(), mediaRecordVisible());
    media_record_dirty = true;
    // Only constant-size state changes above. Render after RX/ACK in loop().
    refreshMediaUi();
    if (acknowledge) Serial.println("MEDIA_ART_OK");
}
void loadGenericVinyl() {
    // Generic pixels belong only to the projection buffer, never a RX slot.
    media_record_flip.request(RecordSide::Generic, millis(), false);
    media_record_dirty = true;
    media_art_valid = true;
    refreshMediaUi();
}
void allocateMediaRecordPixels() {
    // One allocation for the screen lifetime, outside the animation/RX paths.
    // Failure disables flips and uses the bounded hidden-DJ generic fallback.
    static bool attempted = false;
    if (attempted) return;
    attempted = true;
    media_record_pixels = static_cast<unsigned short *>(heap_caps_malloc(
        RECORD_PIXELS * RECORD_PIXELS * sizeof(unsigned short), MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));
}
void updateMediaTrackContext(uint32_t value, uint32_t current_time) {
    if (media_track_context_id != value) {
        media_art_v2.abort();
        media_art_receiving = false;
    }
    media_track_context_id = value;
    media_record_dirty |= media_record_flip.trackContext(
        value, current_time, mediaRecordVisible());
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
void fwBeginFromSource() { media_art_receiving_buffer = 1 - media_art_active_buffer; }
void fwDurationFromSource(uint32_t value) { uint32_t next_duration = value;
                // A corrected duration on the same track is not a new record.
                media_duration_seconds = next_duration;
                 }
void mediaTouchFromSource(uint32_t current_time) {
                int delta_x = (int)touch_last_x - (int)touch_start_x;
                int delta_y = (int)touch_last_y - (int)touch_start_y;
                // The touch controller's raw axes are rotated relative to
                // this portrait display: raw X increases down; raw Y
                // decreases right. Preserve the older disc swipe mapping.
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
                } else if (touch_started_in_focus_status) {
                    handleFocusStatusTap(current_time);
                } else {
                    queueMediaTap(current_time);
                }
            }