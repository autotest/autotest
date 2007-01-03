// Copyright Martin J. Bligh & Google. <mbligh@google.com>.
// New Year's Eve, 2006 
// Released under the GPL v2.
//
// Compile with -D_FILE_OFFSET_BITS=64 -D _GNU_SOURCE

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
#define VERIFY_BLOCKS 16

char *filename = "testfile";
unsigned int megabytes = 1;
unsigned int blocksize = 4096;
unsigned int seconds = 15;
unsigned int linear_tasks = 1;
unsigned int random_tasks = 4;
unsigned int blocks;
unsigned int sectors_per_block;
int fd;

void die(char *error)
{
	fprintf(stderr, error);
	fprintf(stderr, "\n");
	exit(1);
}

/*
 * Fill a block with it's own sector number
 * buf must be at least blocksize
 */
void write_blocks(unsigned int block, unsigned int *buf, unsigned int blocks)
{
	unsigned int i, sec_offset, sector;
	off_t offset;
	unsigned int writesize = blocksize * blocks;
	unsigned int sectors = writesize / SECTOR_SIZE;

	for (sec_offset = 0; sec_offset < sectors; sec_offset++) {
		sector = (block * sectors_per_block) + sec_offset;

		for (i = 0; i < SECTOR_SIZE / sizeof(unsigned int); i++)
			buf[(sec_offset * UINT_PER_SECTOR) + i] = sector;
	}

	offset = block; offset *= blocksize;   // careful of overflow
	lseek(fd, offset, SEEK_SET);
	if (write(fd, buf, writesize) != writesize)
		die("write failed");
}

/*
 * Verify a block contains it's own sector number
 * buf must be at least blocksize
 * 
 * We only check the first number - the rest is pretty pointless
 */
void verify_blocks(unsigned int block, unsigned int *buf, unsigned int blocks)
{
	unsigned int sec_offset, sector;
	off_t offset;
	unsigned int readsize = blocksize * blocks;
	unsigned int sectors = readsize / SECTOR_SIZE;

	offset = block; offset *= blocksize;   // careful of overflow
	lseek(fd, offset, SEEK_SET);
	if (read(fd, buf, readsize) != readsize)
		die("read failed");

	for (sec_offset = 0; sec_offset < sectors; sec_offset++) {
		sector = (block * sectors_per_block) + sec_offset;

		if (buf[sec_offset * UINT_PER_SECTOR] != sector) {
			printf("sector %08x says %08x\n", sector, 
					buf[sec_offset * UINT_PER_SECTOR]);
		}
	}
}

void write_file(int fd, unsigned int end_time, int random_access)
{
	int pid = fork();
	unsigned int block;
	void *buffer;

	if (pid < 0)
		die ("error forking child");
	if (pid)			// parent
		return;

	buffer = malloc(blocksize);

	if (random_access) {
		srandom(time(NULL) - getpid());
		while(time(NULL) < end_time) {
			block = (unsigned int) (random() % blocks);
			write_blocks(block, buffer, 1);
		}
	} else {
		while(time(NULL) < end_time)
			for (block = 0; block < blocks; block++)
				write_blocks(block, buffer, 1);
	}
	free(buffer);
	exit(0);
}

void verify_file(char *filename, unsigned int end_time, int random_access, 
								int direct)
{
	int fd;
	unsigned int block;
	int pid = fork();
	void *buffer;

	if (pid < 0)
		die ("error forking child");
	if (pid)			// parent
		return;

	if (direct)
		fd = open(filename, O_RDONLY | O_TRUNC | O_CREAT | O_DIRECT);
	else
		fd = open(filename, O_RDONLY | O_TRUNC | O_CREAT | O_DIRECT);
		
	buffer = malloc(blocksize * VERIFY_BLOCKS);

	if (random_access) {
		srandom(time(NULL) - getpid());
		while(time(NULL) < end_time) {
			block = (unsigned int) (random() % blocks);
			verify_blocks(block, buffer, 1);
		}
	} else {
		while(time(NULL) < end_time)
			for (block = 0; block < blocks; block++)
				verify_blocks(block, buffer, VERIFY_BLOCKS);
	}
	free(buffer);
	exit(0);
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
	time_t start_time, end_time;
	int tasks, opt;
	void *init_buffer;

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
	sectors_per_block = blocksize / SECTOR_SIZE;

	/* Initialise file */
	fd = open(filename, O_RDWR | O_TRUNC | O_CREAT, 0666);
	if (fd < 0)
		die("open failed");

	start_time = time(NULL);

	/* Initialise all file data to correct blocks */
	init_buffer = malloc(blocksize * VERIFY_BLOCKS);
	for (block = 0; block < blocks; block++)
		write_blocks(block, init_buffer, VERIFY_BLOCKS);
	if(fsync(fd) != 0)
		die("fsync failed");
	free(init_buffer);
	
	printf("Wrote %d MB to %s (%d seconds)\n", megabytes, filename, (int) (time(NULL) - start_time));

	end_time = time(NULL) + seconds;

	/* Fork off all linear access pattern tasks */
	for (tasks = 0; tasks < linear_tasks; tasks++)
		write_file(fd, end_time, 0);

	/* Fork off all random access pattern tasks */
	for (tasks = 0; tasks < random_tasks; tasks++)
		write_file(fd, end_time, 1);

	/* Verify in all four possible ways */
	verify_file(filename, end_time, 0, 0);
	verify_file(filename, end_time, 0, 1);
	verify_file(filename, end_time, 1, 0);
	verify_file(filename, end_time, 1, 1);

	return 0;
}
