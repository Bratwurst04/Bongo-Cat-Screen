// Existing strict parser/CRC/codec fixture, with real production slot staging.
#include "compact_art_host.cpp"
static size_t media_art_expected=0,media_art_received=0;
static uint32_t media_art_last_byte_ms=0,media_record_metadata_revision=0;
#include "face_events_fixture.inc"

static TurntableFrame face_frame;
static void packFace(const TurntableFrame &f,int *out){
    out[0]=(int)f.side;out[1]=f.height;out[2]=f.dx;out[3]=f.dy;
    out[4]=f.paw_x;out[5]=f.paw_y;out[6]=f.reveal;out[7]=f.groove;
    out[8]=f.arm_engaged;out[9]=f.arm_lift;out[10]=f.changing;out[11]=f.full;out[12]=f.paw;
    out[13]=media_record_flip.changes();out[14]=media_record_flip.completed();out[15]=sizeof(MediaTurntable);
}
static TurntableFrame unpackFace(const int *a){
    return {(RecordSide)a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8],a[9],a[10]!=0,a[11]!=0,a[12]!=0};
}
extern "C" __declspec(dllexport) void ff_frame(unsigned now,int visible,int *out){
    firmware_now=now;face_frame=media_record_flip.frame(now,visible!=0);
    // Exactly the production frame-to-descriptor hook; no RX can interleave.
    if(media_art_active_buffer!=media_record_flip.visibleSlot())syncMediaArtworkDescriptor();
    packFace(face_frame,out);
    serviceMediaArtShown(face_frame);
}
extern "C" __declspec(dllexport) void ff_generation(const char *challenge){setMediaArtRefinementGeneration(challenge);}
extern "C" __declspec(dllexport) unsigned ff_shown(){return Serial.shown;}
extern "C" __declspec(dllexport) unsigned ff_shown_id(){return Serial.shown_id;}
extern "C" __declspec(dllexport) const char *ff_shown_challenge(){return Serial.shown_challenge;}
extern "C" __declspec(dllexport) void ff_default(){fwDefaultFromSource();}
extern "C" __declspec(dllexport) void ff_none(){fwNoneFromSource();}
extern "C" __declspec(dllexport) void ff_raw_begin(){fwRawBeginFromSource();}
extern "C" __declspec(dllexport) void ff_raw(const uint8_t *data,unsigned size){consumeQueuedMediaArtwork(data,size);}
extern "C" __declspec(dllexport) unsigned ff_receiving_slot(){return media_art_receiving_buffer;}
extern "C" __declspec(dllexport) void ff_play(int playing,unsigned pos,unsigned duration){media_record_flip.playback(playing!=0,pos,duration);}
extern "C" __declspec(dllexport) int tt_render(unsigned short *out,unsigned capacity,const unsigned short *art,const int *f,int sine,int cosine,const unsigned short *p){
    RecordPalette palette={p[0],p[1],p[2],p[3],p[4]};return renderTurntableDisc(out,capacity,art,unpackFace(f),sine,cosine,palette);
}
extern "C" __declspec(dllexport) void tt_geometry(const int *f,int compact,int *out){
    auto g=turntableGeometry(unpackFace(f),compact!=0);
    out[0]=g.cx;out[1]=g.cy;out[2]=g.zoom;out[3]=g.pivot_x;out[4]=g.pivot_y;
    out[5]=g.tip_x;out[6]=g.tip_y;out[7]=g.lift;out[8]=g.paw_x;out[9]=g.paw_y;
}
extern "C" __declspec(dllexport) int tt_primitives(const int *f,int compact,int paw,int *out,const unsigned short *p){
    TurntablePalette palette={p[0],p[1],p[2],p[3],p[4]};TurntablePrimitive values[64];
    int count=turntablePrimitives(unpackFace(f),compact!=0,paw!=0,palette,values,64);
    for(int i=0;i<count;++i){out[i*7]=(int)values[i].shape;out[i*7+1]=values[i].x1;out[i*7+2]=values[i].y1;
        out[i*7+3]=values[i].x2;out[i*7+4]=values[i].y2;out[i*7+5]=values[i].color;out[i*7+6]=values[i].width;}
    return count;
}
