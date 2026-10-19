#include "../src/media_turntable.h"
#include "../src/media_art_refinement.h"
typedef unsigned __int64 size_t;
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;
typedef unsigned int uint32_t;
extern "C" void *memset(void *, int, size_t);
#pragma function(memset)
extern "C" void *memset(void *p, int value, size_t bytes) {
    volatile unsigned char *out=static_cast<volatile unsigned char *>(p);
    for(size_t i=0;i<bytes;++i)out[i]=static_cast<unsigned char>(value);
    return p;
}
static MediaTurntable model;
static TurntableFrame unpack(const int *a) {
    return {static_cast<RecordSide>(a[0]),a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8],a[9],a[10]!=0,a[11]!=0,a[12]!=0};
}
static void pack(const TurntableFrame &f,int *out) {
    out[0]=static_cast<int>(f.side);out[1]=f.height;out[2]=f.dx;out[3]=f.dy;
    out[4]=f.paw_x;out[5]=f.paw_y;out[6]=f.reveal;out[7]=f.groove;
    out[8]=f.arm_engaged;out[9]=f.arm_lift;out[10]=f.changing;out[11]=f.full;out[12]=f.paw;
}
extern "C" __declspec(dllexport) void tt_reset(){model=MediaTurntable{};}
extern "C" __declspec(dllexport) void tt_times(int *out){
    const int times[]={RECORD_FLIP_FRAME_MS,TURNTABLE_CLEAR_END_MS,TURNTABLE_REACH_END_MS,
        TURNTABLE_GRIP_END_MS,TURNTABLE_LIFT_END_MS,TURNTABLE_FLIP_END_MS,TURNTABLE_FULL_OUT_END_MS,
        TURNTABLE_FULL_IN_END_MS,TURNTABLE_LOWER_END_MS,TURNTABLE_FULL_LOWER_END_MS,
        TURNTABLE_SETTLE_END_MS,TURNTABLE_FULL_SETTLE_END_MS,TURNTABLE_WITHDRAW_END_MS,
        TURNTABLE_FULL_WITHDRAW_END_MS,TURNTABLE_CHANGE_MS,TURNTABLE_FULL_MS,TURNTABLE_REVEAL_MS,
        TURNTABLE_LIFT_PIXELS};
    for(int i=0;i<18;++i)out[i]=times[i];
}
extern "C" __declspec(dllexport) int tt_event(int kind,unsigned int value,unsigned int now,int animate){
    if(kind==0)return model.request(RecordSide::Generic,now,animate!=0);
    if(kind==1)return model.trackDefault(value,now,animate!=0);
    if(kind==2)return model.trackContext(value,now,animate!=0);
    return model.artwork(now,animate!=0);
}
extern "C" __declspec(dllexport) void tt_playback(int playing,unsigned int pos,unsigned int duration){model.playback(playing!=0,pos,duration);}
extern "C" __declspec(dllexport) void tt_frame(unsigned int now,int visible,int *out){
    pack(model.frame(now,visible!=0),out);out[13]=model.changes();out[14]=model.completed();out[15]=sizeof(MediaTurntable);
}
extern "C" __declspec(dllexport) int tt_render(unsigned short *out,unsigned int capacity,const unsigned short *art,const int *frame,int sine,int cosine,const unsigned short *p){
    const RecordPalette palette={p[0],p[1],p[2],p[3],p[4]};
    return renderTurntableDisc(out,capacity,art,unpack(frame),sine,cosine,palette);
}
extern "C" __declspec(dllexport) int tt_reduced(unsigned short *out,unsigned int capacity,const unsigned short *p){
    const RecordPalette palette={p[0],p[1],p[2],p[3],p[4]};return renderTurntableGenericReduced(out,capacity,palette);
}
extern "C" __declspec(dllexport) void tt_geometry(const int *frame,int compact,int *out){
    const TurntableGeometry g=turntableGeometry(unpack(frame),compact!=0);
    out[0]=g.cx;out[1]=g.cy;out[2]=g.zoom;out[3]=g.pivot_x;out[4]=g.pivot_y;
    out[5]=g.tip_x;out[6]=g.tip_y;out[7]=g.lift;out[8]=g.paw_x;out[9]=g.paw_y;
}
extern "C" __declspec(dllexport) int tt_primitives(const int *frame,int compact,int paw,int *out,const unsigned short *p){
    const TurntablePalette palette={p[0],p[1],p[2],p[3],p[4]};TurntablePrimitive values[64];
    const int count=turntablePrimitives(unpack(frame),compact!=0,paw!=0,palette,values,64);
    for(int i=0;i<count;++i){out[i*7]=static_cast<int>(values[i].shape);out[i*7+1]=values[i].x1;
        out[i*7+2]=values[i].y1;out[i*7+3]=values[i].x2;out[i*7+4]=values[i].y2;
        out[i*7+5]=values[i].color;out[i*7+6]=values[i].width;}
    return count;
}

// Actual firmware commit/default/context/allocation and BEGIN slot selection.
constexpr int MEDIA_ART_SIZE=112,MEDIA_ART_LV_BYTES=25088,LV_IMG_CF_TRUE_COLOR_CHROMA_KEYED=1;
struct {struct {int cf,w,h;}header;int data_size;const uint8_t *data;}media_art_descriptor;
static unsigned short media_art_buffers[2][112*112];
static uint8_t media_art_active_buffer=0,media_art_receiving_buffer=1;
static MediaTurntable media_record_flip;
static MediaArtRefinementNotice media_art_refinement_notice;
static bool media_record_dirty=true,media_art_valid=true,media_art_receiving=true;
static uint32_t media_track_context_id=0,media_record_metadata_revision=0,firmware_now=0;
static struct {int aborts=0;void abort(){++aborts;}}media_art_v2;
static unsigned short *media_record_pixels=nullptr;
constexpr int MALLOC_CAP_INTERNAL=1,MALLOC_CAP_8BIT=2;
static int allocation_attempts=0;
void *heap_caps_malloc(size_t,int){++allocation_attempts;return nullptr;}
unsigned int millis(){return firmware_now;}
bool mediaRecordVisible(){return true;}
void refreshMediaUi(){}
void lv_img_cache_invalidate_src(void*){}
static struct {int writes=0;void println(const char*){++writes;}}Serial;
#include "turntable_firmware_fixture.inc"
extern "C" __declspec(dllexport) void tt_fw_reset(){
    media_record_flip=MediaTurntable{};media_record_flip.playback(true,0,200);
    media_record_flip.frame(0,true);media_record_metadata_revision=0;media_track_context_id=0;
    updateMediaTrackContext(101,0);media_record_flip.artwork(0,false);
    media_art_active_buffer=0;media_art_receiving_buffer=1;Serial.writes=0;
    for(int i=0;i<112*112;++i){media_art_buffers[0][i]=1111;media_art_buffers[1][i]=2222;}
}
extern "C" __declspec(dllexport) void tt_fw_context(unsigned int value,unsigned int now){
    firmware_now=now;media_record_flip.trackDefault(++media_record_metadata_revision,now,true);
    updateMediaTrackContext(value,now);
}
extern "C" __declspec(dllexport) void tt_fw_art(unsigned int now){firmware_now=now;activateMediaArtwork(media_art_receiving_buffer,true);}
extern "C" __declspec(dllexport) int tt_fw_begin(){fwBeginFromSource();return media_art_receiving_buffer;}
extern "C" __declspec(dllexport) void tt_fw_overwrite(){for(int i=0;i<112*112;++i)media_art_buffers[media_art_receiving_buffer][i]=3333;}
extern "C" __declspec(dllexport) int tt_fw_acks(){return Serial.writes;}
extern "C" __declspec(dllexport) void tt_fw_frame(unsigned int now,int *out){pack(media_record_flip.frame(now,true),out);out[13]=media_record_flip.changes();out[14]=media_record_flip.completed();}
extern "C" __declspec(dllexport) void tt_fw_draw(unsigned short *out,unsigned int now){
    const RecordPalette p={0,1,2,3,4};renderTurntableDisc(out,112*112,media_art_buffers[media_art_active_buffer],media_record_flip.frame(now,true),0,32768,p);
}
extern "C" __declspec(dllexport) int tt_fw_oom(){allocateMediaRecordPixels();allocateMediaRecordPixels();return allocation_attempts;}
