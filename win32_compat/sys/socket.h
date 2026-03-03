#pragma once
#include <winsock2.h>
#include <ws2tcpip.h>
/* Map POSIX socket types/constants to Winsock equivalents */
#ifndef AF_LOCAL
#define AF_LOCAL AF_UNIX
#endif
