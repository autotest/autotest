// Simple application that creates a server socket, listening for connections
// of the unattended install test. Once it gets a client connected, the
// app will send back an ACK string, indicating the install process is done.
//
// You must link this code with Ws2_32.lib, Mswsock.lib, and Advapi32.lib
//
// Author: Lucas Meneghel Rodrigues <lmr@redhat.com>
// Code was adapted from an MSDN sample.

// Usage: finish.exe

#ifdef __MINGW32__
#undef _WIN32_WINNT
#define _WIN32_WINNT 0x500
#endif

#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <stdlib.h>
#include <stdio.h>

int DEFAULT_PORT = 12323;

void ExitOnError(const char *message, BOOL winsock = FALSE)
{
    LPVOID system_message;
    char buffer[512];
    int error_code;

    if (winsock)
        error_code = WSAGetLastError();
    else
        error_code = GetLastError();
    WSACleanup();

    FormatMessage(FORMAT_MESSAGE_ALLOCATE_BUFFER |
                  FORMAT_MESSAGE_FROM_SYSTEM,
                  NULL,
                  error_code,
                  MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
                  (LPTSTR)&system_message,
                  0,
                  NULL);

    sprintf(buffer,
            "%s!\n"
            "Error code = %d\n"
            "Error message = %s",
            message, error_code, (char *)system_message);

    MessageBox(NULL, buffer, "Error", MB_OK | MB_ICONERROR);

    LocalFree(system_message);
    ExitProcess(1);
}

SOCKET PrepareListenSocket(int port)
{
    sockaddr_in addr;
    linger l;
    int result;

    // Create socket
    SOCKET ListenSocket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (ListenSocket == INVALID_SOCKET)
        ExitOnError("Socket creation failed", TRUE);

    // Enable lingering
    l.l_linger = 10;
    l.l_onoff = 1;
    setsockopt(ListenSocket, SOL_SOCKET, SO_LINGER, (char *)&l, sizeof(l));

    // Bind the socket
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(port);

    result = bind(ListenSocket, (sockaddr *)&addr, sizeof(addr));
    if (result == SOCKET_ERROR)
        ExitOnError("Bind failed", TRUE);

    // Start listening for incoming connections
    result = listen(ListenSocket, SOMAXCONN);
    if (result == SOCKET_ERROR)
        ExitOnError("Listen failed", TRUE);

    return ListenSocket;
}

int main(int argc, char **argv)
{
    WSADATA wsaData;
    SOCKET ListenSocket = INVALID_SOCKET, ClientSocket = INVALID_SOCKET;
    struct addrinfo *result = NULL, hints;
    char *sendbuf = "done";
    int iResult, iSendResult;

    // Validate the parameters
    if (argc != 1) {
        ExitOnError("Finish.exe takes no parameters", FALSE);
    }

    // Initialize Winsock
    iResult = WSAStartup(MAKEWORD(2,2), &wsaData);
    if (iResult != 0) {
        ExitOnError("WSAStartup failed", FALSE);
    }

    // Resolve the server address and port
    ListenSocket = PrepareListenSocket(DEFAULT_PORT);

    // Accept a client socket
    ClientSocket = accept(ListenSocket, NULL, NULL);
    if (ClientSocket == INVALID_SOCKET) {
        closesocket(ListenSocket);
        ExitOnError("Accept failed", TRUE);
    }

    // No longer need the server socket
    closesocket(ListenSocket);

    // Send the ack string to the client
    iSendResult = send(ClientSocket, sendbuf, strlen(sendbuf), 0);
    if (iSendResult == SOCKET_ERROR) {
        closesocket(ClientSocket);
        ExitOnError("Send failed", TRUE);
    }
    // Report the number of bytes sent
    printf("Bytes sent: %d\n", iSendResult);

    // Shutdown the connection since we're done
    iResult = shutdown(ClientSocket, SD_SEND);
    if (iResult == SOCKET_ERROR) {
        closesocket(ClientSocket);
        ExitOnError("Shutdown failed", TRUE);
    }

    // Cleanup
    closesocket(ClientSocket);
    WSACleanup();

    return 0;
}
