#pragma once
#include <windows.h>
#define PROT_READ  1
#define PROT_WRITE 2
#define MAP_PRIVATE 0x02
#define MAP_ANONYMOUS 0x20
#define MAP_FAILED ((void *)-1)
static __inline void *mmap(void *a, size_t l, int p, int f, int fd, long o) {
    (void)a;(void)p;(void)f;(void)fd;(void)o;
    return VirtualAlloc(NULL, l, MEM_COMMIT|MEM_RESERVE, PAGE_READWRITE);
}
static __inline int munmap(void *a, size_t l) { (void)l; return VirtualFree(a, 0, MEM_RELEASE) ? 0 : -1; }
