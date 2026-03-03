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
