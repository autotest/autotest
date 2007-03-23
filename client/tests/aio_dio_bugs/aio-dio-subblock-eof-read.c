/*
 *  Code taken from an example posted to linux-aio at kvack.org
 *  Original Author: Drangon Zhou
 *  Munged by Jeff Moyer to get it to build and to incorporate it into
 *  the autotest framework.
 *
 *  Description:  This source code implements a test to ensure that an AIO
 *  read of the last block in a file opened with O_DIRECT returns the proper
 *  amount of data.  In the past, there was a bug that resulted in a return
 *  value of the requested block size, when in fact there was only a fraction
 *  of that data available.  Thus, if the last data block contained 300 bytes
 *  worth of data, and the user issued a 4k read, we want to ensure that
 *  the return value is 300, not 4k.
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <libaio.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>

/* Create a file of a size that is not a multiple of block size */
#define FILE_SIZE	300

#define fail(fmt , args...) 	\
do {				\
	printf(fmt , ##args);	\
	exit(1);		\
} while (0)

static unsigned char buffer[4096] __attribute((aligned (512)));

int
main(int argc, char **argv)
{
	int ret;
	int fd;
	const char *filename;
	struct iocb myiocb;
	struct iocb *cb = &myiocb;
	io_context_t ioctx;
	struct io_event ie;
    
	if (argc != 2)
		fail("only arg should be file name");

	filename = argv[1];
	fd = open(filename, O_CREAT|O_RDWR|O_DIRECT, 0600);
	if (fd < 0)
		fail("open returned error %d\n", errno);

	ret = ftruncate(fd, FILE_SIZE);
	if (ret < 0)
		fail("truncate returned error %d\n", errno);

	/* <1> use normal disk read, this should be ok */
	ret = read(fd, buffer, 4096);
	if (ret != FILE_SIZE)
		fail("buffered read returned %d, should be 300\n", ret);

	/* <2> use AIO disk read, it sees error. */
	memset(&myiocb, 0, sizeof(myiocb));
	cb->data = 0;
	cb->key = 0;
	cb->aio_lio_opcode = IO_CMD_PREAD;
	cb->aio_reqprio = 0; 
	cb->aio_fildes = fd; 
	cb->u.c.buf = buffer;
	cb->u.c.nbytes = 4096;
	cb->u.c.offset = 0;
    
	ret = io_queue_init(1, &ioctx);
	if (ret != 0)
		fail("io_queue_init returned error %d\n", ret);

	ret = io_submit(ioctx, 1, &cb);
	if (ret != 1)
		fail("io_submit returned error %d\n", ret);

	ret = io_getevents(ioctx, 1, 1, &ie, NULL);
	if (ret != 1)
		fail("io_getevents returned %d\n", ret);

	/*
	 *  If all goes well, we should see 300 bytes read.  If things
	 *  are broken, we may very well see a result of 4k.
	 */
	if (ie.res != FILE_SIZE)
		fail("AIO read of last block in file returned %d bytes, "
		     "expected %d\n", ret, FILE_SIZE);

	printf("AIO read of last block in file succeeded.\n");
	return 0;
}
