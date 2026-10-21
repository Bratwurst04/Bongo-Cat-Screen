// Host reference only; both included inputs are verified/copied by the audit.
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;
#include "lvgl_color16.inc"
#include "media_art_compact.h"

extern "C" __declspec(dllexport) unsigned quality_color(unsigned r,unsigned g,unsigned b) {
    lv_color16_t color=LV_COLOR_MAKE16(r,g,b);
    return color.full;
}
extern "C" __declspec(dllexport) void quality_full(const uint8_t *rgb,uint16_t *out) {
    for(int i=0;i<112*112;++i) {
        lv_color16_t color=LV_COLOR_MAKE16(rgb[i*3],rgb[i*3+1],rgb[i*3+2]);
        out[i]=color.full;
    }
}
extern "C" __declspec(dllexport) int quality_expand(uint16_t *slot) {
    return expandCompactArtwork565(slot,112*112);
}
