#pragma once
// MSVC x64 varargs ABI. LVGL's own formatter remains the implementation.
typedef char *va_list;
#ifdef __cplusplus
extern "C" {
#endif
void __cdecl __va_start(va_list *, ...);
#ifdef __cplusplus
}
#endif
#pragma intrinsic(__va_start)
#define va_start(ap, last) ((void)__va_start(&(ap), last))
#define va_end(ap) ((void)((ap) = (va_list)0))
#define va_copy(dst, src) ((void)((dst) = (src)))
#define va_arg(ap, type) ((sizeof(type) > 8 || (sizeof(type) & (sizeof(type)-1))) ? \
    **(type **)(((ap) += 8)-8) : *(type *)(((ap) += 8)-8))
