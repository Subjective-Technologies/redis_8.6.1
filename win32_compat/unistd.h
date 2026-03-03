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
