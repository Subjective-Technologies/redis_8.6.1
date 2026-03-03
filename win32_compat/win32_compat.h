#pragma once
#ifdef _WIN32

#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <io.h>
#include <process.h>
#include <direct.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <stdint.h>
#include <time.h>
#include <errno.h>
#include <intrin.h>

/* ----------------------------------------------------------------
 * GCC __attribute__ compat
 *
 * MSVC does not understand __attribute__((...)).  Redis uses it for
 * packed structs (sds.h), unused parameters, and printf format
 * checking.  We strip the attribute entirely; x86/x64 struct
 * layouts happen to match because the SDS header fields are
 * naturally aligned.
 * ---------------------------------------------------------------- */
#ifndef __attribute__
#define __attribute__(x)
#endif

/* ----------------------------------------------------------------
 * MSVC atomic intrinsics — provide the GCC __atomic_* API so that
 * atomicvar.h's second code-path (__ATOMIC_RELAXED branch) works.
 * ---------------------------------------------------------------- */
#ifndef __ATOMIC_RELAXED
#define __ATOMIC_RELAXED 0
#endif
#ifndef __ATOMIC_SEQ_CST
#define __ATOMIC_SEQ_CST 5
#endif

/* 64-bit interlocked helpers that mirror GCC __atomic builtins.
 * Redis atomic variables are long long / unsigned long long. */
static __inline long long __atomic_add_fetch_impl(volatile long long *p, long long v) {
    return _InterlockedExchangeAdd64(p, v) + v;
}
static __inline long long __atomic_fetch_add_impl(volatile long long *p, long long v) {
    return _InterlockedExchangeAdd64(p, v);
}
static __inline long long __atomic_sub_fetch_impl(volatile long long *p, long long v) {
    return _InterlockedExchangeAdd64(p, -v) - v;
}
static __inline long long __atomic_load_n_impl(volatile long long *p) {
    long long v;
    /* x86/x64: aligned 64-bit reads are atomic. Use a compiler barrier. */
    v = *p;
    _ReadWriteBarrier();
    return v;
}
static __inline void __atomic_store_n_impl(volatile long long *p, long long v, int mo) {
    if (mo == __ATOMIC_SEQ_CST) {
        (void)_InterlockedExchange64(p, v);
    } else {
        _ReadWriteBarrier();
        *p = v;
        _ReadWriteBarrier();
    }
}
static __inline long long __atomic_exchange_n_impl(volatile long long *p, long long v) {
    return _InterlockedExchange64(p, v);
}
static __inline int __atomic_compare_exchange_n_impl(volatile long long *p,
                                                      long long *expected,
                                                      long long desired) {
    long long old = _InterlockedCompareExchange64(p, desired, *expected);
    if (old == *expected) return 1;
    *expected = old;
    return 0;
}

#define __atomic_add_fetch(p,v,o)       __atomic_add_fetch_impl((volatile long long*)(p),(long long)(v))
#define __atomic_fetch_add(p,v,o)       __atomic_fetch_add_impl((volatile long long*)(p),(long long)(v))
#define __atomic_sub_fetch(p,v,o)       __atomic_sub_fetch_impl((volatile long long*)(p),(long long)(v))
#define __atomic_load_n(p,o)            __atomic_load_n_impl((volatile long long*)(p))
#define __atomic_store_n(p,v,o)         __atomic_store_n_impl((volatile long long*)(p),(long long)(v),(o))
#define __atomic_exchange_n(p,v,o)      __atomic_exchange_n_impl((volatile long long*)(p),(long long)(v))
#define __atomic_compare_exchange_n(p,e,d,w,so,fo) \
    __atomic_compare_exchange_n_impl((volatile long long*)(p),(long long*)(e),(long long)(d))

/* POSIX-to-Win32 mappings */
#ifndef STDIN_FILENO
#define STDIN_FILENO  0
#define STDOUT_FILENO 1
#define STDERR_FILENO 2
#endif

#ifndef S_ISREG
#define S_ISREG(m) (((m) & _S_IFREG) == _S_IFREG)
#endif
#ifndef S_ISDIR
#define S_ISDIR(m) (((m) & _S_IFDIR) == _S_IFDIR)
#endif

#ifndef PATH_MAX
#define PATH_MAX MAX_PATH
#endif

/* ssize_t */
#ifndef _SSIZE_T_DEFINED
#define _SSIZE_T_DEFINED
#ifdef _WIN64
typedef __int64 ssize_t;
#else
typedef long ssize_t;
#endif
#endif

/* Map some POSIX names */
#ifndef strcasecmp
#define strcasecmp  _stricmp
#endif
#ifndef strncasecmp
#define strncasecmp _strnicmp
#endif
/* NOTE: do NOT redefine snprintf — MSVC 2015+ has a conforming one */
#ifndef getpid
#define getpid _getpid
#endif

/* Dummy definitions for signals not on Windows */
#ifndef SIGALRM
#define SIGALRM 14
#endif
#ifndef SIGHUP
#define SIGHUP 1
#endif
#ifndef SIGPIPE
#define SIGPIPE 13
#endif

#ifndef WNOHANG
#define WNOHANG 1
#endif

#ifndef _PID_T_DEFINED
#define _PID_T_DEFINED
typedef int pid_t;
#endif

/* stubs for POSIX functions Redis uses */
static __inline int kill(pid_t pid, int sig) { (void)pid; (void)sig; return -1; }

void win32_init_winsock(void);

#endif /* _WIN32 */
