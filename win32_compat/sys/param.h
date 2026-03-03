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
