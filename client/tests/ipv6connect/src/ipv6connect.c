// Copyright 2008 Google Inc.  Released under the GPL v2.
//
// This test performs numerous connects (with auto-binding), to a server
// listening on all local addresses using an IPv6 socket, by connecting to
// 127.0.0.1, ::ffff:127.0.0.1 and ::1.
//
// The code is really three tests:
//
//   - RunWithOneServer, using CreateServer and ConnectAndAccept,
//     uses one server socket and repeatedly connects to it.
//
//   - RunWithOneShotServers, using CreateServerConnectAndAccept,
//     creates servers, connects to them and then discards them.
//
//   - RunMultiThreaded, using ThreadedCreateServerConnectAndAccept,
//     ThreadedStartServer and ThreadedGetServerFD, is equivalent to
//     RunWithOneShotServers but uses multiple threads, one for the
//     server and one for the client.
//
// Each of these tests triggers error conditions on different kernels
// to a different extent.

#include <arpa/inet.h>
#include <netinet/in.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

// Which loopback address to connect to.
enum LoopbackAddr { V4_LOOPBACK, V6_LOOPBACK, V6_MAPPED_V4_LOOPBACK };

// Connect to a listening TCP socket, and accept the connection.
static void ConnectAndAccept(enum LoopbackAddr addr, int server_fd, int port) {
  struct sockaddr_in6 sa;
  socklen_t addr_len;
  int client_fd, accepted_fd;

  if (addr == V6_LOOPBACK || addr == V6_MAPPED_V4_LOOPBACK) {
    char buf[INET6_ADDRSTRLEN];

    memset(&sa, 0, sizeof(sa));
    if ((client_fd = socket(AF_INET6, SOCK_STREAM, IPPROTO_TCP)) == -1) {
      perror("socket");
      exit(1);
    }
    if (addr == V6_LOOPBACK) {
      inet_pton(AF_INET6, "::1", &sa.sin6_addr);
    } else if (addr == V6_MAPPED_V4_LOOPBACK) {
      inet_pton(AF_INET6, "::ffff:127.0.0.1", &sa.sin6_addr);
    }
    if (!inet_ntop(AF_INET6, &sa.sin6_addr, buf, INET6_ADDRSTRLEN)) {
      perror("inet_ntop");
      exit(1);
    }
    addr_len = sizeof(sa);
    sa.sin6_family = AF_INET6;
    sa.sin6_port = port;
    if (connect(client_fd, (struct sockaddr*)(&sa),
                sizeof(struct sockaddr_in6)) == -1) {
      perror("connect");
      exit(1);
    }
    write(2, (addr == V6_LOOPBACK) ? "+" : "-", 1);
  } else {
    struct sockaddr_in sa4;

    if ((client_fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)) == -1) {
      perror("socket");
      exit(1);
    }
    memset(&sa4, 0, sizeof(sa4));
    sa4.sin_family = AF_INET;
    inet_pton(AF_INET, "127.0.0.1", &sa4.sin_addr);
    sa4.sin_port = port;
    if (connect(client_fd, (struct sockaddr*)(&sa4),
                sizeof(struct sockaddr_in)) == -1) {
      perror("connect");
      exit(1);
    }
    write(2, ".", 1);
  }
  addr_len = sizeof(sa);
  if ((accepted_fd = accept(server_fd,
                            (struct sockaddr*)(&sa), &addr_len)) == -1) {
    perror("accept");
    exit(1);
  }
  close(client_fd);
  close(accepted_fd);
}

// Create a listening TCP socket.
static void CreateServer(int* server_fd, int* port) {
  struct sockaddr_in6 sa;
  socklen_t addr_len;

  memset(&sa, 0, sizeof(sa));
  if ((*server_fd = socket(AF_INET6, SOCK_STREAM, IPPROTO_TCP)) == -1) {
    perror("socket");
    exit(1);
  }
  addr_len = sizeof(sa);
  sa.sin6_family = AF_INET6;
  sa.sin6_addr = in6addr_any;
  sa.sin6_port = 0;
  if (bind(*server_fd, (struct sockaddr*)(&sa), sizeof(sa)) == -1) {
    perror("bind");
    exit(1);
  }
  if (getsockname(*server_fd, (struct sockaddr*)(&sa), &addr_len) == -1) {
    perror("getsockname");
    exit(1);
  }
  if (listen(*server_fd, 10) == -1) {
    perror("listen");
    exit(1);
  }
  *port = sa.sin6_port;
}

// Create a socket, connect to it, accept, and discard both.
static void CreateServerConnectAndAccept(enum LoopbackAddr addr) {
  struct sockaddr_in6 sa;
  socklen_t addr_len;
  int server_fd, client_fd, accepted_fd, connect_rc;

  if ((server_fd = socket(AF_INET6, SOCK_STREAM, IPPROTO_TCP)) == -1) {
    perror("socket");
    exit(1);
  }
  addr_len = sizeof(sa);
  memset(&sa, 0, sizeof(sa));
  sa.sin6_family = AF_INET6;
  sa.sin6_addr = in6addr_any;
  sa.sin6_port = 0;
  if (bind(server_fd, (struct sockaddr*)(&sa), sizeof(sa)) == -1) {
    perror("bind");
    exit(1);
  }
  if (getsockname(server_fd, (struct sockaddr*)(&sa), &addr_len) == -1) {
    perror("getsockname");
    exit(1);
  }
  if (listen(server_fd, 10) == -1) {
    perror("listen");
    exit(1);
  }
  if (addr == V6_LOOPBACK || addr == V6_MAPPED_V4_LOOPBACK) {
    char buf[INET6_ADDRSTRLEN];

    if ((client_fd = socket(AF_INET6, SOCK_STREAM, IPPROTO_TCP)) == -1) {
      perror("socket");
      exit(1);
    }
    if (addr == V6_LOOPBACK) {
      inet_pton(AF_INET6, "::1", &sa.sin6_addr);
    } else if (addr == V6_MAPPED_V4_LOOPBACK) {
      inet_pton(AF_INET6, "::ffff:127.0.0.1", &sa.sin6_addr);
    }
    if (!inet_ntop(AF_INET6, &sa.sin6_addr, buf, INET6_ADDRSTRLEN)) {
      perror("inet_ntop");
      exit(1);
    }
    connect_rc = connect(client_fd, (struct sockaddr*)(&sa),
                         sizeof(struct sockaddr_in6));
    write(2, (addr == V6_MAPPED_V4_LOOPBACK) ? "-" : "+", 1);
  } else {
    struct sockaddr_in sa4;

    if ((client_fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)) == -1) {
      perror("socket");
      exit(1);
    }
    memset(&sa4, 0, sizeof(sa4));
    sa4.sin_family = AF_INET;
    inet_pton(AF_INET, "127.0.0.1", &sa4.sin_addr);
    sa4.sin_port = sa.sin6_port;
    connect_rc = connect(client_fd, (struct sockaddr*)(&sa4),
                         sizeof(struct sockaddr_in));
    write(2, ".", 1);
  }
  if (connect_rc == -1) {
    perror("connect");
    exit(1);
  }
  addr_len = sizeof(sa);
  if ((accepted_fd = accept(server_fd,
                            (struct sockaddr*)(&sa), &addr_len)) == -1) {
    perror("accept");
    exit(1);
  }
  close(accepted_fd);
  close(client_fd);
  close(server_fd);
}

// Globals for threaded version.
static volatile int threaded_listening = 0;
static int threaded_server_fd;
static pthread_mutex_t threaded_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t threaded_cond = PTHREAD_COND_INITIALIZER;

// Block until listening, then return server address.
static int ThreadedGetServerFD() {
  pthread_mutex_lock(&threaded_mutex);
  while (!threaded_listening) {
    pthread_cond_wait(&threaded_cond, &threaded_mutex);
  }
  pthread_mutex_unlock(&threaded_mutex);
  return threaded_server_fd;
}

// Start a server which accepts one connection.
static void* ThreadedStartServer(void* unused) {
  struct sockaddr_in6 sa;
  socklen_t addr_len = sizeof(sa);
  int accept_fd;

  if ((threaded_server_fd = socket(AF_INET6, SOCK_STREAM, IPPROTO_TCP)) == -1) {
    perror("socket");
    exit(1);
  }

  // Any IP, unused port.
  memset(&sa, 0, sizeof(sa));
  sa.sin6_family = AF_INET6;
  sa.sin6_addr = in6addr_any;
  sa.sin6_port = 0;

  // Bind.
  if (bind(threaded_server_fd, (struct sockaddr*)(&sa), sizeof(sa)) == -1) {
    perror("bind");
    exit(1);
  }

  // Listen.
  if (listen(threaded_server_fd, 10) == -1) {
    perror("listen");
    exit(1);
  }
  pthread_mutex_lock(&threaded_mutex);
  threaded_listening = 1;
  pthread_cond_signal(&threaded_cond);
  pthread_mutex_unlock(&threaded_mutex);

  // Try to accept.
  if ((accept_fd = accept(threaded_server_fd, (struct sockaddr*)(&sa),
                          &addr_len)) == -1) {
    perror("accept");
    exit(1);
  }

  // All done.
  close(threaded_server_fd);
  close(accept_fd);
  threaded_listening = 0;
  return NULL;
}

// Start a server thread, then connect to it via TCP.
static void ThreadedCreateServerConnectAndAccept(enum LoopbackAddr addr) {
  pthread_t pthread;
  int server_fd, client_fd;
  struct sockaddr_in6 sa;
  socklen_t addr_len = sizeof(sa);

  pthread_create(&pthread, NULL, ThreadedStartServer, NULL);

  // Get the server address information -- this call will block until
  // the server is listening.
  server_fd = ThreadedGetServerFD();
  memset(&sa, 0, sizeof(sa));
  if (getsockname(server_fd, (struct sockaddr*)(&sa), &addr_len) == -1) {
    perror("getsockname");
    exit(1);
  }

  if (addr == V6_LOOPBACK || addr == V6_MAPPED_V4_LOOPBACK) {
    char buf[INET6_ADDRSTRLEN];

    if ((client_fd = socket(AF_INET6, SOCK_STREAM, IPPROTO_TCP)) == -1) {
      perror("socket");
      exit(1);
    }

    // Check that we are listening on ::
    if (!inet_ntop(AF_INET6, &sa.sin6_addr, buf, INET6_ADDRSTRLEN)) {
      fprintf(stderr, "inet_ntop failed\n");
      exit(1);
    }
    if (strlen(buf) != 2) {
      fprintf(stderr, "Expected to listen on ::, instead listening on %s", buf);
      exit(1);
    }

    if (addr == V6_LOOPBACK) {
      inet_pton(AF_INET6, "::1", &sa.sin6_addr);
    } else if (addr == V6_MAPPED_V4_LOOPBACK) {
      inet_pton(AF_INET6, "::ffff:127.0.0.1", &sa.sin6_addr);
    }
    if (connect(client_fd, (struct sockaddr*)(&sa),
                sizeof(struct sockaddr_in6)) == -1) {
      perror("connect");
      exit(1);
    }
  } else {
    struct sockaddr_in sa4;

    if ((client_fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)) == -1) {
      perror("socket");
      exit(1);
    }

    memset(&sa4, 0, sizeof(sa4));
    sa4.sin_family = AF_INET;
    inet_aton("127.0.0.1", &sa4.sin_addr);
    sa4.sin_port = sa.sin6_port;

    if (connect(client_fd, (struct sockaddr*)(&sa4),
                sizeof(struct sockaddr_in)) == -1) {
      perror("connect");
      exit(1);
    }
  }

  // Update progress.
  switch (addr) {
    case V4_LOOPBACK:
      write(2, ".", 1);
      break;
    case V6_MAPPED_V4_LOOPBACK:
      write(2, "-", 1);
      break;
    case V6_LOOPBACK:
      write(2, "+", 1);
      break;
  }

  // Close our connection and wait for the server thread to shutdown.
  close(client_fd);
  pthread_join(pthread, NULL);
}

static void RunWithOneServer(int outer, int inner) {
  int i, j, server_fd, port;
  fprintf(stderr, "Starting test with one server port for all connects\n");
  for (i = 0; i < outer; ++i) {
    CreateServer(&server_fd, &port);
    for (j = 0; j < inner; ++j) {
      ConnectAndAccept(V4_LOOPBACK, server_fd, port);
    }
    write(2, "\n", 1);
    for (j = 0; j < inner; ++j) {
      ConnectAndAccept(V6_MAPPED_V4_LOOPBACK, server_fd, port);
    }
    write(2, "\n", 1);
    for (j = 0; j < inner; ++j) {
      ConnectAndAccept(V6_LOOPBACK, server_fd, port);
    }
    write(2, "\n", 1);
    close(server_fd);
  }
}

static void RunWithOneShotServers(int outer, int inner) {
  int i, j;
  fprintf(stderr, "Starting test with one server port per connect\n");
  for (i = 0; i < outer; ++i) {
    for (j = 0; j < inner; ++j) {
      CreateServerConnectAndAccept(V4_LOOPBACK);
    }
    write(2, "\n", 1);
    for (j = 0; j < inner; ++j) {
      CreateServerConnectAndAccept(V6_MAPPED_V4_LOOPBACK);
    }
    write(2, "\n", 1);
    for (j = 0; j < inner; ++j) {
      CreateServerConnectAndAccept(V6_LOOPBACK);
    }
    write(2, "\n", 1);
  }
}

static void RunMultiThreaded(int outer, int inner) {
  int i, j;
  fprintf(stderr, "Starting multi-threaded test\n");
  for (i = 0; i < outer; ++i) {
    for (j = 0; j < inner; ++j) {
      ThreadedCreateServerConnectAndAccept(V4_LOOPBACK);
    }
    write(2, "\n", 1);
    for (j = 0; j < inner; ++j) {
      ThreadedCreateServerConnectAndAccept(V6_MAPPED_V4_LOOPBACK);
    }
    write(2, "\n", 1);
    for (j = 0; j < inner; ++j) {
      ThreadedCreateServerConnectAndAccept(V6_LOOPBACK);
    }
    write(2, "\n", 1);
  }
}

static const char* usage =
    "Usage: %s [types [outer [inner]]]\n"
    "Arguments:\n"
    "\ttypes: String consisting of [OMT], for the test types to run\n"
    "\t       O: One server, multiple connects\n"
    "\t       M: One server per connect (multiple server ports)\n"
    "\t       T: Multi-threaded version of \'M\'\n"
    "\touter: Number of passes through the outer loops, default 10\n"
    "\tinner: Number of passes through the inner loops, default 75\n";

static void Usage(char *argv0) {
  fprintf(stderr, usage, argv0);
  exit(2);
}

int main(int argc, char** argv) {
  char *types = "OMT";
  int i, inner = 75, outer = 10, timediff;
  struct timeval tv0, tv1;

  // Parse the options.
  if (argc == 4) {
    inner = atoi(argv[3]);
    if (inner <= 0) {
      Usage(argv[0]);
    }
    argc--;
  }
  if (argc == 3) {
    outer = atoi(argv[2]);
    if (outer <= 0) {
      Usage(argv[0]);
    }
    argc--;
  }
  if (argc == 2) {
    types = argv[1];
    if (strspn(types, "OMT") != strlen(types)) {
      Usage(argv[0]);
    }
    argc--;
  }
  if (argc != 1) {
    Usage(argv[0]);
  }

  // Run the tests.
  gettimeofday(&tv0, NULL);
  for (i = 0; i < strlen(types); ++i) {
    switch (types[i]) {
      case 'O':
        RunWithOneServer(outer, inner);
        break;
      case 'M':
        RunWithOneShotServers(outer, inner);
        break;
      case 'T':
        RunMultiThreaded(outer, inner);
        break;
    }
  }
  gettimeofday(&tv1, NULL);
  timediff = (tv1.tv_sec - tv0.tv_sec) * 1000000 + tv1.tv_usec - tv0.tv_usec;
  fprintf(stderr, "Total time = %d.%06ds\n", timediff / 1000000,
          timediff % 1000000);
  exit(0);
}
