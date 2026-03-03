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
