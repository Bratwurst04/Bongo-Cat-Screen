// Actual LVGL 8.3.11 software raster + 40-row flush reconstruction.
// Only the display transport, clock, serial notification and DJ test pattern are
// host adapters. Scene creation, viewport, rotation, projection, arm/paw drawing,
// slot selection and Focus geometry are extracted unchanged from firmware.
#include <lvgl.h>
#include <string.h>
#include "../src/media_turntable.h"
#include "../src/focus_countdown_layout.h"

#ifdef _WIN32
#define VP_EXPORT extern "C" __declspec(dllexport)
#else
#define VP_EXPORT extern "C" __attribute__((visibility("default")))
#endif
extern "C" const lv_font_t *vp_title_font(void);
extern "C" const lv_font_t *vp_artist_font(void);
#define lv_font_media_swedish_16 (*vp_title_font())
#define lv_font_media_swedish_14 (*vp_artist_font())
template<class T> T min(T a, T b) { return a < b ? a : b; }
template<class T> T max(T a, T b) { return a > b ? a : b; }

constexpr int MEDIA_ART_SIZE = 112, CAT_SIZE = 64;
constexpr int MEDIA_ART_LV_BYTES = 112*112*2;
constexpr uint32_t MEDIA_VINYL_FRAME_MS = 60;
constexpr int MEDIA_VINYL_ANGLE_STEP = 18;
lv_obj_t *media_screen, *media_art_box, *media_art_viewport, *media_art_image;
lv_obj_t *media_arm_layer, *media_paw_layer, *media_state_label, *media_cat_canvas;
lv_obj_t *media_title_label, *media_artist_label, *media_progress_bar;
lv_obj_t *media_elapsed_label, *media_duration_label, *media_playback_status_label;
lv_obj_t *feature_overlay, *other_screen;
bool media_focus_layout_active, media_cat_mode, media_art_valid, media_is_playing;
bool media_record_dirty;
PanelId active_panel;
uint32_t media_position_seconds, media_duration_seconds, media_turntable_last_tick;
uint32_t media_vinyl_last_frame, media_track_context_id, clock_ms;
int media_vinyl_angle;
uint8_t media_art_active_buffer;
unsigned short art_storage[2][112*112], record_storage[112*112];
unsigned short *media_art_buffers[2] = {art_storage[0], art_storage[1]};
unsigned short *media_record_pixels;
lv_color_t media_cat_canvas_buffer[CAT_SIZE*CAT_SIZE];
lv_img_dsc_t media_art_descriptor, media_record_descriptor;
MediaTurntable media_record_flip;
TurntableFrame media_turntable_frame, media_record_last_frame;
uint32_t millis() { return clock_ms; }
void serviceMediaArtShown(const TurntableFrame &) {} // Serial notice, no draw.
void renderMediaCat() {
    // A bounded opaque diagnostic pattern, not a simulated/accepted Bongo sprite.
    for (int y=0; y<CAT_SIZE; ++y) for (int x=0; x<CAT_SIZE; ++x)
        media_cat_canvas_buffer[y*CAT_SIZE+x] = lv_color_hex((x+y)%8 < 4 ? 0xFFFFFF : 0xFF83AA);
    lv_obj_invalidate(media_cat_canvas);
}
#include "viewport_fixture.inc"

static lv_disp_t *display;
static lv_disp_drv_t driver; // LVGL retains this pointer for the display lifetime.
static lv_disp_draw_buf_t draw_buffer;
static lv_color_t rows[240*40], pixels[240*320], incremental[240*320], reference[240*320];
static char error_text[256];
static uint64_t measured[8];
static uint64_t flush_pixels;
static int flush_y_max, compared_frames;

static int fail(int line, const char *condition) {
    if (error_text[0]) return 1;
    lv_snprintf(error_text, sizeof(error_text), "line %d: %s (frame %d)", line, condition, compared_frames);
    return 1;
}
#define CHECK(c) do { if (!(c)) return fail(__LINE__, #c); } while (0)

static void flush(lv_disp_drv_t *driver, const lv_area_t *area, lv_color_t *colors) {
    for (int y=area->y1; y<=area->y2; ++y) for (int x=area->x1; x<=area->x2; ++x)
        pixels[y*240+x] = *colors++;
    flush_pixels += lv_area_get_size(area);
    flush_y_max = max(flush_y_max, (int)area->y2);
    lv_disp_flush_ready(driver);
}

static void refresh() { lv_refr_now(display); }
static void full() { lv_obj_invalidate(lv_scr_act()); refresh(); }
static bool matchesFull() {
    refresh();
    memcpy(incremental, pixels, sizeof(pixels));
    full();
    ++compared_frames;
    return memcmp(incremental, pixels, sizeof(pixels)) == 0;
}

static void init() {
    // Production malloc config does not expose lv_deinit. Initialize globals
    // once; dispose each test's display/screens/animations before the next one.
    static bool initialized=false;
    if(!initialized) { lv_init(); initialized=true; }
    lv_disp_draw_buf_init(&draw_buffer, rows, NULL, 240*40);
    lv_disp_drv_init(&driver);
    driver.hor_res=240; driver.ver_res=320;
    driver.draw_buf=&draw_buffer; driver.flush_cb=flush;
    display=lv_disp_drv_register(&driver);
    media_focus_layout_active=false; media_cat_mode=false; media_is_playing=true;
    media_art_valid=true; media_record_dirty=true;
    active_panel=PanelId::Player; media_track_context_id=1;
    media_position_seconds=45; media_duration_seconds=180;
    media_turntable_last_tick=media_vinyl_last_frame=0; media_vinyl_angle=0;
    clock_ms=1000; media_art_active_buffer=0; media_record_pixels=record_storage;
    media_record_flip=MediaTurntable{};
    media_turntable_frame=TurntableFrame{}; media_record_last_frame=TurntableFrame{};
    media_art_descriptor=lv_img_dsc_t{}; media_record_descriptor=lv_img_dsc_t{};
    memset(measured,0,sizeof(measured)); compared_frames=0;
    memset(pixels,0xA5,sizeof(pixels)); error_text[0]=0;
    const uint16_t key=lv_color_make(0,255,0).full;
    for (int slot=0; slot<2; ++slot) for (int y=0;y<112;++y) for(int x=0;x<112;++x) {
        const int dx=x-56, dy=y-56;
        art_storage[slot][y*112+x] = dx*dx+dy*dy >= 54*54 ? key :
            lv_color_hex(slot ? ((x+y)%20<10 ? 0xF0AD40 : 0xA022CC) :
                                (x<56 ? (y<56?0xF02030:0x4070FF) : (y<56?0xC0D040:0x60C0D0))).full;
    }
    media_screen=lv_obj_create(NULL);
    lv_obj_set_style_bg_color(media_screen,lv_color_hex(0x080A0C),0);
    lv_obj_set_style_bg_opa(media_screen,LV_OPA_COVER,0);
    lv_obj_set_style_border_width(media_screen,0,0);
    lv_obj_set_style_pad_all(media_screen,0,0);
    lv_obj_clear_flag(media_screen,LV_OBJ_FLAG_SCROLLABLE);
    #include "viewport_scene.inc"
    lv_label_set_text(media_title_label,"Ångström över sjön – en lång svensk låttitel");
    lv_label_set_text(media_artist_label,"Änglar, öl och Örjan – lång artisttext");
    other_screen=lv_obj_create(NULL);
    lv_obj_set_style_bg_color(other_screen,lv_color_hex(0x284560),0);
    feature_overlay=lv_obj_create(lv_layer_top());
    lv_obj_set_size(feature_overlay,240,320);
    lv_obj_add_flag(feature_overlay,LV_OBJ_FLAG_HIDDEN);
    media_record_flip.trackContext(1,clock_ms,false);
    media_record_flip.artworkInSlot(0,1,clock_ms,false);
    syncMediaArtworkDescriptor();
    lv_obj_clear_flag(media_art_image,LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(media_state_label,LV_OBJ_FLAG_HIDDEN);
    lv_scr_load(media_screen);
    lv_obj_update_layout(media_screen);
    updateMediaRecordFlip(clock_ms);
    full();
}

static void finish() {
    lv_obj_del(feature_overlay);
    lv_obj_del(other_screen);
    lv_disp_remove(display);
    lv_anim_del_all();
}

static int geometry() {
    lv_obj_update_layout(media_screen);
    const FocusMediaLayout layout=focusMediaLayout(media_focus_layout_active);
    CHECK(lv_obj_get_parent(media_art_image)==media_art_viewport);
    CHECK(lv_obj_get_parent(media_art_viewport)==media_screen);
    CHECK(lv_obj_get_parent(media_arm_layer)==media_screen);
    CHECK(lv_obj_get_parent(media_paw_layer)==media_screen);
    CHECK(lv_obj_get_index(media_art_viewport)<lv_obj_get_index(media_arm_layer));
    CHECK(lv_obj_get_index(media_arm_layer)<lv_obj_get_index(media_paw_layer));
    CHECK(lv_obj_get_x(media_art_viewport)==layout.x && lv_obj_get_y(media_art_viewport)==layout.y);
    CHECK(lv_obj_get_width(media_art_viewport)==layout.size && lv_obj_get_height(media_art_viewport)==layout.size);
    CHECK(!lv_obj_has_flag_any(media_art_viewport,LV_OBJ_FLAG_CLICKABLE|LV_OBJ_FLAG_SCROLLABLE));
    CHECK(lv_obj_get_style_bg_opa(media_art_viewport,0)==LV_OPA_TRANSP);
    CHECK(lv_obj_get_style_border_width(media_art_viewport,0)==0);
    CHECK(lv_obj_get_style_radius(media_art_viewport,0)==0);
    CHECK(lv_obj_has_flag(media_art_viewport,LV_OBJ_FLAG_OVERFLOW_VISIBLE)==media_turntable_frame.changing);
    // Existing hidden/panel early return deliberately defers the image pose.
    // The clip/parent contract still applies there; check absolute pose once
    // actually rendered, including the first frame on return to Player.
    if(!mediaRecordVisible() || lv_obj_has_flag(media_art_image,LV_OBJ_FLAG_HIDDEN)) return 0;
    const lv_img_dsc_t *source=(const lv_img_dsc_t *)lv_img_get_src(media_art_image);
    lv_area_t absolute; lv_obj_get_coords(media_art_image,&absolute);
    CHECK(absolute.x1==layout.x+layout.size/2-(int)source->header.w/2+media_turntable_frame.dx*layout.art_zoom/256);
    CHECK(absolute.y1==layout.y+layout.size/2-(int)source->header.h/2+media_turntable_frame.dy*layout.art_zoom/256);
    CHECK(lv_img_get_zoom(media_art_image)==layout.art_zoom*(source->header.w==56?2:1));
    lv_point_t pivot;lv_img_get_pivot(media_art_image,&pivot);
    CHECK(pivot.x==(int)source->header.w/2 && pivot.y==(int)source->header.h/2);
    return 0;
}

// Screen-parent reference uses the OLD independent absolute-coordinate formula.
// Projection poses compare the complete scene exactly. For steady rotation only,
// isolate the disc from antialiased arm/border compositing: LVGL's integer step
// depends on the clipped destination width. Each differing pixel must have the
// same color within one display pixel in BOTH directions, at most 32 per frame.
// Exact geometry above and full/incremental equality never have a tolerance.
static bool matchesLegacy(bool sampling=false) {
    const bool box_hidden=lv_obj_has_flag(media_art_box,LV_OBJ_FLAG_HIDDEN);
    const bool arm_hidden=lv_obj_has_flag(media_arm_layer,LV_OBJ_FLAG_HIDDEN);
    const bool paw_hidden=lv_obj_has_flag(media_paw_layer,LV_OBJ_FLAG_HIDDEN);
    if(sampling) {
        lv_obj_add_flag(media_art_box,LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(media_arm_layer,LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(media_paw_layer,LV_OBJ_FLAG_HIDDEN);
    }
    full(); memcpy(reference,pixels,sizeof(pixels));
    const int x=lv_obj_get_x(media_art_image), y=lv_obj_get_y(media_art_image);
    lv_obj_set_parent(media_art_image,media_screen);
    lv_obj_move_to_index(media_art_image,lv_obj_get_index(media_art_viewport)+1);
    const FocusMediaLayout old=focusMediaLayout(media_focus_layout_active);
    lv_obj_set_pos(media_art_image,old.x+old.size/2-lv_obj_get_width(media_art_image)/2+
                   media_turntable_frame.dx*old.art_zoom/256,
                   old.y+old.size/2-lv_obj_get_height(media_art_image)/2+
                   media_turntable_frame.dy*old.art_zoom/256);
    full();
    bool same=true;
    uint64_t differences=0;
    for(int y0=0;y0<320;++y0) for(int x0=0;x0<240;++x0) {
        const int i=y0*240+x0;
        if(reference[i].full==pixels[i].full) continue;
        ++differences;
        if(!sampling) { same=false; continue; }
        bool old_neighbor=false,new_neighbor=false;
        for(int dy=-1;dy<=1;++dy) for(int dx=-1;dx<=1;++dx) {
            const int nx=x0+dx,ny=y0+dy;
            if(nx<0||nx>=240||ny<0||ny>=320) continue;
            old_neighbor|=reference[i].full==pixels[ny*240+nx].full;
            new_neighbor|=pixels[i].full==reference[ny*240+nx].full;
        }
        if(!old_neighbor || !new_neighbor) same=false;
    }
    if(sampling) {
        measured[3]+=differences;
        measured[4]=max(measured[4],differences);
        if(differences) ++measured[5];
        const int group=lv_obj_get_width(media_art_image)==56?7:6;
        measured[group]=max(measured[group],differences);
        if(differences>32) same=false;
    }
    lv_obj_set_parent(media_art_image,media_art_viewport);
    lv_obj_set_pos(media_art_image,x,y);
    if(sampling) {
        if(!box_hidden) lv_obj_clear_flag(media_art_box,LV_OBJ_FLAG_HIDDEN);
        if(!arm_hidden) lv_obj_clear_flag(media_arm_layer,LV_OBJ_FLAG_HIDDEN);
        if(!paw_hidden) lv_obj_clear_flag(media_paw_layer,LV_OBJ_FLAG_HIDDEN);
    }
    full();
    return same;
}

static int pose(uint32_t time, bool legacy=true) {
    clock_ms=time; updateMediaRecordFlip(time);
    CHECK(geometry()==0);
    CHECK(matchesFull());
    if (legacy) CHECK(matchesLegacy());
    return 0;
}

static int rotation() {
    CHECK(geometry()==0);
    for (int compact=0;compact<2;++compact) {
        refreshFocusMediaLayout(compact!=0);
        CHECK(pose(clock_ms+20)==0);
        for (int i=0;i<200;++i) {
            clock_ms+=60; flush_pixels=0; flush_y_max=-1;
            updateMediaVinyl(clock_ms); refresh();
            CHECK(flush_y_max < 205);
            measured[0]+=flush_pixels;
            CHECK(matchesFull()); CHECK(matchesLegacy(true));
            CHECK(lv_img_get_angle(media_art_image)==media_vinyl_angle);
            CHECK(geometry()==0);
        }
        // Same source update with the legacy screen parent quantifies only
        // software flush area, never physical FPS/CPU or TFT completion time.
        const int x=lv_obj_get_x(media_art_image),y=lv_obj_get_y(media_art_image);
        const FocusMediaLayout layout=focusMediaLayout(compact!=0);
        lv_obj_set_parent(media_art_image,media_screen);
        lv_obj_move_to_index(media_art_image,lv_obj_get_index(media_art_viewport)+1);
        lv_obj_set_pos(media_art_image,x+layout.x,y+layout.y); full();
        for(int i=0;i<200;++i) {
            clock_ms+=60; flush_pixels=0;
            updateMediaVinyl(clock_ms); refresh(); measured[1]+=flush_pixels;
        }
        lv_obj_set_parent(media_art_image,media_art_viewport);
        lv_obj_set_pos(media_art_image,x,y); full();
    }
    CHECK(measured[0]>0 && measured[0]<measured[1]);
    // Existing OOM generic path doubles the zoom of the 56px source.
    media_record_pixels=NULL;
    media_record_flip.request(RecordSide::Generic,clock_ms,false);
    media_record_dirty=true;
    CHECK(pose(clock_ms+20)==0);
    CHECK(media_record_descriptor.header.w==56);
    CHECK(lv_img_get_zoom(media_art_image)==focusMediaLayout(true).art_zoom*2);
    for(int compact=0;compact<2;++compact) {
        refreshFocusMediaLayout(compact!=0);
        CHECK(pose(clock_ms+20)==0);
        for(int i=0;i<200;++i) {
            clock_ms+=60; updateMediaVinyl(clock_ms);
            CHECK(geometry()==0);
            CHECK(matchesFull()); CHECK(matchesLegacy(true));
        }
    }
    return 0;
}

static int change(uint32_t id, bool full_change, bool rapid=false) {
    const uint32_t began=clock_ms+100;
    media_track_context_id=id;
    media_record_flip.trackContext(id,began,true);
    const uint8_t slot=media_record_flip.beginArtwork();
    media_record_flip.artworkInSlot(slot,id,began+10,true);
    media_record_dirty=true;
    bool saw_outside=false,saw_full=false,saw_paw=false,saw_edge=false;
    for(uint32_t dt=0;dt<=2600;dt+=20) {
        if(rapid && dt==500) {
            media_track_context_id=id+100;
            media_record_flip.trackContext(id+100,began+dt,true);
            const uint8_t next=media_record_flip.beginArtwork();
            media_record_flip.artworkInSlot(next,id+100,began+dt+1,true);
        }
        CHECK(pose(began+dt)==0);
        saw_full|=media_turntable_frame.full;
        saw_paw|=media_turntable_frame.paw;
        saw_edge|=media_turntable_frame.changing && media_turntable_frame.height<=2;
        saw_outside|=media_turntable_frame.full && media_turntable_frame.dx < -56;
    }
    CHECK(saw_paw);
    if(full_change) CHECK(saw_full && saw_outside);
    else CHECK(saw_edge);
    CHECK(!media_turntable_frame.changing);
    return 0;
}

static int transitions() {
    // Complete stable identities exercise the model's existing every-fifth
    // full withdrawal, with all 20ms poses compared against the old scene.
    for(uint32_t id=2;id<=8;++id) CHECK(change(id,id==6,id==8)==0);
    refreshFocusMediaLayout(true);
    CHECK(pose(clock_ms+20)==0);
    for(uint32_t id=9;id<=12;++id) CHECK(change(id,id==11)==0);
    return 0;
}

static int interruptions() {
    for(int compact=0;compact<2;++compact) for(int mode=0;mode<4;++mode) {
        refreshFocusMediaLayout(compact!=0);
        CHECK(pose(clock_ms+20)==0);
        const uint32_t began=clock_ms+100;
        const uint32_t id=++media_track_context_id;
        media_record_flip.trackContext(id,began,true);
        const uint8_t slot=media_record_flip.beginArtwork();
        media_record_flip.artworkInSlot(slot,id,began+10,true);
        CHECK(pose(began+660)==0);
        CHECK(media_turntable_frame.changing);
        // All interruption paths must clear the old image under its OLD clip,
        // even before updateMediaRecordFlip's hidden/not-visible early return.
        if(mode==0) refreshFocusMediaLayout(compact==0);
        if(mode==1) {
            media_cat_mode=true;
            lv_obj_add_flag(media_art_image,LV_OBJ_FLAG_HIDDEN);
            lv_obj_clear_flag(media_cat_canvas,LV_OBJ_FLAG_HIDDEN);
            renderMediaCat();
        }
        if(mode==2) lv_obj_clear_flag(feature_overlay,LV_OBJ_FLAG_HIDDEN);
        if(mode==3) { active_panel=PanelId::Bongo; lv_scr_load(other_screen); }
        CHECK(pose(clock_ms+20,false)==0);
        CHECK(!lv_obj_has_flag(media_art_viewport,LV_OBJ_FLAG_OVERFLOW_VISIBLE));
        media_cat_mode=false; active_panel=PanelId::Player;
        lv_obj_add_flag(feature_overlay,LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(media_cat_canvas,LV_OBJ_FLAG_HIDDEN);
        lv_obj_clear_flag(media_art_image,LV_OBJ_FLAG_HIDDEN);
        lv_scr_load(media_screen);
        CHECK(pose(clock_ms+20)==0);
        CHECK(!media_turntable_frame.changing);
    }
    // Partial withdrawal followed by a layout cancellation while already far
    // outside the clip, in both directions. This is the stale-halves risk.
    for(int compact=0;compact<2;++compact) {
        while(media_record_flip.completed()%5 != 4) {
            const uint32_t next=media_track_context_id+1;
            CHECK(change(next,false)==0);
        }
        const uint32_t began=clock_ms+100;
        media_record_flip.trackContext(++media_track_context_id,began,true);
        CHECK(pose(began+1000)==0);
        CHECK(media_turntable_frame.full && media_turntable_frame.dx < -56);
        refreshFocusMediaLayout(compact==0);
        CHECK(matchesFull());
        CHECK(pose(clock_ms+20)==0);
    }
    return 0;
}

static int marqueeAndOracle() {
    CHECK(lv_label_get_long_mode(media_title_label)==LV_LABEL_LONG_SCROLL_CIRCULAR);
    full(); memcpy(reference,pixels,sizeof(pixels));
    bool text_moved=false;
    for(int i=0;i<120;++i) {
        clock_ms+=20; lv_tick_inc(20); lv_timer_handler();
        updateMediaVinyl(clock_ms);
        CHECK(matchesFull());
        if(memcmp(reference+205*240,pixels+205*240,115*240*sizeof(lv_color_t))) text_moved=true;
    }
    CHECK(text_moved);
    // Oracle sensitivity: changing actual visible pixels without invalidation
    // must differ from a full redraw. No mocked list of dirty rectangles.
    full();
    const uint8_t slot=media_art_active_buffer;
    for(int i=0;i<112*112;++i) art_storage[slot][i]=lv_color_hex(0xFFFFFF).full;
    CHECK(!matchesFull());
    lv_obj_invalidate(media_art_image); CHECK(matchesFull());
    return 0;
}

VP_EXPORT int vp_run(int test) {
    init();
    const int result=test==0?rotation():test==1?transitions():test==2?interruptions():marqueeAndOracle();
    measured[2]=compared_frames;
    finish();
    return result;
}
VP_EXPORT const char *vp_error() { return error_text; }
VP_EXPORT uint64_t vp_measure(int index) { return measured[index]; }
VP_EXPORT int vp_format_test() { return lv_snprintf(error_text,sizeof(error_text),"%d %s",17,"OK"); }
