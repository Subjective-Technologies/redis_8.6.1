#pragma once
#include <windows.h>
#define RTLD_NOW  0
#define RTLD_LOCAL 0
static __inline void *dlopen(const char *f, int m) { (void)m; return (void*)LoadLibraryA(f); }
static __inline int dlclose(void *h) { return FreeLibrary((HMODULE)h) ? 0 : -1; }
static __inline void *dlsym(void *h, const char *s) { return (void*)GetProcAddress((HMODULE)h, s); }
static __inline const char *dlerror(void) { return "dlopen not supported"; }
