// Simple remote shell server (and file transfer server)
// Author: Michael Goldish <mgoldish@redhat.com>
// Much of the code here was adapted from Microsoft code samples.

// Usage: rss.exe [shell port] [file transfer port]
// If no shell port is specified the default is 10022.
// If no file transfer port is specified the default is 10023.

// Definitions:
// A 'msg' is a 32 bit integer.
// A 'packet' is a 32 bit unsigned integer followed by a string of bytes.
// The 32 bit integer indicates the length of the string.

// Protocol for file transfers:
//
// When uploading files/directories to the server:
// 1. The client connects.
// 2. The server sends RSS_MAGIC.
// 3. The client sends the chunk size for file transfers (a 32 bit integer
//    between 512 and 1048576 indicating the size in bytes).
// 4. The client sends RSS_SET_PATH, followed by a packet (as defined above)
//    containing the path (in the server's filesystem) where files and/or
//    directories are to be stored.
// Uploading a file (optional, can be repeated many times):
//   5. The client sends RSS_CREATE_FILE, followed by a packet containing the
//      filename (filename only, without a path), followed by a series of
//      packets (called chunks) containing the file's contents.  The size of
//      each chunk is the size set by the client in step 3, except for the
//      last chunk, which must be smaller.
// Uploading a directory (optional, can be repeated many times):
//   6. The client sends RSS_CREATE_DIR, followed by a packet containing the
//      name of the directory to be created (directory name only, without a
//      path).
//   7. The client uploads files and directories to the new directory (using
//      steps 5, 6, 8).
//   8. The client sends RSS_LEAVE_DIR.
// 9. The client sends RSS_DONE and waits for a response.
// 10. The server sends RSS_OK to indicate that it's still listening.
// 11. Steps 4-10 are repeated as many times as necessary.
// 12. The client disconnects.
// If a critical error occurs at any time, the server may send RSS_ERROR
// followed by a packet containing an error message, and the connection is
// closed.
//
// When downloading files from the server:
// 1. The client connects.
// 2. The server sends RSS_MAGIC.
// 3. The client sends the chunk size for file transfers (a 32 bit integer
//    between 512 and 1048576 indicating the size in bytes).
// 4. The client sends RSS_SET_PATH, followed by a packet (as defined above)
//    containing a path (in the server's filesystem) or a wildcard pattern
//    indicating the files/directories the client wants to download.
// The server then searches the given path.  For every file found:
//   5. The server sends RSS_CREATE_FILE, followed by a packet containing the
//      filename (filename only, without a path), followed by a series of
//      packets (called chunks) containing the file's contents.  The size of
//      each chunk is the size set by the client in step 3, except for the
//      last chunk, which must be smaller.
// For every directory found:
//   6. The server sends RSS_CREATE_DIR, followed by a packet containing the
//      name of the directory to be created (directory name only, without a
//      path).
//   7. The server sends files and directories located inside the directory
//      (using steps 5, 6, 8).
//   8. The server sends RSS_LEAVE_DIR.
// 9. The server sends RSS_DONE.
// 10. Steps 4-9 are repeated as many times as necessary.
// 11. The client disconnects.
// If a critical error occurs, the server may send RSS_ERROR followed by a
// packet containing an error message, and the connection is closed.
// RSS_ERROR may be sent only when the client expects a msg.

#define _WIN32_WINNT 0x0500

#include <winsock2.h>
#include <windows.h>
#include <stdio.h>
#include <stdarg.h>
#include <shlwapi.h>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "shlwapi.lib")

#define TEXTBOX_LIMIT 262144

// Constants for file transfer server
#define RSS_MAGIC           0x525353
#define RSS_OK              1
#define RSS_ERROR           2
#define RSS_UPLOAD          3
#define RSS_DOWNLOAD        4
#define RSS_SET_PATH        5
#define RSS_CREATE_FILE     6
#define RSS_CREATE_DIR      7
#define RSS_LEAVE_DIR       8
#define RSS_DONE            9

// Globals
int shell_port = 10022;
int file_transfer_port = 10023;

HWND hMainWindow = NULL;
HWND hTextBox = NULL;

char text_buffer[8192] = {0};
int text_size = 0;

CRITICAL_SECTION critical_section;

FILE *log_file;

struct client_info {
    SOCKET socket;
    char addr_str[256];
    int pid;
    HWND hwnd;
    HANDLE hJob;
    HANDLE hChildOutputRead;
    HANDLE hThreadChildToSocket;
    char *chunk_buffer;
    int chunk_size;
};

/*-----------------
 * Shared functions
 *-----------------*/

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
    MessageBox(hMainWindow, buffer, "Error", MB_OK | MB_ICONERROR);

    LocalFree(system_message);
    ExitProcess(1);
}

void FlushTextBuffer()
{
    if (!text_size) return;
    // Clear the text box if it contains too much text
    int len = GetWindowTextLength(hTextBox);
    while (len > TEXTBOX_LIMIT - sizeof(text_buffer)) {
        SendMessage(hTextBox, EM_SETSEL, 0, TEXTBOX_LIMIT * 1/4);
        SendMessage(hTextBox, EM_REPLACESEL, FALSE, (LPARAM)"...");
        len = GetWindowTextLength(hTextBox);
    }
    // Append the contents of text_buffer to the text box
    SendMessage(hTextBox, EM_SETSEL, len, len);
    SendMessage(hTextBox, EM_REPLACESEL, FALSE, (LPARAM)text_buffer);
    // Clear text_buffer
    text_buffer[0] = 0;
    text_size = 0;
    // Make sure the log file's buffer is flushed as well
    if (log_file)
        fflush(log_file);
}

void AppendMessage(const char *message, ...)
{
    va_list args;
    char str[512] = {0};

    va_start(args, message);
    vsnprintf(str, sizeof(str) - 3, message, args);
    va_end(args);
    strcat(str, "\r\n");
    int len = strlen(str);

    EnterCriticalSection(&critical_section);
    // Write message to the log file
    if (log_file)
        fwrite(str, len, 1, log_file);
    // Flush the text buffer if necessary
    if (text_size + len + 1 > sizeof(text_buffer))
        FlushTextBuffer();
    // Append message to the text buffer
    strcpy(text_buffer + text_size, str);
    text_size += len;
    LeaveCriticalSection(&critical_section);
}

// Flush the text buffer every 250 ms
DWORD WINAPI UpdateTextBox(LPVOID client_info_ptr)
{
    while (1) {
        Sleep(250);
        EnterCriticalSection(&critical_section);
        FlushTextBuffer();
        LeaveCriticalSection(&critical_section);
    }
    return 0;
}

void FormatStringForPrinting(char *dst, const char *src, int size)
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
        ExitOnError("bind failed", TRUE);

    // Start listening for incoming connections
    result = listen(ListenSocket, SOMAXCONN);
    if (result == SOCKET_ERROR)
        ExitOnError("listen failed", TRUE);

    return ListenSocket;
}

client_info* Accept(SOCKET ListenSocket)
{
    sockaddr_in addr;
    int addrlen = sizeof(addr);

    // Accept the connection
    SOCKET socket = accept(ListenSocket, (sockaddr *)&addr, &addrlen);
    if (socket == INVALID_SOCKET) {
        if (WSAGetLastError() == WSAEINTR)
            return NULL;
        else
            ExitOnError("accept failed", TRUE);
    }

    // Allocate a new client_info struct
    client_info *ci = (client_info *)calloc(1, sizeof(client_info));
    if (!ci)
        ExitOnError("Could not allocate client_info struct");
    // Populate the new struct
    ci->socket = socket;
    const char *address = inet_ntoa(addr.sin_addr);
    if (!address) address = "unknown";
    sprintf(ci->addr_str, "%s:%d", address, addr.sin_port);

    return ci;
}

// Read a given number of bytes into a buffer
BOOL Receive(SOCKET socket, char *buffer, int len)
{
    while (len > 0) {
        int bytes_received = recv(socket, buffer, len, 0);
        if (bytes_received <= 0)
            return FALSE;
        buffer += bytes_received;
        len -= bytes_received;
    }
    return TRUE;
}

// Send a given number of bytes from a buffer
BOOL Send(SOCKET socket, const char *buffer, int len)
{
    while (len > 0) {
        int bytes_sent = send(socket, buffer, len, 0);
        if (bytes_sent <= 0)
            return FALSE;
        buffer += bytes_sent;
        len -= bytes_sent;
    }
    return TRUE;
}

/*-------------
 * Shell server
 *-------------*/

DWORD WINAPI ChildToSocket(LPVOID client_info_ptr)
{
    client_info *ci = (client_info *)client_info_ptr;
    char buffer[1024];
    DWORD bytes_read;

    while (1) {
        // Read data from the child's STDOUT/STDERR pipes
        if (!ReadFile(ci->hChildOutputRead,
                      buffer, sizeof(buffer),
                      &bytes_read, NULL) || !bytes_read) {
            if (GetLastError() == ERROR_BROKEN_PIPE)
                break; // Pipe done -- normal exit path
            else
                ExitOnError("ReadFile failed"); // Something bad happened
        }
        // Send data to the client
        Send(ci->socket, buffer, bytes_read);
    }

    AppendMessage("Child exited");
    closesocket(ci->socket);
    return 0;
}

DWORD WINAPI SocketToChild(LPVOID client_info_ptr)
{
    client_info *ci = (client_info *)client_info_ptr;
    char buffer[256], formatted_buffer[768];
    int bytes_received;

    AppendMessage("Shell server: new client connected (%s)", ci->addr_str);

    while (1) {
        // Receive data from the socket
        ZeroMemory(buffer, sizeof(buffer));
        bytes_received = recv(ci->socket, buffer, sizeof(buffer), 0);
        if (bytes_received <= 0)
            break;
        // Report the data received
        FormatStringForPrinting(formatted_buffer, buffer, sizeof(buffer));
        AppendMessage("Client (%s) entered text: \"%s\"",
                      ci->addr_str, formatted_buffer);
        // Send the data as a series of WM_CHAR messages to the console window
        for (int i = 0; i < bytes_received; i++) {
            SendMessage(ci->hwnd, WM_CHAR, buffer[i], 0);
            SendMessage(ci->hwnd, WM_SETFOCUS, 0, 0);
        }
    }

    AppendMessage("Shell server: client disconnected (%s)", ci->addr_str);

    // Attempt to terminate the child's process tree:
    // Using taskkill (where available)
    sprintf(buffer, "taskkill /PID %d /T /F", ci->pid);
    system(buffer);
    // .. and using TerminateJobObject()
    TerminateJobObject(ci->hJob, 0);
    // Wait for the ChildToSocket thread to terminate
    WaitForSingleObject(ci->hThreadChildToSocket, 10000);
    // In case the thread refuses to exit, terminate it
    TerminateThread(ci->hThreadChildToSocket, 0);
    // Close the socket
    closesocket(ci->socket);

    // Free resources
    CloseHandle(ci->hJob);
    CloseHandle(ci->hThreadChildToSocket);
    CloseHandle(ci->hChildOutputRead);
    free(ci);

    AppendMessage("SocketToChild thread exited");
    return 0;
}

void PrepAndLaunchRedirectedChild(client_info *ci,
                                  HANDLE hChildStdOut,
                                  HANDLE hChildStdErr)
{
    PROCESS_INFORMATION pi;
    STARTUPINFO si;

    // Allocate a new console for the child
    HWND hwnd = GetForegroundWindow();
    FreeConsole();
    AllocConsole();
    ShowWindow(GetConsoleWindow(), SW_HIDE);
    if (hwnd)
        SetForegroundWindow(hwnd);

    // Set up the start up info struct.
    ZeroMemory(&si, sizeof(STARTUPINFO));
    si.cb = sizeof(STARTUPINFO);
    si.dwFlags = STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW;
    si.hStdOutput = hChildStdOut;
    si.hStdInput  = GetStdHandle(STD_INPUT_HANDLE);
    si.hStdError  = hChildStdErr;
    // Use this if you want to hide the child:
    si.wShowWindow = SW_HIDE;
    // Note that dwFlags must include STARTF_USESHOWWINDOW if you want to
    // use the wShowWindow flags.

    // Launch the process that you want to redirect.
    if (!CreateProcess(NULL, "cmd.exe", NULL, NULL, TRUE,
                       0, NULL, "C:\\", &si, &pi))
        ExitOnError("CreateProcess failed");

    // Close any unnecessary handles.
    if (!CloseHandle(pi.hThread))
        ExitOnError("CloseHandle failed");

    // Keep the process ID
    ci->pid = pi.dwProcessId;
    // Assign the process to a newly created JobObject
    ci->hJob = CreateJobObject(NULL, NULL);
    AssignProcessToJobObject(ci->hJob, pi.hProcess);
    // Keep the console window's handle
    ci->hwnd = GetConsoleWindow();

    // Detach from the child's console
    FreeConsole();
}

void SpawnSession(client_info *ci)
{
    HANDLE hOutputReadTmp, hOutputRead, hOutputWrite;
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

    // Close inheritable copies of the handles you do not want to be
    // inherited.
    if (!CloseHandle(hOutputReadTmp))
        ExitOnError("CloseHandle failed");

    PrepAndLaunchRedirectedChild(ci, hOutputWrite, hErrorWrite);

    ci->hChildOutputRead = hOutputRead;

    // Close pipe handles (do not continue to modify the parent).
    // You need to make sure that no handles to the write end of the
    // output pipe are maintained in this process or else the pipe will
    // not close when the child process exits and the ReadFile will hang.
    if (!CloseHandle(hOutputWrite)) ExitOnError("CloseHandle failed");
    if (!CloseHandle(hErrorWrite)) ExitOnError("CloseHandle failed");
}

DWORD WINAPI ShellListenThread(LPVOID param)
{
    HANDLE hThread;

    SOCKET ListenSocket = PrepareListenSocket(shell_port);

    // Inform the user
    AppendMessage("Shell server: waiting for clients to connect...");

    while (1) {
        client_info *ci = Accept(ListenSocket);
        if (!ci) break;
        // Under heavy load, spawning cmd.exe might take a while, so tell the
        // client to be patient
        const char *message = "Please wait...\r\n";
        Send(ci->socket, message, strlen(message));
        // Spawn a new redirected cmd.exe process
        SpawnSession(ci);
        // Start transferring data from the child process to the client
        hThread = CreateThread(NULL, 0, ChildToSocket, (LPVOID)ci, 0, NULL);
        if (!hThread)
            ExitOnError("Could not create ChildToSocket thread");
        ci->hThreadChildToSocket = hThread;
        // ... and from the client to the child process
        hThread = CreateThread(NULL, 0, SocketToChild, (LPVOID)ci, 0, NULL);
        if (!hThread)
            ExitOnError("Could not create SocketToChild thread");
    }

    return 0;
}

/*---------------------
 * File transfer server
 *---------------------*/

int ReceivePacket(SOCKET socket, char *buffer, DWORD max_size)
{
    DWORD packet_size = 0;

    if (!Receive(socket, (char *)&packet_size, 4))
        return -1;
    if (packet_size > max_size)
        return -1;
    if (!Receive(socket, buffer, packet_size))
        return -1;

    return packet_size;
}

int ReceiveStrPacket(SOCKET socket, char *buffer, DWORD max_size)
{
    memset(buffer, 0, max_size);
    return ReceivePacket(socket, buffer, max_size - 1);
}

BOOL SendPacket(SOCKET socket, const char *buffer, DWORD len)
{
    if (!Send(socket, (char *)&len, 4))
        return FALSE;
    return Send(socket, buffer, len);
}

BOOL SendMsg(SOCKET socket, DWORD msg)
{
    return Send(socket, (char *)&msg, 4);
}

// Send data from a file
BOOL SendFileChunks(client_info *ci, const char *filename)
{
    FILE *fp = fopen(filename, "rb");
    if (!fp) return FALSE;

    while (1) {
        int bytes_read = fread(ci->chunk_buffer, 1, ci->chunk_size, fp);
        if (!SendPacket(ci->socket, ci->chunk_buffer, bytes_read))
            break;
        if (bytes_read < ci->chunk_size) {
            if (ferror(fp))
                break;
            else {
                fclose(fp);
                return TRUE;
            }
        }
    }

    fclose(fp);
    return FALSE;
}

// Receive data into a file
BOOL ReceiveFileChunks(client_info *ci, const char *filename)
{
    FILE *fp = fopen(filename, "wb");
    if (!fp) return FALSE;

    while (1) {
        int bytes_received = ReceivePacket(ci->socket, ci->chunk_buffer,
                                           ci->chunk_size);
        if (bytes_received < 0)
            break;
        if (bytes_received > 0)
            if (fwrite(ci->chunk_buffer, bytes_received, 1, fp) < 1)
                break;
        if (bytes_received < ci->chunk_size) {
            fclose(fp);
            return TRUE;
        }
    }

    fclose(fp);
    return FALSE;
}

BOOL ExpandPath(char *path, int max_size)
{
    char temp[512];
    int result;

    PathRemoveBackslash(path);
    result = ExpandEnvironmentStrings(path, temp, sizeof(temp));
    if (result == 0 || result > sizeof(temp))
        return FALSE;
    strncpy(path, temp, max_size - 1);
    return TRUE;
}

int TerminateTransfer(client_info *ci, const char *message)
{
    AppendMessage(message);
    AppendMessage("File transfer server: client disconnected (%s)",
                  ci->addr_str);
    closesocket(ci->socket);
    free(ci->chunk_buffer);
    free(ci);
    return 0;
}

int TerminateWithError(client_info *ci, const char *message)
{
    SendMsg(ci->socket, RSS_ERROR);
    SendPacket(ci->socket, message, strlen(message));
    return TerminateTransfer(ci, message);
}

int ReceiveThread(client_info *ci)
{
    char path[512], filename[512];
    DWORD msg;

    AppendMessage("Client (%s) wants to upload files", ci->addr_str);

    while (1) {
        if (!Receive(ci->socket, (char *)&msg, 4))
            return TerminateTransfer(ci, "Could not receive further msgs");

        switch (msg) {
        case RSS_SET_PATH:
            if (ReceiveStrPacket(ci->socket, path, sizeof(path)) < 0)
                return TerminateWithError(ci,
                    "RSS_SET_PATH: could not receive path, or path too long");
            AppendMessage("Client (%s) set path to %s", ci->addr_str, path);
            if (!ExpandPath(path, sizeof(path)))
                return TerminateWithError(ci,
                    "RSS_SET_PATH: error expanding environment strings");
            break;

        case RSS_CREATE_FILE:
            if (ReceiveStrPacket(ci->socket, filename, sizeof(filename)) < 0)
                return TerminateWithError(ci,
                    "RSS_CREATE_FILE: could not receive filename");
            if (PathIsDirectory(path))
                PathAppend(path, filename);
            AppendMessage("Client (%s) is uploading %s", ci->addr_str, path);
            if (!ReceiveFileChunks(ci, path))
                return TerminateWithError(ci,
                    "RSS_CREATE_FILE: error receiving or writing file "
                    "contents");
            PathAppend(path, "..");
            break;

        case RSS_CREATE_DIR:
            if (ReceiveStrPacket(ci->socket, filename, sizeof(filename)) < 0)
                return TerminateWithError(ci,
                    "RSS_CREATE_DIR: could not receive dirname");
            if (PathIsDirectory(path))
                PathAppend(path, filename);
            AppendMessage("Entering dir %s", path);
            if (PathFileExists(path)) {
                if (!PathIsDirectory(path))
                    return TerminateWithError(ci,
                        "RSS_CREATE_DIR: path exists and is not a directory");
            } else {
                if (!CreateDirectory(path, NULL))
                    return TerminateWithError(ci,
                        "RSS_CREATE_DIR: could not create directory");
            }
            break;

        case RSS_LEAVE_DIR:
            PathAppend(path, "..");
            AppendMessage("Returning to dir %s", path);
            break;

        case RSS_DONE:
            if (!SendMsg(ci->socket, RSS_OK))
                return TerminateTransfer(ci,
                    "RSS_DONE: could not send OK msg");
            break;

        default:
            return TerminateWithError(ci, "Received unexpected msg");
        }
    }
}

// Given a path or a pattern with wildcards, send files or directory trees to
// the client
int SendFiles(client_info *ci, const char *pattern)
{
    char path[512];
    WIN32_FIND_DATA ffd;

    HANDLE hFind = FindFirstFile(pattern, &ffd);
    if (hFind == INVALID_HANDLE_VALUE) {
        // If a weird error occurred (like failure to list directory contents
        // due to insufficient permissions) print a warning and continue.
        if (GetLastError() != ERROR_FILE_NOT_FOUND)
            AppendMessage("WARNING: FindFirstFile failed on pattern %s",
                          pattern);
        return 1;
    }

    strncpy(path, pattern, sizeof(path) - 1);
    PathAppend(path, "..");

    do {
        if (ffd.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)
            continue;
        if (ffd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            // Directory
            if (!strcmp(ffd.cFileName, ".") || !strcmp(ffd.cFileName, ".."))
                continue;
            PathAppend(path, ffd.cFileName);
            AppendMessage("Entering dir %s", path);
            PathAppend(path, "*");
            if (!SendMsg(ci->socket, RSS_CREATE_DIR)) {
                FindClose(hFind);
                return TerminateTransfer(ci,
                    "Could not send RSS_CREATE_DIR msg");
            }
            if (!SendPacket(ci->socket, ffd.cFileName,
                            strlen(ffd.cFileName))) {
                FindClose(hFind);
                return TerminateTransfer(ci, "Could not send dirname");
            }
            if (!SendFiles(ci, path)) {
                FindClose(hFind);
                return 0;
            }
            if (!SendMsg(ci->socket, RSS_LEAVE_DIR)) {
                FindClose(hFind);
                return TerminateTransfer(ci,
                    "Could not send RSS_LEAVE_DIR msg");
            }
            PathAppend(path, "..");
            PathAppend(path, "..");
            AppendMessage("Returning to dir %s", path);
        } else {
            // File
            PathAppend(path, ffd.cFileName);
            AppendMessage("Client (%s) is downloading %s", ci->addr_str, path);
            // Make sure the file is readable
            FILE *fp = fopen(path, "rb");
            if (fp) fclose(fp);
            else {
                AppendMessage("WARNING: could not read file %s", path);
                PathAppend(path, "..");
                continue;
            }
            if (!SendMsg(ci->socket, RSS_CREATE_FILE)) {
                FindClose(hFind);
                return TerminateTransfer(ci,
                    "Could not send RSS_CREATE_FILE msg");
            }
            if (!SendPacket(ci->socket, ffd.cFileName,
                            strlen(ffd.cFileName))) {
                FindClose(hFind);
                return TerminateTransfer(ci, "Could not send filename");
            }
            if (!SendFileChunks(ci, path)) {
                FindClose(hFind);
                return TerminateTransfer(ci, "Could not send file contents");
            }
            PathAppend(path, "..");
        }
    } while (FindNextFile(hFind, &ffd));

    if (GetLastError() == ERROR_NO_MORE_FILES) {
        FindClose(hFind);
        return 1;
    } else {
        FindClose(hFind);
        return TerminateWithError(ci, "FindNextFile failed");
    }
}

int SendThread(client_info *ci)
{
    char pattern[512];
    DWORD msg;

    AppendMessage("Client (%s) wants to download files", ci->addr_str);

    while (1) {
        if (!Receive(ci->socket, (char *)&msg, 4))
            return TerminateTransfer(ci, "Could not receive further msgs");

        switch (msg) {
        case RSS_SET_PATH:
            if (ReceiveStrPacket(ci->socket, pattern, sizeof(pattern)) < 0)
                return TerminateWithError(ci,
                    "RSS_SET_PATH: could not receive path, or path too long");
            AppendMessage("Client (%s) asked for %s", ci->addr_str, pattern);
            if (!ExpandPath(pattern, sizeof(pattern)))
                return TerminateWithError(ci,
                    "RSS_SET_PATH: error expanding environment strings");
            if (!SendFiles(ci, pattern))
                return 0;
            if (!SendMsg(ci->socket, RSS_DONE))
                return TerminateTransfer(ci,
                    "RSS_SET_PATH: could not send RSS_DONE msg");
            break;

        default:
            return TerminateWithError(ci, "Received unexpected msg");
        }
    }
}

DWORD WINAPI TransferThreadEntry(LPVOID client_info_ptr)
{
    client_info *ci = (client_info *)client_info_ptr;
    DWORD msg;

    AppendMessage("File transfer server: new client connected (%s)",
                  ci->addr_str);

    if (!SendMsg(ci->socket, RSS_MAGIC))
        return TerminateTransfer(ci, "Could not send greeting message");
    if (!Receive(ci->socket, (char *)&ci->chunk_size, 4))
        return TerminateTransfer(ci, "Error receiving chunk size");
    AppendMessage("Client (%s) set chunk size to %d", ci->addr_str,
                  ci->chunk_size);
    if (ci->chunk_size > 1048576 || ci->chunk_size < 512)
        return TerminateWithError(ci, "Client set invalid chunk size");
    if (!(ci->chunk_buffer = (char *)malloc(ci->chunk_size)))
        return TerminateWithError(ci, "Memory allocation error");
    if (!Receive(ci->socket, (char *)&msg, 4))
        return TerminateTransfer(ci, "Error receiving msg");

    if (msg == RSS_UPLOAD)
        return ReceiveThread(ci);
    else if (msg == RSS_DOWNLOAD)
        return SendThread(ci);
    return TerminateWithError(ci, "Received unexpected msg");
}

DWORD WINAPI FileTransferListenThread(LPVOID param)
{
    SOCKET ListenSocket = PrepareListenSocket(file_transfer_port);

    // Inform the user
    AppendMessage("File transfer server: waiting for clients to connect...");

    while (1) {
        client_info *ci = Accept(ListenSocket);
        if (!ci) break;
        if (!CreateThread(NULL, 0, TransferThreadEntry, (LPVOID)ci, 0, NULL))
            ExitOnError("Could not create file transfer thread");
    }

    return 0;
}

/*--------------------
 * WndProc and WinMain
 *--------------------*/

LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    RECT rect;
    WSADATA wsaData;
    SYSTEMTIME lt;
    char log_filename[256];

    switch (msg) {
    case WM_CREATE:
        // Create text box
        GetClientRect(hwnd, &rect);
        hTextBox = CreateWindowEx(WS_EX_CLIENTEDGE,
                                  "EDIT", "",
                                  WS_CHILD | WS_VISIBLE | WS_VSCROLL |
                                  ES_MULTILINE | ES_AUTOVSCROLL,
                                  20, 20,
                                  rect.right - 40,
                                  rect.bottom - 40,
                                  hwnd,
                                  NULL,
                                  GetModuleHandle(NULL),
                                  NULL);
        if (!hTextBox)
            ExitOnError("Could not create text box");
        // Set font
        SendMessage(hTextBox, WM_SETFONT,
                    (WPARAM)GetStockObject(DEFAULT_GUI_FONT),
                    MAKELPARAM(FALSE, 0));
        // Set size limit
        SendMessage(hTextBox, EM_LIMITTEXT, TEXTBOX_LIMIT, 0);
        // Initialize critical section object for text buffer access
        InitializeCriticalSection(&critical_section);
        // Open log file
        GetLocalTime(&lt);
        sprintf(log_filename, "rss_%02d-%02d-%02d_%02d-%02d-%02d.log",
                lt.wYear, lt.wMonth, lt.wDay,
                lt.wHour, lt.wMinute, lt.wSecond);
        log_file = fopen(log_filename, "wb");
        // Create text box update thread
        if (!CreateThread(NULL, 0, UpdateTextBox, NULL, 0, NULL))
            ExitOnError("Could not create text box update thread");
        // Initialize Winsock
        if (WSAStartup(MAKEWORD(2, 2), &wsaData))
            ExitOnError("Winsock initialization failed");
        // Start the listening threads
        if (!CreateThread(NULL, 0, ShellListenThread, NULL, 0, NULL))
            ExitOnError("Could not create shell server listen thread");
        if (!CreateThread(NULL, 0, FileTransferListenThread, NULL, 0, NULL))
            ExitOnError("Could not create file transfer server listen thread");
        break;

    case WM_SIZE:
        MoveWindow(hTextBox, 20, 20,
                   LOWORD(lParam) - 40, HIWORD(lParam) - 40, TRUE);
        break;

    case WM_DESTROY:
        if (WSACleanup())
            ExitOnError("WSACleanup failed");
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
    char title[256];

    if (strlen(lpCmdLine))
        sscanf(lpCmdLine, "%d %d", &shell_port, &file_transfer_port);

    sprintf(title, "Remote Shell Server (listening on ports %d, %d)",
            shell_port, file_transfer_port);

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
        CreateWindow("RemoteShellServerWindowClass", title,
                     WS_OVERLAPPEDWINDOW,
                     20, 20, 600, 400,
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
