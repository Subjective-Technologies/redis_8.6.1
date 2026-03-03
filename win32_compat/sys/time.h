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
