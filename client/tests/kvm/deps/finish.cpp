// Simple application that creates a server socket, listening for connections
// of the unattended install test. Once it gets a client connected, the
// app will send back an ACK string, indicating the install process is done.
//
// You must link this code with Ws2_32.lib, Mswsock.lib, and Advapi32.lib
//
// Author: Lucas Meneghel Rodrigues <lmr@redhat.com>
// Code was adapted from an MSDN sample.

// Usage: finish.exe

// MinGW's ws2tcpip.h only defines getaddrinfo and other functions only for
// the case _WIN32_WINNT >= 0x0501.
#ifdef __MINGW32__
#undef _WIN32_WINNT
#define _WIN32_WINNT 0x501
#endif

#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <stdlib.h>
#include <stdio.h>

#define DEFAULT_PORT "12323"
int main(int argc, char **argv)
{
    WSADATA wsaData;
    SOCKET ListenSocket = INVALID_SOCKET, ClientSocket = INVALID_SOCKET;
    struct addrinfo *result = NULL, hints;
    char *sendbuf = "done";
    int iResult, iSendResult;

    // Validate the parameters
    if (argc != 1) {
        printf("usage: %s", argv[0]);
        return 1;
    }

    // Initialize Winsock
    iResult = WSAStartup(MAKEWORD(2,2), &wsaData);
    if (iResult != 0) {
        printf("WSAStartup failed: %d\n", iResult);
        return 1;
    }

    ZeroMemory(&hints, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_protocol = IPPROTO_TCP;
    hints.ai_flags = AI_PASSIVE;

    // Resolve the server address and port
    iResult = getaddrinfo(NULL, DEFAULT_PORT, &hints, &result);
    if (iResult != 0) {
        printf("getaddrinfo failed: %d\n", iResult);
        WSACleanup();
        return 1;
    }

    // Create a SOCKET for connecting to server
    ListenSocket = socket(result->ai_family, result->ai_socktype,
                          result->ai_protocol);
    if (ListenSocket == INVALID_SOCKET) {
        printf("socket failed: %ld\n", WSAGetLastError());
        freeaddrinfo(result);
        WSACleanup();
        return 1;
    }

    // Setup the TCP listening socket
    iResult = bind(ListenSocket, result->ai_addr, (int)result->ai_addrlen);
    if (iResult == SOCKET_ERROR) {
        printf("bind failed: %d\n", WSAGetLastError());
        freeaddrinfo(result);
        closesocket(ListenSocket);
        WSACleanup();
        return 1;
    }

    freeaddrinfo(result);

    iResult = listen(ListenSocket, SOMAXCONN);
    if (iResult == SOCKET_ERROR) {
        printf("listen failed: %d\n", WSAGetLastError());
        closesocket(ListenSocket);
        WSACleanup();
        return 1;
    }

    // Accept a client socket
    ClientSocket = accept(ListenSocket, NULL, NULL);
    if (ClientSocket == INVALID_SOCKET) {
        printf("accept failed: %d\n", WSAGetLastError());
        closesocket(ListenSocket);
        WSACleanup();
        return 1;
    }

    // No longer need the server socket
    closesocket(ListenSocket);

    // Send the ack string to the client
    iSendResult = send(ClientSocket, sendbuf, sizeof(sendbuf), 0);
    if (iSendResult == SOCKET_ERROR) {
        printf("send failed: %d\n", WSAGetLastError());
        closesocket(ClientSocket);
        WSACleanup();
        return 1;
    }
    // Report the number of bytes sent
    printf("Bytes sent: %d\n", iSendResult);

    // Shutdown the connection since we're done
    iResult = shutdown(ClientSocket, SD_SEND);
    if (iResult == SOCKET_ERROR) {
        printf("shutdown failed: %d\n", WSAGetLastError());
        closesocket(ClientSocket);
        WSACleanup();
        return 1;
    }

    // Cleanup
    closesocket(ClientSocket);
    WSACleanup();

    return 0;
}
