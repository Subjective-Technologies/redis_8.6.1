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
