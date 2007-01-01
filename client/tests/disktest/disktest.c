// Copyright Martin J. Bligh & Google. <mbligh@google.com>.
// New Year's Eve, 2006 
// Released under the GPL v2.
//
// Compile with -D_FILE_OFFSET_BITS=64

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <time.h>
#include <getopt.h>

#define SECTOR_SIZE 512
#define UINT_PER_SECTOR  (SECTOR_SIZE / sizeof(unsigned int))

char *filename = "testfile";
unsigned int megabytes = 1;
unsigned int blocksize = 4096;
unsigned int seconds = 15;
unsigned int linear_tasks = 4;
unsigned int random_tasks = 4;
unsigned int blocks;
unsigned int sectors_per_block;
int fd;

void die(char *error)
{
	fprintf(stderr, error);
	exit(1);
}

/*
 * Fill a block with it's own sector number
 * buf must be at least blocksize
 */
void write_block(unsigned int block, unsigned int *buf)
{
	unsigned int i, sec_offset, sector;
	off_t offset;

	for (sec_offset = 0; sec_offset < sectors_per_block; sec_offset++) {
		sector = (block * sectors_per_block) + sec_offset;

		for (i = 0; i < SECTOR_SIZE / sizeof(unsigned int); i++)
			buf[(sec_offset * UINT_PER_SECTOR) + i] = sector;
	}

	offset = block; offset *= blocksize;   // careful of overflow
	lseek(fd, offset, SEEK_SET);
	if (write(fd, buf, blocksize) != blocksize)
		die("write failed");
}

/*
 * Verify a block contains it's own sector number
 * buf must be at least blocksize
 * 
 * We only check the first number - the rest is pretty pointless
 */
void verify_block(unsigned int block, unsigned int *buf)
{
	unsigned int sec_offset, sector;
	off_t offset;

	offset = block; offset *= blocksize;   // careful of overflow
	lseek(fd, offset, SEEK_SET);
	if (read(fd, buf, blocksize) != blocksize)
		die("read failed");

	for (sec_offset = 0; sec_offset < sectors_per_block; sec_offset++) {
		sector = (block * sectors_per_block) + sec_offset;

		if (buf[sec_offset * UINT_PER_SECTOR] != sector) {
			printf("sector %08x says %08x\n", sector, 
					buf[sec_offset * UINT_PER_SECTOR]);
		}
	}
}

void usage(void)
{
	printf("Usage: disktest\n");
	printf("    [-f filename]        filename to use     (testfile)\n");
	printf("    [-s seconds]         seconds to run for  (15)\n");
	printf("    [-m megabytes]       megabytes to use    (1)\n");
	printf("    [-b blocksize]	 blocksize           (4096)\n");
	printf("    [-l linear tasks]    linear access tasks (4)\n");
	printf("    [-r random tasks]    random access tasks (4)\n");
	printf("\n");
}

int main(int argc, char *argv[])
{
	unsigned int block;
	time_t end_time;
	int tasks, pid, opt;
	void *buffer;

	/* Parse all input options */
	while ((opt = getopt(argc, argv, "f:s:m:b:l:r:")) != -1) {
		switch (opt) {
			case 'f':
				filename = optarg;
				break;
			case 's':
				seconds = atoi(optarg);
				break;
			case 'm':
				megabytes = atoi(optarg);
				break;
			case 'b':
				blocksize = atoi(optarg);
				break;
			case 'l':
				linear_tasks = atoi(optarg);
				break;
			case 'r':
				random_tasks = atoi(optarg);
				break;
			default:
				usage();
				exit(1);
		}
	}
	argc -= optind;
	argv += optind;

	/* blocksize must be < 1MB, and a divisor. Tough */
	blocks = megabytes * (1024 * 1024 / blocksize);
	buffer = malloc(blocksize);

	/* Initialise file */
	fd = open(filename, O_RDWR | O_TRUNC | O_CREAT, 0666);
	if (fd < 0)
		die("open failed");

	/* Initialise all file data to correct blocks */
	for (block = 0; block < blocks; block++)
		write_block(block, buffer);

	end_time = time(NULL) + seconds;

	/* Fork off all linear access pattern tasks */
	for (tasks = 0; tasks < linear_tasks; tasks++) {
		pid = fork();
		if (!pid) {                         // child
			unsigned int block;
			void *buf = malloc(blocksize);

			while(time(NULL) < end_time)
				for (block = 0; block < blocks; block++)
					write_block(block, buf);

			free(buf);
			exit(0);
		}
	}

	/* Fork off all random access pattern tasks */
	for (tasks = 0; tasks < random_tasks; tasks++) {
		pid = fork();
		if (!pid) {                         // child
			void *buf = malloc(blocksize);
			unsigned int block;

			srandom(time(NULL) - getpid());
			while(time(NULL) < end_time) {
				block = (unsigned int) (random() % blocks);
				write_block(block, buf);
			}

			free(buf);
			exit(0);
		}
	}

	/* The parent task's job is to verify the data */
	while(time(NULL) < end_time)
		for (block = 0; block < blocks; block++)
			verify_block(block, buffer);

	free(buffer);
	return 0;
}
