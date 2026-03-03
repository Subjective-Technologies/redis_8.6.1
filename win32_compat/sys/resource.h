#pragma once
#define RLIMIT_NOFILE 7
struct rlimit { unsigned long long rlim_cur; unsigned long long rlim_max; };
static __inline int getrlimit(int r, struct rlimit *l) { (void)r; l->rlim_cur=1024; l->rlim_max=4096; return 0; }
static __inline int setrlimit(int r, const struct rlimit *l) { (void)r; (void)l; return -1; }
#define RUSAGE_SELF 0
struct rusage { struct { long tv_sec; long tv_usec; } ru_utime, ru_stime; long ru_maxrss; };
static __inline int getrusage(int w, struct rusage *u) { (void)w; memset(u,0,sizeof(*u)); return 0; }
