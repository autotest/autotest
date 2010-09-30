#define _GNU_SOURCE
#include <sys/syscall.h>
#include <sys/types.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <unistd.h>
#include <time.h>

void ts_subtract(struct timespec *result,
                 const struct timespec *time1, const struct timespec *time2) {
  *result = *time1;
  result->tv_sec -= time2->tv_sec ;
  if (result->tv_nsec < time2->tv_nsec) {
    /* borrow a second */
    result->tv_nsec += 1000000000L;
    result->tv_sec--;
  }
  result->tv_nsec -= time2->tv_nsec;
}

void usage(const char *cmd) {
    fprintf(stderr, "usage: %s <iterations>\n", cmd);
}

int main (int argc, char *argv[]) {
  struct timespec start_time, end_time, elapsed_time;
  uid_t uid;
  long iterations, i;
  double per_call;

  if (argc != 2) {
    usage(argv[0]);
    return 1;
  }

  iterations = atol(argv[1]);
  if (iterations < 0) {
    usage(argv[0]);
    return 1;
  }

  if (clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &start_time)) {
    perror("clock_gettime");
    return errno;
  }

  for (i = iterations; i; i--)
    uid = syscall(SYS_getuid);

  if (clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &end_time)) {
    perror("clock_gettime");
    return errno;
  }

  ts_subtract(&elapsed_time, &end_time, &start_time);
  per_call = (elapsed_time.tv_sec * 1000000000.0L + elapsed_time.tv_nsec) /
      (double)iterations;
  printf("%ld calls in %ld.%09ld s (%lf ns/call)\n", iterations,
         elapsed_time.tv_sec, elapsed_time.tv_nsec, per_call);

  return 0;
}
