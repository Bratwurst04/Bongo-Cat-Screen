// Actual firmware parser/commit and codec helpers with host-only IO/UI stubs.
typedef unsigned __int64 size_t;
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;
typedef unsigned int uint32_t;
#define UINT16_MAX 65535
extern "C" void *memset(void *,int,size_t);
extern "C" void *memcpy(void *,const void *,size_t);
#pragma function(memset)
#pragma function(memcpy)
extern "C" void *memset(void *p,int v,size_t n){volatile uint8_t *o=(volatile uint8_t*)p;for(size_t i=0;i<n;++i)o[i]=(uint8_t)v;return p;}
extern "C" void *memcpy(void *p,const void *s,size_t n){volatile uint8_t *o=(volatile uint8_t*)p;const uint8_t *a=(const uint8_t*)s;for(size_t i=0;i<n;++i)o[i]=a[i];return p;}
inline void *operator new(size_t,void *p){return p;}
#include "compact_types_fixture.inc"
#include "../src/media_art_compact.h"
#include "../src/media_turntable.h"
#include "../src/media_art_refinement.h"

static bool starts(const char *text,const char *prefix){while(*prefix)if(*text++!=*prefix++)return false;return true;}
class String {
    const char *text_="";int used_=0;
public:
    String(const char *s=""):text_(s){while(s[used_])++used_;}
    int length()const{return used_;}
    const char *c_str()const{static char scratch[512];int n=used_<511?used_:511;for(int i=0;i<n;++i)scratch[i]=text_[i];scratch[n]=0;return scratch;}
    char operator[](int i)const{return text_[i];}
    bool startsWith(const char *prefix)const{int i=0;while(prefix[i]){if(i>=used_||text_[i]!=prefix[i])return false;++i;}return true;}
    int indexOf(char ch,int from=0)const{for(int i=from;i<used_;++i)if(text_[i]==ch)return i;return -1;}
    String substring(int from,int to=2147483647)const{
        String result;if(from<0)from=0;if(to>used_)to=used_;
        if(from>used_)from=used_;if(to<from)to=from;result.text_=text_+from;result.used_=to-from;return result;
    }
};
int isxdigit(int ch){return (ch>='0'&&ch<='9')||(ch>='a'&&ch<='f')||(ch>='A'&&ch<='F');}
unsigned long strtoul(const char *text,char **end,int base){
    unsigned long long value=0;
    while(*text){int n=*text>='0'&&*text<='9'?*text-'0':*text>='a'&&*text<='f'?*text-'a'+10:*text>='A'&&*text<='F'?*text-'A'+10:99;
        if(n>=base)break;value=value*base+n;++text;}
    *end=const_cast<char *>(text);return value>0xFFFFFFFFu?0xFFFFFFFFu:static_cast<unsigned long>(value);
}
// Strict base64 boundary stub; production mbedTLS is unchanged. The real
// parser's length/order/CRC/pixel/slot branches execute below.
int b64value(uint8_t ch){if(ch>='A'&&ch<='Z')return ch-'A';if(ch>='a'&&ch<='z')return ch-'a'+26;if(ch>='0'&&ch<='9')return ch-'0'+52;return ch=='+'?62:ch=='/'?63:-1;}
int mbedtls_base64_decode(uint8_t *out,size_t capacity,size_t *written,const uint8_t *input,size_t length){
    *written=0;if(length%4)return -1;
    for(size_t i=0;i<length;i+=4){int a=b64value(input[i]),b=b64value(input[i+1]),c=input[i+2]=='='?0:b64value(input[i+2]),d=input[i+3]=='='?0:b64value(input[i+3]);
        if(a<0||b<0||c<0||d<0||(i+4<length&&(input[i+2]=='='||input[i+3]=='=')))return -1;
        uint8_t bytes[3]={(uint8_t)((a<<2)|(b>>4)),(uint8_t)((b<<4)|(c>>2)),(uint8_t)((c<<6)|d)};
        unsigned count=input[i+2]=='='?1:input[i+3]=='='?2:3;
        if(*written+count>capacity)return -1;for(unsigned n=0;n<count;++n)out[(*written)++]=bytes[n];
    }return 0;
}

typedef lv_color16_t lv_color_t;
lv_color_t lv_color_make(uint8_t r,uint8_t g,uint8_t b){lv_color_t color=LV_COLOR_MAKE16(r,g,b);return color;}
constexpr int MEDIA_ART_SIZE=112,MEDIA_ART_RGB_BYTES=37632,MEDIA_ART_LV_BYTES=25088,LV_IMG_CF_TRUE_COLOR_CHROMA_KEYED=1;
static lv_color_t media_art_buffers[2][112*112];
static uint8_t media_art_active_buffer=0,media_art_receiving_buffer=1;
static size_t media_art_pixels_received=0;
static uint8_t media_art_rgb_triplet[3]={},media_art_rgb_triplet_used=0;
static uint32_t media_art_v2_started_ms=0,media_art_v2_last_chunk_ms=0,firmware_now=0;
static uint32_t media_track_context_id=0;
static bool media_art_receiving=false,media_art_compact_active=false,media_art_valid=true,media_record_dirty=true;
#ifdef BONGO_ART2_COMPACT80
static MediaArtV2Transfer media_art_v2(MEDIA_ART_RGB_BYTES,COMPACT_ART_BYTES);
#else
static MediaArtV2Transfer media_art_v2(MEDIA_ART_RGB_BYTES);
#endif
static MediaTurntable media_record_flip;
static MediaArtRefinementNotice media_art_refinement_notice;
static struct {struct {int cf,w,h;}header;int data_size;const uint8_t *data;}media_art_descriptor;
static struct {
    unsigned ok=0,error=0,last_id=0,shown=0,shown_id=0;char reason[40]={},shown_challenge[17]={};
    void println(const char*){}
    void printf(const char *format,unsigned id){last_id=id;if(starts(format,"MEDIA_ART2_OK:"))++ok;else if(starts(format,"MEDIA_ART2_ERROR:"))++error;}
    void printf(const char *format,unsigned id,const char *value){
        if(starts(format,"MEDIA_ART2_SHOWN:")){
            ++shown;shown_id=id;for(unsigned i=0;i<17;++i)shown_challenge[i]=value[i];return;
        }
        unsigned i=0;while(value[i]&&i<39){reason[i]=value[i];++i;}reason[i]=0;
    }
}Serial;
uint32_t millis(){return firmware_now;}
bool mediaRecordVisible(){return true;}
void refreshMediaUi(){}
void lv_img_cache_invalidate_src(void*){}
#include "compact_parser_fixture.inc"

extern "C" __declspec(dllexport) void ca_reset(){
#ifdef BONGO_ART2_COMPACT80
    new(&media_art_v2) MediaArtV2Transfer(MEDIA_ART_RGB_BYTES,COMPACT_ART_BYTES);
#else
    new(&media_art_v2) MediaArtV2Transfer(MEDIA_ART_RGB_BYTES);
#endif
    media_art_active_buffer=0;media_art_receiving_buffer=1;media_art_compact_active=false;
    media_track_context_id=0;
    media_art_pixels_received=0;media_art_rgb_triplet_used=0;Serial.ok=Serial.error=Serial.last_id=0;Serial.reason[0]=0;
    media_record_flip=MediaTurntable{};
    media_art_refinement_notice=MediaArtRefinementNotice{};Serial.shown=Serial.shown_id=0;Serial.shown_challenge[0]=0;
    for(int i=0;i<112*112;++i){media_art_buffers[0][i].full=1111;media_art_buffers[1][i].full=2222;}
}
extern "C" __declspec(dllexport) void ca_line(const char *line,unsigned now){firmware_now=now;handleMediaArt2Command(String(line),now);}
extern "C" __declspec(dllexport) void ca_context(unsigned id,unsigned now){firmware_now=now;updateMediaTrackContext(id,now);}
extern "C" __declspec(dllexport) int ca_active(){return media_art_active_buffer;}
extern "C" __declspec(dllexport) unsigned ca_ok(){return Serial.ok;}
extern "C" __declspec(dllexport) unsigned ca_error(){return Serial.error;}
extern "C" __declspec(dllexport) unsigned ca_id(){return Serial.last_id;}
extern "C" __declspec(dllexport) const char *ca_reason(){return Serial.reason;}
extern "C" __declspec(dllexport) unsigned ca_receiving(){return media_art_v2.active;}
extern "C" __declspec(dllexport) void ca_descriptor(int *out){out[0]=media_art_descriptor.header.w;out[1]=media_art_descriptor.header.h;out[2]=media_art_descriptor.data_size;out[3]=media_art_descriptor.data==reinterpret_cast<const uint8_t *>(media_art_buffers[media_art_active_buffer]);}
extern "C" __declspec(dllexport) void ca_snapshot(unsigned slot,uint16_t *out){for(int i=0;i<112*112;++i)out[i]=media_art_buffers[slot][i].full;}
extern "C" __declspec(dllexport) int ca_expand(uint16_t *slot,unsigned capacity){return expandCompactArtwork565(slot,capacity);}
extern "C" __declspec(dllexport) unsigned ca_color(unsigned r,unsigned g,unsigned b){return lv_color_make((uint8_t)r,(uint8_t)g,(uint8_t)b).full;}
extern "C" __declspec(dllexport) void ca_legacy_pixels(const uint8_t *rgb,uint16_t *out){for(int i=0;i<112*112;++i)out[i]=lv_color_make(rgb[i*3],rgb[i*3+1],rgb[i*3+2]).full;}
