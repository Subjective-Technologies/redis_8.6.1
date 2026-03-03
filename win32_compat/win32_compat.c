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
