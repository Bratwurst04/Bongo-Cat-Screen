/* Test-only host glue. Rendering, fonts and flush scheduling are real LVGL. */
#include <lvgl.h>
#include <stdlib.h>
#include "viewport_font_data.h"

#ifdef _MSC_VER
int _fltused = 0;
__declspec(noreturn)
#else
__attribute__((noreturn))
#endif
void vp_assert_fail(const char *file, int line) {
    (void)file;
    (void)line;
    abort();
}

/* The firmware's tiny C++ factory just copies the base and sets these fields.
 * Do that explicitly in C: /NOENTRY intentionally has no C++ CRT initializer. */
const lv_font_t *vp_title_font(void) {
    static lv_font_t font;
    font = lv_font_montserrat_16;
    font.dsc = &media_swedish_16_dsc;
    font.fallback = &lv_font_montserrat_16;
    return &font;
}
const lv_font_t *vp_artist_font(void) {
    static lv_font_t font;
    font = lv_font_montserrat_14;
    font.dsc = &media_swedish_14_dsc;
    font.fallback = &lv_font_montserrat_14;
    return &font;
}
