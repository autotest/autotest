#define _XOPEN_SOURCE 500 /* pwrite */
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <libaio.h>
#include <errno.h>
#include <time.h>
#include <sys/types.h>
#include <sys/wait.h>

/*
 * DIO invalidates the read cache after it writes.  At one point it tried to
 * return EIO if this failed.  When called from AIO, though, this EIO return
 * would clobber EIOCBQUEUED and cause fs/aio.c and fs/direct-io.c to complete
 * an iocb twice.  This typically references freed memory from an interrupt
 * handler and oopses.
 *
 * This test hits the race after at most two minutes on a single spindle.  It
 * spins performing large dio writes.  It also spins racing buffered writes.
 * It assumes it's on ext3 using ordered writes.  The ordered write bhs can be
 * pinned by jbd as a transaction commits.  If invalidate_inode_pages2_range()
 * hits pages backed by those buffers ->releasepage will fail and it'll try to
 * return -EIO.
 */
#ifndef O_DIRECT
#define O_DIRECT         040000 /* direct disk access hint */
#endif

#define GINORMOUS (32 * 1024 * 1024)


/* This test never survived to 180 seconds on a single spindle */
#define SECONDS 200

static unsigned char buf[GINORMOUS] __attribute((aligned (512)));

#define fail(fmt , args...) do {\
	printf(fmt , ##args);	\
	exit(1);		\
} while (0)

void spin_dio(int fd)
{
	io_context_t ctx;
	struct iocb iocb;
	struct iocb *iocbs[1] = { &iocb };
	struct io_event event;
	int ret;

        io_prep_pwrite(&iocb, fd, buf, GINORMOUS, 0);

	ret = io_queue_init(1, &ctx);
	if (ret)
		fail("io_queue_init returned %d", ret);

	while (1) {
		ret = io_submit(ctx, 1, iocbs);
		if (ret != 1)
			fail("io_submit returned %d instead of 1", ret);

		ret = io_getevents(ctx, 1, 1, &event, NULL);
		if (ret != 1)
			fail("io_getevents returned %d instead of 1", ret);

		if (event.res == -EIO) {
			printf("invalidation returned -EIO, OK\n");
			exit(0);
		}

		if (event.res != GINORMOUS)
			fail("event res %ld\n", event.res);
	}
}

void spin_buffered(int fd)
{
	int ret;

	while (1) {
		ret = pwrite(fd, buf, GINORMOUS, 0);
		if (ret != GINORMOUS)
			fail("buffered write returned %d", ret);
	}
}

static void alarm_handler(int signum)
{
}

int main(int argc, char **argv)
{
	pid_t buffered_pid;
	pid_t dio_pid;
	pid_t pid;
	int fd;
	int fd2;
	int status;

	if (argc != 2)
		fail("only arg should be file name");

	fd = open(argv[1], O_DIRECT|O_CREAT|O_RDWR, 0644);
	if (fd < 0)
		fail("open dio failed: %d\n", errno);

	fd2 = open(argv[1], O_RDWR, 0644);
	if (fd < 0)
		fail("open failed: %d\n", errno);

	buffered_pid = fork();
	if (buffered_pid < 0)
		fail("fork failed: %d\n", errno);

	if (buffered_pid == 0) {
		spin_buffered(fd2);
		exit(0);
	}

	dio_pid = fork();
	if (dio_pid < 0) {
		kill(buffered_pid, SIGKILL);
		fail("fork failed: %d\n", errno);
	}

	if (dio_pid == 0) {
		spin_dio(fd);
		exit(0);
	}

	signal(SIGALRM, alarm_handler);
	alarm(SECONDS);

	pid = wait(&status);
	if (pid < 0 && errno == EINTR) {
		/* if we timed out then we're done */
		kill(buffered_pid, SIGKILL);
		kill(dio_pid, SIGKILL);
		printf("ran for %d seconds without error, passing\n", SECONDS);
		exit(0);
	}

	if (pid == dio_pid)
		kill(buffered_pid, SIGKILL);
	else
		kill(dio_pid, SIGKILL);

	/* 
	 * pass on the child's pass/fail return code or fail if the child 
	 * didn't exit cleanly.
	 */
	exit(WIFEXITED(status) ? WEXITSTATUS(status) : 1);
}
