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
