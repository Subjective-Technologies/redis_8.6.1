##############################################################################
# CMakeLists.txt – Redis 8.6.1 (Windows / MSVC build)
#
# This file enables building Redis with CMake + Visual Studio on Windows.
# On Linux/macOS the traditional Makefile is still preferred.
##############################################################################
cmake_minimum_required(VERSION 3.20)
project(redis VERSION 8.6.1 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------
option(BUILD_TLS       "Build with TLS (OpenSSL) support" OFF)
option(USE_JEMALLOC    "Use jemalloc allocator (Linux only)" OFF)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
set(REDIS_SRC   "${CMAKE_CURRENT_SOURCE_DIR}/src")
set(REDIS_DEPS  "${CMAKE_CURRENT_SOURCE_DIR}/deps")

# ---------------------------------------------------------------------------
# Platform defines
# ---------------------------------------------------------------------------
if(WIN32)
    add_definitions(
        -D_CRT_SECURE_NO_WARNINGS
        -D_CRT_NONSTDC_NO_DEPRECATE
        -DWIN32_LEAN_AND_MEAN
        -DREDIS_STATIC=
        -DNO_BACKTRACE
    )
    # ae.c #includes the backend .c file based on these defines.
    # Windows has none of HAVE_EPOLL/HAVE_KQUEUE/HAVE_EVPORT, so ae.c
    # falls through to #include "ae_select.c" automatically.
elseif(APPLE)
    add_definitions(
        -DREDIS_STATIC=
        -DHAVE_KQUEUE
    )
else()
    add_definitions(
        -DREDIS_STATIC=
        -DHAVE_PROC_STAT
        -DHAVE_PROC_MAPS
        -DHAVE_EPOLL
        -DHAVE_MSG_NOSIGNAL
        -DHAVE_ACCEPT4
        -DHAVE_PIPE2
    )
endif()

# ---------------------------------------------------------------------------
# Generate release.h (normally done by mkreleasehdr.sh)
# ---------------------------------------------------------------------------
if(NOT EXISTS "${REDIS_SRC}/release.h")
    file(WRITE "${REDIS_SRC}/release.h"
        "#define REDIS_GIT_SHA1 \"00000000\"\n"
        "#define REDIS_GIT_DIRTY \"0\"\n"
        "#define REDIS_BUILD_ID \"0\"\n"
    )
endif()

# ---------------------------------------------------------------------------
# Windows compatibility shim
# ---------------------------------------------------------------------------
set(WIN32_COMPAT_DIR "${CMAKE_CURRENT_SOURCE_DIR}/win32_compat")
if(WIN32 AND NOT EXISTS "${WIN32_COMPAT_DIR}")
    file(MAKE_DIRECTORY "${WIN32_COMPAT_DIR}")
endif()

if(WIN32)
    # Generate POSIX-compat headers that Redis sources expect on Unix

    # --- win32_compat.h (master compat header) ---
    file(WRITE "${WIN32_COMPAT_DIR}/win32_compat.h" [=[
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
]=])

    # --- unistd.h (stub so #include <unistd.h> works) ---
    file(WRITE "${WIN32_COMPAT_DIR}/unistd.h" [=[
#pragma once
/* Minimal unistd.h shim for MSVC */
#include <io.h>
#include <process.h>
#include <direct.h>
#include <stdint.h>

#ifndef STDIN_FILENO
#define STDIN_FILENO  0
#define STDOUT_FILENO 1
#define STDERR_FILENO 2
#endif

#ifndef _SSIZE_T_DEFINED
#define _SSIZE_T_DEFINED
#ifdef _WIN64
typedef __int64 ssize_t;
#else
typedef long ssize_t;
#endif
#endif

#ifndef _PID_T_DEFINED
#define _PID_T_DEFINED
typedef int pid_t;
#endif

#define access _access
#define F_OK 0
#define R_OK 4
#define W_OK 2
#define X_OK 0  /* no execute check on Windows */

#define getcwd _getcwd
#define chdir  _chdir
#define isatty _isatty
#define fileno _fileno
#define lseek  _lseek
#define close  _close
#define read   _read
#define write  _write
#define dup    _dup
#define dup2   _dup2
#define unlink _unlink
#define rmdir  _rmdir
#define usleep(us) Sleep((us) / 1000)
#define sleep(s)   Sleep((s) * 1000)

static __inline int fork(void) { return -1; /* not supported */ }
static __inline unsigned int alarm(unsigned int s) { (void)s; return 0; }
]=])

    # --- sys/select.h (stub — Winsock provides select) ---
    file(WRITE "${WIN32_COMPAT_DIR}/sys/select.h" [=[
#pragma once
/* On Windows, select() comes from winsock2.h */
#include <winsock2.h>
]=])

    # --- sys/wait.h (stub) ---
    file(WRITE "${WIN32_COMPAT_DIR}/sys/wait.h" [=[
#pragma once
#ifndef _PID_T_DEFINED
#define _PID_T_DEFINED
typedef int pid_t;
#endif
#ifndef WNOHANG
#define WNOHANG 1
#endif
#define WIFEXITED(s)   1
#define WEXITSTATUS(s) (s)
#define WIFSIGNALED(s) 0
#define WTERMSIG(s)    0
static __inline pid_t waitpid(pid_t p, int *s, int o) { (void)p; (void)o; if(s) *s=0; return -1; }
static __inline pid_t wait3(int *s, int o, void *r) { (void)o; (void)r; if(s) *s=0; return -1; }
]=])

    # --- sys/time.h (stub — map gettimeofday + clock_gettime) ---
    file(WRITE "${WIN32_COMPAT_DIR}/sys/time.h" [=[
#pragma once
#include <winsock2.h>  /* struct timeval */
#include <time.h>
#ifndef _TIMEVAL_DEFINED
#define _TIMEVAL_DEFINED
#endif
/* POSIX clock IDs — Windows uses QueryPerformanceCounter instead,
 * but Redis's monotonic.c checks for CLOCK_MONOTONIC at compile time. */
#ifndef CLOCK_MONOTONIC
#define CLOCK_MONOTONIC 1
#endif
#ifndef CLOCK_REALTIME
#define CLOCK_REALTIME 0
#endif
#ifndef HAVE_CLOCK_GETTIME
#define HAVE_CLOCK_GETTIME 0
#endif
]=])

    # --- sys/param.h (stub) ---
    file(WRITE "${WIN32_COMPAT_DIR}/sys/param.h" [=[
#pragma once
/* Minimal sys/param.h stub for Windows */
#ifndef MAXPATHLEN
#define MAXPATHLEN 260
#endif
#ifndef BYTE_ORDER
#define LITTLE_ENDIAN 1234
#define BIG_ENDIAN    4321
#define BYTE_ORDER    LITTLE_ENDIAN
#endif
]=])

    # --- sys/resource.h (stub) ---
    file(WRITE "${WIN32_COMPAT_DIR}/sys/resource.h" [=[
#pragma once
#define RLIMIT_NOFILE 7
struct rlimit { unsigned long long rlim_cur; unsigned long long rlim_max; };
static __inline int getrlimit(int r, struct rlimit *l) { (void)r; l->rlim_cur=1024; l->rlim_max=4096; return 0; }
static __inline int setrlimit(int r, const struct rlimit *l) { (void)r; (void)l; return -1; }
#define RUSAGE_SELF 0
struct rusage { struct { long tv_sec; long tv_usec; } ru_utime, ru_stime; long ru_maxrss; };
static __inline int getrusage(int w, struct rusage *u) { (void)w; memset(u,0,sizeof(*u)); return 0; }
]=])

    # --- sys/uio.h (stub for writev/readv) ---
    file(WRITE "${WIN32_COMPAT_DIR}/sys/uio.h" [=[
#pragma once
struct iovec { void *iov_base; size_t iov_len; };
]=])

    # --- sys/mman.h (stub) ---
    file(WRITE "${WIN32_COMPAT_DIR}/sys/mman.h" [=[
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
]=])

    # --- strings.h (stub) ---
    file(WRITE "${WIN32_COMPAT_DIR}/strings.h" [=[
#pragma once
#include <string.h>
#ifndef strcasecmp
#define strcasecmp  _stricmp
#endif
#ifndef strncasecmp
#define strncasecmp _strnicmp
#endif
#define bzero(b,len) memset((b), 0, (len))
#define bcopy(s,d,n) memmove((d),(s),(n))
]=])

    # --- sys/socket.h (stub — Winsock provides socket API) ---
    file(WRITE "${WIN32_COMPAT_DIR}/sys/socket.h" [=[
#pragma once
#include <winsock2.h>
#include <ws2tcpip.h>
/* Map POSIX socket types/constants to Winsock equivalents */
#ifndef AF_LOCAL
#define AF_LOCAL AF_UNIX
#endif
]=])

    # --- netinet/in.h, netinet/tcp.h, arpa/inet.h, netdb.h, poll.h (stubs) ---
    file(WRITE "${WIN32_COMPAT_DIR}/netinet/in.h"  "#pragma once\n#include <winsock2.h>\n#include <ws2tcpip.h>\n")
    file(WRITE "${WIN32_COMPAT_DIR}/netinet/tcp.h" "#pragma once\n#include <winsock2.h>\n#include <ws2tcpip.h>\n")
    file(WRITE "${WIN32_COMPAT_DIR}/arpa/inet.h"   "#pragma once\n#include <winsock2.h>\n#include <ws2tcpip.h>\n")
    file(WRITE "${WIN32_COMPAT_DIR}/netdb.h"       "#pragma once\n#include <winsock2.h>\n#include <ws2tcpip.h>\n")
    file(WRITE "${WIN32_COMPAT_DIR}/poll.h"        "#pragma once\n#include <winsock2.h>\n")

    # --- syslog.h (stub) ---
    file(WRITE "${WIN32_COMPAT_DIR}/syslog.h" [=[
#pragma once
#define LOG_DEBUG   7
#define LOG_INFO    6
#define LOG_NOTICE  5
#define LOG_WARNING 4
#define LOG_ERR     3
#define LOG_LOCAL0  (16<<3)
static __inline void openlog(const char *i, int o, int f) { (void)i;(void)o;(void)f; }
static __inline void syslog(int p, const char *f, ...) { (void)p;(void)f; }
static __inline void closelog(void) {}
]=])

    # --- pthread.h (minimal stub) ---
    file(WRITE "${WIN32_COMPAT_DIR}/pthread.h" [=[
#pragma once
#include <windows.h>
typedef HANDLE pthread_t;
typedef CRITICAL_SECTION pthread_mutex_t;
typedef CONDITION_VARIABLE pthread_cond_t;
typedef int pthread_attr_t;
typedef int pthread_mutexattr_t;
typedef int pthread_condattr_t;
#define PTHREAD_MUTEX_INITIALIZER {0}
static __inline int pthread_mutex_init(pthread_mutex_t *m, const pthread_mutexattr_t *a) { (void)a; InitializeCriticalSection(m); return 0; }
static __inline int pthread_mutex_destroy(pthread_mutex_t *m) { DeleteCriticalSection(m); return 0; }
static __inline int pthread_mutex_lock(pthread_mutex_t *m) { EnterCriticalSection(m); return 0; }
static __inline int pthread_mutex_unlock(pthread_mutex_t *m) { LeaveCriticalSection(m); return 0; }
static __inline int pthread_cond_init(pthread_cond_t *c, const pthread_condattr_t *a) { (void)a; InitializeConditionVariable(c); return 0; }
static __inline int pthread_cond_destroy(pthread_cond_t *c) { (void)c; return 0; }
static __inline int pthread_cond_signal(pthread_cond_t *c) { WakeConditionVariable(c); return 0; }
static __inline int pthread_cond_broadcast(pthread_cond_t *c) { WakeAllConditionVariable(c); return 0; }
static __inline int pthread_cond_wait(pthread_cond_t *c, pthread_mutex_t *m) { SleepConditionVariableCS(c, m, INFINITE); return 0; }
]=])

    # --- dlfcn.h (stub for module loading) ---
    file(WRITE "${WIN32_COMPAT_DIR}/dlfcn.h" [=[
#pragma once
#include <windows.h>
#define RTLD_NOW  0
#define RTLD_LOCAL 0
static __inline void *dlopen(const char *f, int m) { (void)m; return (void*)LoadLibraryA(f); }
static __inline int dlclose(void *h) { return FreeLibrary((HMODULE)h) ? 0 : -1; }
static __inline void *dlsym(void *h, const char *s) { return (void*)GetProcAddress((HMODULE)h, s); }
static __inline const char *dlerror(void) { return "dlopen not supported"; }
]=])

    # --- win32_compat.c ---
    file(WRITE "${WIN32_COMPAT_DIR}/win32_compat.c" [=[
#ifdef _WIN32
#include "win32_compat.h"
#include <stdio.h>
#include <string.h>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "advapi32.lib")

static int _winsock_initialized = 0;
void win32_init_winsock(void) {
    if (!_winsock_initialized) {
        WSADATA wsa;
        WSAStartup(MAKEWORD(2, 2), &wsa);
        _winsock_initialized = 1;
    }
}

#endif /* _WIN32 */
]=])
endif()

# ---------------------------------------------------------------------------
# Dependency libraries (built as static libs)
# ---------------------------------------------------------------------------

# --- hiredis ---
file(GLOB HIREDIS_SOURCES "${REDIS_DEPS}/hiredis/*.c")
# Remove test/example files
list(FILTER HIREDIS_SOURCES EXCLUDE REGEX "(test|example|ssl)")
add_library(hiredis STATIC ${HIREDIS_SOURCES})
target_include_directories(hiredis PUBLIC "${REDIS_DEPS}/hiredis")
if(WIN32)
    target_compile_definitions(hiredis PRIVATE _CRT_SECURE_NO_WARNINGS _CRT_NONSTDC_NO_DEPRECATE)
    target_include_directories(hiredis BEFORE PRIVATE "${WIN32_COMPAT_DIR}")
    target_link_libraries(hiredis PUBLIC ws2_32)
endif()

# --- lua ---
set(LUA_SOURCES
    lapi.c lcode.c ldebug.c ldo.c ldump.c lfunc.c lgc.c llex.c lmem.c
    lobject.c lopcodes.c lparser.c lstate.c lstring.c ltable.c ltm.c
    lundump.c lvm.c lzio.c strbuf.c fpconv.c
    lauxlib.c lbaselib.c ldblib.c liolib.c lmathlib.c loslib.c
    ltablib.c lstrlib.c loadlib.c linit.c
    lua_cjson.c lua_struct.c lua_cmsgpack.c lua_bit.c
)
list(TRANSFORM LUA_SOURCES PREPEND "${REDIS_DEPS}/lua/src/")
add_library(lua STATIC ${LUA_SOURCES})
target_include_directories(lua PUBLIC "${REDIS_DEPS}/lua/src")
target_compile_definitions(lua PRIVATE
    ENABLE_CJSON_GLOBAL
    LUA_ANSI
    _CRT_SECURE_NO_WARNINGS
)
if(WIN32)
    target_include_directories(lua PRIVATE "${WIN32_COMPAT_DIR}")
    # MSVC needs FI (force-include) stdint.h so INT32_MIN is visible in lua_bit.c
    target_compile_options(lua PRIVATE /FI"stdint.h")
endif()

# --- hdr_histogram ---
add_library(hdr_histogram STATIC "${REDIS_DEPS}/hdr_histogram/hdr_histogram.c")
target_include_directories(hdr_histogram PUBLIC "${REDIS_DEPS}/hdr_histogram")
# Redis ships hdr_redis_malloc.h instead of hdr_malloc.h
target_compile_definitions(hdr_histogram PRIVATE
    HDR_MALLOC_INCLUDE="hdr_redis_malloc.h"
)
if(WIN32)
    target_compile_definitions(hdr_histogram PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()

# --- fpconv ---
add_library(fpconv STATIC "${REDIS_DEPS}/fpconv/fpconv_dtoa.c")
target_include_directories(fpconv PUBLIC "${REDIS_DEPS}/fpconv")

# --- fast_float (C++) ---
add_library(fast_float STATIC "${REDIS_DEPS}/fast_float/fast_float_strtod.cpp")
target_include_directories(fast_float PUBLIC "${REDIS_DEPS}/fast_float")

# --- xxhash ---
add_library(xxhash STATIC "${REDIS_DEPS}/xxhash/xxhash.c")
target_include_directories(xxhash PUBLIC "${REDIS_DEPS}/xxhash")

# --- linenoise (only for redis-cli; skip on Windows — uses termios.h) ---
if(NOT WIN32 AND EXISTS "${REDIS_DEPS}/linenoise/linenoise.c")
    add_library(linenoise STATIC "${REDIS_DEPS}/linenoise/linenoise.c")
    target_include_directories(linenoise PUBLIC "${REDIS_DEPS}/linenoise")
endif()

# ---------------------------------------------------------------------------
# Common include directories for Redis sources
# ---------------------------------------------------------------------------
set(REDIS_INCLUDE_DIRS
    "${REDIS_SRC}"
    "${REDIS_DEPS}/hiredis"
    "${REDIS_DEPS}/linenoise"
    "${REDIS_DEPS}/lua/src"
    "${REDIS_DEPS}/hdr_histogram"
    "${REDIS_DEPS}/fpconv"
    "${REDIS_DEPS}/fast_float"
    "${REDIS_DEPS}/xxhash"
)
if(WIN32)
    # Win32 compat dir must come FIRST so our stub headers (unistd.h,
    # sys/select.h, etc.) are found before the compiler looks for them.
    list(PREPEND REDIS_INCLUDE_DIRS "${WIN32_COMPAT_DIR}")
endif()

# ---------------------------------------------------------------------------
# redis-server
# ---------------------------------------------------------------------------
set(REDIS_SERVER_SOURCES
    threads_mngr.c memory_prefetch.c adlist.c quicklist.c ae.c
    anet.c dict.c ebuckets.c eventnotifier.c iothread.c mstr.c entry.c
    kvstore.c fwtree.c estore.c server.c sds.c zmalloc.c lzf_c.c lzf_d.c
    pqsort.c zipmap.c sha1.c ziplist.c release.c networking.c util.c
    object.c db.c replication.c rdb.c t_string.c t_list.c t_set.c t_zset.c
    t_hash.c config.c aof.c pubsub.c multi.c debug.c sort.c intset.c
    syncio.c cluster.c cluster_legacy.c cluster_slot_stats.c crc16.c
    endianconv.c slowlog.c eval.c bio.c rio.c rand.c memtest.c syscheck.c
    crcspeed.c crccombine.c crc64.c bitops.c sentinel.c notify.c
    setproctitle.c blocked.c hyperloglog.c latency.c sparkline.c
    redis-check-rdb.c redis-check-aof.c geo.c lazyfree.c module.c evict.c
    expire.c geohash.c geohash_helper.c childinfo.c defrag.c siphash.c
    rax.c t_stream.c listpack.c localtime.c lolwut.c lolwut5.c lolwut6.c
    lolwut8.c acl.c tracking.c socket.c tls.c sha256.c timeout.c
    setcpuaffinity.c monotonic.c mt19937-64.c resp_parser.c call_reply.c
    script_lua.c script.c functions.c function_lua.c commands.c strl.c
    connection.c unix.c logreqres.c keymeta.c chk.c hotkeys.c
)
# Skip cluster_asm.c on MSVC (x86 asm, not needed)
if(NOT MSVC)
    list(APPEND REDIS_SERVER_SOURCES cluster_asm.c)
endif()

list(TRANSFORM REDIS_SERVER_SOURCES PREPEND "${REDIS_SRC}/")
# ae.c #includes the platform-specific backend (ae_select.c, ae_epoll.c, ae_kqueue.c)
# internally, so we do NOT add AE_SOURCE as a separate translation unit.
if(WIN32)
    list(APPEND REDIS_SERVER_SOURCES "${WIN32_COMPAT_DIR}/win32_compat.c")
endif()

add_executable(redis-server ${REDIS_SERVER_SOURCES})
target_include_directories(redis-server PRIVATE ${REDIS_INCLUDE_DIRS})
target_link_libraries(redis-server PRIVATE
    hiredis lua hdr_histogram fpconv fast_float xxhash
)
if(WIN32)
    target_link_libraries(redis-server PRIVATE ws2_32 advapi32)
    target_compile_definitions(redis-server PRIVATE
        _CRT_SECURE_NO_WARNINGS
        _CRT_NONSTDC_NO_DEPRECATE
    )
    # Force-include the compat header so every .c file gets POSIX type
    # definitions (ssize_t, pid_t, etc.) before any Redis header.
    target_compile_options(redis-server PRIVATE /FI"win32_compat.h")
elseif(APPLE)
    target_link_libraries(redis-server PRIVATE m dl pthread)
else()
    target_link_libraries(redis-server PRIVATE m dl pthread rt stdc++)
endif()

# ---------------------------------------------------------------------------
# redis-cli
# ---------------------------------------------------------------------------
set(REDIS_CLI_SOURCES
    anet.c adlist.c dict.c redis-cli.c zmalloc.c release.c ae.c
    redisassert.c crcspeed.c crccombine.c crc64.c siphash.c crc16.c
    monotonic.c cli_common.c mt19937-64.c strl.c cli_commands.c
)
list(TRANSFORM REDIS_CLI_SOURCES PREPEND "${REDIS_SRC}/")
# ae.c #includes its own backend; do not add AE_SOURCE separately.
if(WIN32)
    list(APPEND REDIS_CLI_SOURCES "${WIN32_COMPAT_DIR}/win32_compat.c")
endif()

add_executable(redis-cli ${REDIS_CLI_SOURCES})
target_include_directories(redis-cli PRIVATE ${REDIS_INCLUDE_DIRS})
target_link_libraries(redis-cli PRIVATE hiredis hdr_histogram)
if(TARGET linenoise)
    target_link_libraries(redis-cli PRIVATE linenoise)
endif()
if(WIN32)
    target_link_libraries(redis-cli PRIVATE ws2_32 advapi32)
    target_compile_definitions(redis-cli PRIVATE
        _CRT_SECURE_NO_WARNINGS
        _CRT_NONSTDC_NO_DEPRECATE
    )
    target_compile_options(redis-cli PRIVATE /FI"win32_compat.h")
elseif(NOT APPLE)
    target_link_libraries(redis-cli PRIVATE m pthread stdc++)
else()
    target_link_libraries(redis-cli PRIVATE m pthread)
endif()

# ---------------------------------------------------------------------------
# redis-benchmark
# ---------------------------------------------------------------------------
set(REDIS_BENCHMARK_SOURCES
    ae.c anet.c redis-benchmark.c adlist.c dict.c zmalloc.c
    redisassert.c release.c crcspeed.c crccombine.c crc64.c siphash.c
    crc16.c monotonic.c cli_common.c mt19937-64.c strl.c
)
list(TRANSFORM REDIS_BENCHMARK_SOURCES PREPEND "${REDIS_SRC}/")
# ae.c #includes its own backend; do not add AE_SOURCE separately.
if(WIN32)
    list(APPEND REDIS_BENCHMARK_SOURCES "${WIN32_COMPAT_DIR}/win32_compat.c")
endif()

add_executable(redis-benchmark ${REDIS_BENCHMARK_SOURCES})
target_include_directories(redis-benchmark PRIVATE ${REDIS_INCLUDE_DIRS})
target_link_libraries(redis-benchmark PRIVATE hiredis hdr_histogram)
if(WIN32)
    target_link_libraries(redis-benchmark PRIVATE ws2_32 advapi32)
    target_compile_definitions(redis-benchmark PRIVATE
        _CRT_SECURE_NO_WARNINGS
        _CRT_NONSTDC_NO_DEPRECATE
    )
    target_compile_options(redis-benchmark PRIVATE /FI"win32_compat.h")
elseif(NOT APPLE)
    target_link_libraries(redis-benchmark PRIVATE m pthread stdc++)
else()
    target_link_libraries(redis-benchmark PRIVATE m pthread)
endif()

# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------
install(TARGETS redis-server redis-cli redis-benchmark
    RUNTIME DESTINATION bin
)
