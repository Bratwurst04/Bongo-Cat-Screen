#pragma once
// Test-only Windows x64 C ABI declarations for the existing compiler/CRT.
typedef unsigned __int64 size_t;
typedef __int64 ptrdiff_t;
#ifndef NULL
#define NULL 0
#endif
#define offsetof(type, member) ((size_t)&(((type *)0)->member))
