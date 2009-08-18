// Simple remote shell server
// Author: Michael Goldish <mgoldish@redhat.com>
// Much of the code here was adapted from Microsoft code samples.

// Usage: rss.exe [port]
// If no port is specified the default is 22.

#define _WIN32_WINNT 0x0500

#include <windows.h>
#include <winsock2.h>
#include <stdio.h>

#pragma comment(lib, "ws2_32.lib")

int port = 22;

HWND hMainWindow = NULL;
HWND hTextBox = NULL;

struct client_info {
    SOCKET socket;
    sockaddr_in addr;
    int pid;
    HANDLE hJob;
    HANDLE hChildOutputRead;
    HANDLE hChildInputWrite;
    HANDLE hThreadChildToSocket;
};

void ExitOnError(char *message, BOOL winsock = 0)
{
    LPVOID system_message;
    char buffer[512];

    int error_code;
    if (winsock)
        error_code = WSAGetLastError();
    else
        error_code = GetLastError();

    WSACleanup();

    FormatMessage(
        FORMAT_MESSAGE_ALLOCATE_BUFFER|FORMAT_MESSAGE_FROM_SYSTEM,
        NULL, error_code, MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        (LPTSTR)&system_message, 0, NULL);

    sprintf(buffer,
            "%s!\n"
            "Error code = %d\n"
            "Error message = %s",
            message, error_code, (char *)system_message);

    MessageBox(hMainWindow, buffer, "Error", MB_OK | MB_ICONERROR);

    LocalFree(system_message);
    ExitProcess(1);
}

void AppendMessage(char *message)
{
    int length = GetWindowTextLength(hTextBox);
    SendMessage(hTextBox, EM_SETSEL, (WPARAM)length, (LPARAM)length);
    SendMessage(hTextBox, EM_REPLACESEL, (WPARAM)FALSE, (LPARAM)message);
}

void FormatStringForPrinting(char *dst, char *src, int size)
{
    int j = 0;

    for (int i = 0; i < size && src[i]; i++) {
        if (src[i] == '\n') {
            dst[j++] = '\\';
            dst[j++] = 'n';
        } else if (src[i] == '\r') {
            dst[j++] = '\\';
            dst[j++] = 'r';
        } else if (src[i] == '\t') {
            dst[j++] = '\\';
            dst[j++] = 't';
        } else if (src[i] == '\\') {
            dst[j++] = '\\';
            dst[j++] = '\\';
        } else dst[j++] = src[i];
    }
    dst[j] = 0;
}

char* GetClientIPAddress(client_info *ci)
{
    char *address = inet_ntoa(ci->addr.sin_addr);
    if (address)
        return address;
    else
        return "unknown";
}

DWORD WINAPI ChildToSocket(LPVOID client_info_ptr)
{
    char buffer[1024], message[1024];
    client_info ci;
    DWORD bytes_read;
    int bytes_sent;

    memcpy(&ci, client_info_ptr, sizeof(ci));

    while (1) {
        // Read data from the child's STDOUT/STDERR pipes
        if (!ReadFile(ci.hChildOutputRead,
                      buffer, sizeof(buffer),
                      &bytes_read, NULL) || !bytes_read) {
            if (GetLastError() == ERROR_BROKEN_PIPE)
                break; // Pipe done -- normal exit path
            else
                ExitOnError("ReadFile failed"); // Something bad happened
        }
        // Send data to the client
        bytes_sent = send(ci.socket, buffer, bytes_read, 0);
        /*
        // Make sure all the data was sent
        if (bytes_sent != bytes_read) {
            sprintf(message,
                    "ChildToSocket: bytes read (%d) != bytes sent (%d)",
                    bytes_read, bytes_sent);
            ExitOnError(message, 1);
        }
        */
    }

    AppendMessage("Child exited\r\n");
    shutdown(ci.socket, SD_BOTH);

    return 0;
}

DWORD WINAPI SocketToChild(LPVOID client_info_ptr)
{
    char buffer[256], formatted_buffer[768];
    char message[1024], client_info_str[256];
    client_info ci;
    DWORD bytes_written;
    int bytes_received;

    memcpy(&ci, client_info_ptr, sizeof(ci));

    sprintf(client_info_str, "address %s, port %d",
            GetClientIPAddress(&ci), ci.addr.sin_port);

    sprintf(message, "New client connected (%s)\r\n", client_info_str);
    AppendMessage(message);

    while (1) {
        // Receive data from the socket
        ZeroMemory(buffer, sizeof(buffer));
        bytes_received = recv(ci.socket, buffer, sizeof(buffer), 0);
        if (bytes_received <= 0)
            break;
        // Report the data received
        FormatStringForPrinting(formatted_buffer, buffer, sizeof(buffer));
        sprintf(message, "Client (%s) entered text: \"%s\"\r\n",
                client_info_str, formatted_buffer);
        AppendMessage(message);
        // Write the data to the child's STDIN
        WriteFile(ci.hChildInputWrite, buffer, bytes_received,
                  &bytes_written, NULL);
        // Make sure all the data was written
        if (bytes_written != bytes_received) {
            sprintf(message,
                    "SocketToChild: bytes received (%d) != bytes written (%d)",
                    bytes_received, bytes_written);
            ExitOnError(message, 1);
        }
    }

    sprintf(message, "Client disconnected (%s)\r\n", client_info_str);
    AppendMessage(message);

    // Attempt to terminate the child's process tree:
    // Using taskkill (where available)
    sprintf(buffer, "taskkill /PID %d /T /F", ci.pid);
    system(buffer);
    // .. and using TerminateJobObject()
    TerminateJobObject(ci.hJob, 0);
    // Wait for the ChildToSocket thread to terminate
    WaitForSingleObject(ci.hThreadChildToSocket, 10000);
    // In case the thread refuses to exit -- terminate it
    TerminateThread(ci.hThreadChildToSocket, 0);
    // Close the socket
    shutdown(ci.socket, SD_BOTH);
    closesocket(ci.socket);

    // Close unnecessary handles
    CloseHandle(ci.hJob);
    CloseHandle(ci.hThreadChildToSocket);
    CloseHandle(ci.hChildOutputRead);
    CloseHandle(ci.hChildInputWrite);

    AppendMessage("SocketToChild thread exited\r\n");

    return 0;
}

void PrepAndLaunchRedirectedChild(client_info *ci,
                                  HANDLE hChildStdOut,
                                  HANDLE hChildStdIn,
                                  HANDLE hChildStdErr)
{
    PROCESS_INFORMATION pi;
    STARTUPINFO si;

    // Set up the start up info struct.
    ZeroMemory(&si, sizeof(STARTUPINFO));
    si.cb = sizeof(STARTUPINFO);
    si.dwFlags = STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW;
    si.hStdOutput = hChildStdOut;
    si.hStdInput  = hChildStdIn;
    si.hStdError  = hChildStdErr;
    // Use this if you want to hide the child:
    si.wShowWindow = SW_HIDE;
    // Note that dwFlags must include STARTF_USESHOWWINDOW if you want to
    // use the wShowWindow flags.

    // Launch the process that you want to redirect.
    if (!CreateProcess(NULL, "cmd.exe", NULL, NULL, TRUE,
                       CREATE_NEW_CONSOLE, NULL, "C:\\", &si, &pi))
        ExitOnError("CreateProcess failed");

    // Close any unnecessary handles.
    if (!CloseHandle(pi.hThread))
        ExitOnError("CloseHandle failed");

    // Keep the process ID
    ci->pid = pi.dwProcessId;
    // Assign the process to a newly created JobObject
    ci->hJob = CreateJobObject(NULL, NULL);
    AssignProcessToJobObject(ci->hJob, pi.hProcess);
}

void SpawnSession(client_info *ci)
{
    HANDLE hOutputReadTmp, hOutputRead, hOutputWrite;
    HANDLE hInputWriteTmp, hInputRead, hInputWrite;
    HANDLE hErrorWrite;
    SECURITY_ATTRIBUTES sa;

    // Set up the security attributes struct.
    sa.nLength = sizeof(SECURITY_ATTRIBUTES);
    sa.lpSecurityDescriptor = NULL;
    sa.bInheritHandle = TRUE;

    // Create the child output pipe.
    if (!CreatePipe(&hOutputReadTmp, &hOutputWrite, &sa, 0))
        ExitOnError("CreatePipe failed");

    // Create a duplicate of the output write handle for the std error
    // write handle. This is necessary in case the child application
    // closes one of its std output handles.
    if (!DuplicateHandle(GetCurrentProcess(), hOutputWrite,
                         GetCurrentProcess(), &hErrorWrite, 0,
                         TRUE, DUPLICATE_SAME_ACCESS))
        ExitOnError("DuplicateHandle failed");

    // Create the child input pipe.
    if (!CreatePipe(&hInputRead, &hInputWriteTmp, &sa, 0))
        ExitOnError("CreatePipe failed");

    // Create new output read handle and the input write handles. Set
    // the Properties to FALSE. Otherwise, the child inherits the
    // properties and, as a result, non-closeable handles to the pipes
    // are created.
    if (!DuplicateHandle(GetCurrentProcess(), hOutputReadTmp,
                         GetCurrentProcess(),
                         &hOutputRead, // Address of new handle.
                         0, FALSE, // Make it uninheritable.
                         DUPLICATE_SAME_ACCESS))
        ExitOnError("DuplicateHandle failed");

    if (!DuplicateHandle(GetCurrentProcess(), hInputWriteTmp,
                         GetCurrentProcess(),
                         &hInputWrite, // Address of new handle.
                         0, FALSE, // Make it uninheritable.
                         DUPLICATE_SAME_ACCESS))
        ExitOnError("DuplicateHandle failed");

    // Close inheritable copies of the handles you do not want to be
    // inherited.
    if (!CloseHandle(hOutputReadTmp)) ExitOnError("CloseHandle failed");
    if (!CloseHandle(hInputWriteTmp)) ExitOnError("CloseHandle failed");

    PrepAndLaunchRedirectedChild(ci, hOutputWrite, hInputRead, hErrorWrite);

    ci->hChildOutputRead = hOutputRead;
    ci->hChildInputWrite = hInputWrite;

    // Close pipe handles (do not continue to modify the parent).
    // You need to make sure that no handles to the write end of the
    // output pipe are maintained in this process or else the pipe will
    // not close when the child process exits and the ReadFile will hang.
    if (!CloseHandle(hOutputWrite)) ExitOnError("CloseHandle failed");
    if (!CloseHandle(hInputRead )) ExitOnError("CloseHandle failed");
    if (!CloseHandle(hErrorWrite)) ExitOnError("CloseHandle failed");
}

DWORD WINAPI ListenThread(LPVOID param)
{
    WSADATA wsaData;
    SOCKET ListenSocket = INVALID_SOCKET;
    sockaddr_in addr;
    int result, addrlen;
    client_info ci;
    HANDLE hThread;

    // Initialize Winsock
    result = WSAStartup(MAKEWORD(2,2), &wsaData);
    if (result)
        ExitOnError("Winsock initialization failed");

    // Create socket
    ListenSocket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (ListenSocket == INVALID_SOCKET)
        ExitOnError("Socket creation failed", 1);

    // Bind the socket
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(port);

    result = bind(ListenSocket, (sockaddr *)&addr, sizeof(addr));
    if (result == SOCKET_ERROR)
        ExitOnError("bind failed", 1);

    // Start listening for incoming connections
    result = listen(ListenSocket, SOMAXCONN);
    if (result == SOCKET_ERROR)
        ExitOnError("listen failed", 1);

    // Inform the user
    AppendMessage("Waiting for clients to connect...\r\n");

    while (1) {
        addrlen = sizeof(ci.addr);
        ci.socket = accept(ListenSocket, (sockaddr *)&ci.addr, &addrlen);
        if (ci.socket == INVALID_SOCKET) {
            if (WSAGetLastError() == WSAEINTR)
                break;
            else
                ExitOnError("accept failed", 1);
        }

        // Under heavy load, spawning cmd.exe might take a while, so tell the
        // client to be patient
        char *message = "Please wait...\r\n";
        send(ci.socket, message, strlen(message), 0);
        // Spawn a new redirected cmd.exe process
        SpawnSession(&ci);
        // Start transferring data from the child process to the client
        hThread = CreateThread(NULL, 0, ChildToSocket, (LPVOID)&ci, 0, NULL);
        if (!hThread)
            ExitOnError("Could not create ChildToSocket thread");
        ci.hThreadChildToSocket = hThread;
        // ... and from the client to the child process
        hThread = CreateThread(NULL, 0, SocketToChild, (LPVOID)&ci, 0, NULL);
        if (!hThread)
            ExitOnError("Could not create SocketToChild thread");
    }

    return 0;
}

LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    RECT rect;
    HANDLE hListenThread;

    switch (msg) {
        case WM_CREATE:
            // Create text box
            GetClientRect(hwnd, &rect);
            hTextBox = CreateWindowEx(WS_EX_CLIENTEDGE,
                                      "EDIT", "",
                                      WS_CHILD|WS_VISIBLE|WS_VSCROLL|
                                      ES_MULTILINE|ES_AUTOVSCROLL,
                                      20, 20,
                                      rect.right - 40,
                                      rect.bottom - 40,
                                      hwnd,
                                      NULL,
                                      GetModuleHandle(NULL),
                                      NULL);
            if (!hTextBox)
                ExitOnError("Could not create text box");

            // Set the font
            SendMessage(hTextBox, WM_SETFONT,
                        (WPARAM)GetStockObject(DEFAULT_GUI_FONT),
                        MAKELPARAM(FALSE, 0));

            // Start the listening thread
            hListenThread =
                CreateThread(NULL, 0, ListenThread, NULL, 0, NULL);
            if (!hListenThread)
                ExitOnError("Could not create server thread");
            break;

        case WM_DESTROY:
            WSACleanup();
            PostQuitMessage(0);
            break;

        default:
            return DefWindowProc(hwnd, msg, wParam, lParam);
    }

    return 0;
}

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance,
                   LPSTR lpCmdLine, int nShowCmd)
{
    WNDCLASSEX wc;
    MSG msg;

    if (strlen(lpCmdLine))
        sscanf(lpCmdLine, "%d", &port);

    // Make sure the firewall is disabled
    system("netsh firewall set opmode disable");

    // Create the window class
    wc.cbSize        = sizeof(WNDCLASSEX);
    wc.style         = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc   = WndProc;
    wc.cbClsExtra    = 0;
    wc.cbWndExtra    = 0;
    wc.hInstance     = hInstance;
    wc.hIcon         = LoadIcon(NULL, IDI_APPLICATION);
    wc.hIconSm       = LoadIcon(NULL, IDI_APPLICATION);
    wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wc.lpszMenuName  = NULL;
    wc.lpszClassName = "RemoteShellServerWindowClass";
    wc.hCursor       = LoadCursor(NULL, IDC_ARROW);

    if (!RegisterClassEx(&wc))
        ExitOnError("Could not register window class");

    // Create the main window
    hMainWindow =
        CreateWindow("RemoteShellServerWindowClass",
                     "Remote Shell Server",
                     WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,
                     20, 20, 500, 300,
                     NULL, NULL, hInstance, NULL);
    if (!hMainWindow)
        ExitOnError("Could not create window");

    ShowWindow(hMainWindow, SW_SHOWMINNOACTIVE);
    UpdateWindow(hMainWindow);

    // Main message loop
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    ExitProcess(0);
}
