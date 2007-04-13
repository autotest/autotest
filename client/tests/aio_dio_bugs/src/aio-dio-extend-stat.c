#define __USE_GNU
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <libaio.h>
#include <malloc.h>
#include <fcntl.h>
#include <pthread.h>
#include <errno.h>

#ifndef O_DIRECT
#define O_DIRECT         040000 /* direct disk access hint */
#endif


/*
 * This was originally submitted to
 * http://bugzilla.kernel.org/show_bug.cgi?id=6831 by 
 * Rafal Wijata <wijata@nec-labs.com>.  It caught a race in dio aio completion
 * that would call aio_complete() before the dio callers would update i_size.
 * A stat after io_getevents() would not see the new file size.
 *
 * The bug was fixed in the fs/direct-io.c completion reworking that appeared
 * in 2.6.20.  This test should fail on 2.6.19.
 */

#define BUFSIZE 1024

static unsigned char buf[BUFSIZE] __attribute((aligned (512)));

/* 
 * this was arbitrarily chosen to take about two seconds on a dual athlon in a
 * debugging kernel.. it trips up long before that.
 */
#define MAX_AIO_EVENTS 4000

#define fail(fmt , args...) do {\
	printf(fmt , ##args);	\
	exit(1);		\
} while (0)

void fun_write1(void* ptr);
void fun_writeN(void* ptr);
void fun_read(void* ptr);

int  handle = 0;
io_context_t ctxp;
struct iocb *iocbs[MAX_AIO_EVENTS];
struct io_event ioevents[MAX_AIO_EVENTS];

volatile int submittedSize = 0; //synchronization

int main(int argc, char **argv)
{
	pthread_t thread_read; 
	pthread_t thread_write;
	int i;
	int ret;

	if (argc != 2)
		fail("only arg should be file name\n");

	for (i = 0; i < BUFSIZE; ++i)
		buf[i] = 'A' + (char)(i % ('Z'-'A'+1));

	buf[BUFSIZE-1] = '\n';

	handle = open(argv[1], O_CREAT | O_TRUNC | O_DIRECT | O_RDWR, 0600); 
	if (handle == -1) 
		fail("failed to open test file %s, errno: %d\n",
			argv[1], errno);

	memset(&ctxp, 0, sizeof(ctxp));
	ret = io_setup(MAX_AIO_EVENTS, &ctxp);
	if (ret)
		fail("io_setup returned %d\n", ret);

	for (i = 0; i < MAX_AIO_EVENTS; ++i) {

		iocbs[i] = calloc(1, sizeof(struct iocb));
		if (iocbs[i] == NULL)
			fail("failed to allocate an iocb\n");
	
/*		iocbs[i]->data = i; */
		iocbs[i]->aio_fildes = handle;
		iocbs[i]->aio_lio_opcode = IO_CMD_PWRITE;
		iocbs[i]->aio_reqprio = 0;
		iocbs[i]->u.c.buf = buf;
		iocbs[i]->u.c.nbytes = BUFSIZE;
		iocbs[i]->u.c.offset = BUFSIZE*i;
	}

	pthread_create(&thread_read, NULL, (void*)&fun_read, NULL);
	pthread_create(&thread_write, NULL, (void*)&fun_writeN, NULL);

	pthread_join(thread_read, NULL);
	pthread_join(thread_write, NULL);

	io_destroy(ctxp);
	close(handle);

	printf("%u iterations of racing extensions and collection passed\n",
		MAX_AIO_EVENTS);

	return 0;
}

void fun_read(void *ptr)
{
	long n = MAX_AIO_EVENTS;
	struct stat filestat;
	long long exSize;
	long i;
	long r;

	while (n > 0) {
		r = io_getevents(ctxp, 1, MAX_AIO_EVENTS, ioevents, NULL);
		if (r < 0) 
			fail("io_getevents returned %ld\n", r);

		n -= r;
		for (i = 0; i < r; ++i) {
			if (ioevents[i].obj->u.c.nbytes != BUFSIZE)
				fail("error in block: expacted %d bytes, "
				     "receiced %ld\n", BUFSIZE,
				     ioevents[i].obj->u.c.nbytes);

			exSize = ioevents[i].obj->u.c.offset +
				 ioevents[i].obj->u.c.nbytes;
			fstat(handle, &filestat);
			if (filestat.st_size < exSize)
				fail("write of %lu bytes @%llu finished, "
				     "expected filesize at least %llu, but "
				     "got %ld\n", ioevents[i].obj->u.c.nbytes,
				     ioevents[i].obj->u.c.offset, exSize,
				     filestat.st_size);
		}
	}
}

void fun_writeN(void *ptr)
{
	int i;
	int ret;

	for(i = 0; i < MAX_AIO_EVENTS; ++i) {
		ret = io_submit(ctxp, 1, &(iocbs[i]));
		if (ret != 1)
			fail("io_subit returned %d instead of 1\n", ret);
	}
}

void fun_write1(void *ptr)
{
	int ret;
    
	ret = io_submit(ctxp, MAX_AIO_EVENTS, iocbs);
	if (ret !=  MAX_AIO_EVENTS)
		fail("io_subit returned %d instead of %u\n", ret,
		     MAX_AIO_EVENTS);
}
