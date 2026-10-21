#pragma once
#include <stddef.h>
#include <stdarg.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct _iobuf FILE;
int printf(const char *, ...);
int puts(const char *);
int putchar(int);
int snprintf(char *, size_t, const char *, ...);
int vsnprintf(char *, size_t, const char *, va_list);
#ifdef __cplusplus
}
#endif
