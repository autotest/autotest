// Copyright Martin J. Bligh & Google. <mbligh@google.com>.
// New Year's Eve, 2006 
// Released under the GPL v2.
//
// Compile with -D_FILE_OFFSET_BITS=64 -D _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <time.h>
#include <getopt.h>
#include <errno.h>
#include <malloc.h>
#include <string.h>

struct pattern {
	unsigned int sector;
	unsigned int signature;
};

#define SECTOR_SIZE 512
#define PATTERN_PER_SECTOR  (SECTOR_SIZE / sizeof(struct pattern))

char *filename = "testfile";
volatile int stop = 0;
int init_only = 0;
int verify_only = 0;
unsigned int megabytes = 1;
unsigned int skip_mb = 0;
unsigned int start_block = 0;
unsigned int blocksize = 4096;
unsigned int seconds = 15;
unsigned int linear_tasks = 1;
unsigned int random_tasks = 4;
unsigned int blocks;
unsigned int sectors_per_block;
unsigned int signature = 0;
unsigned int stop_on_error = 0;

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
void write_block(int fd, unsigned int block, struct pattern *buffer)
{
	unsigned int i, sec_offset, sector;
	off_t offset;
	struct pattern *sector_buffer;

	for (sec_offset = 0; sec_offset < sectors_per_block; sec_offset++) {
		sector = (block * sectors_per_block) + sec_offset;
		sector_buffer = &buffer[sec_offset * PATTERN_PER_SECTOR];

		for (i = 0; i < PATTERN_PER_SECTOR; i++) {
			sector_buffer[i].sector = sector;
			sector_buffer[i].signature = signature;
		}
	}

	offset = block; offset *= blocksize;   // careful of overflow
	lseek(fd, offset, SEEK_SET);
	if (write(fd, buffer, blocksize) != blocksize) {
		fprintf(stderr, "Write failed : file %s : block %d\n", filename, block);
		exit(1);
	}
}

/*
 * Verify a block contains the correct signature and sector numbers for
 * each sector within that block. We check every copy within the sector
 * and count how many were wrong.
 * 
 * buf must be at least blocksize
 */
int verify_block(int fd, unsigned int block, struct pattern *buffer, char *err)
{
	unsigned int sec_offset, sector;
	off_t offset;
	int i, errors = 0;
	struct pattern *sector_buffer;

	offset = block; offset *= blocksize;   // careful of overflow
	lseek(fd, offset, SEEK_SET);
	if (read(fd, buffer, blocksize) != blocksize) {
		fprintf(stderr, "read failed: block %d (errno: %d) filename %s %s\n", block, errno, filename, err);
		exit(1);
	}

	for (sec_offset = 0; sec_offset < sectors_per_block; sec_offset++) {
		unsigned int read_sector = 0, read_signature = 0;
		unsigned int sector_errors = 0, signature_errors = 0;

		sector = (block * sectors_per_block) + sec_offset;
		sector_buffer = &buffer[sec_offset * PATTERN_PER_SECTOR];

		for (i = 0; i < PATTERN_PER_SECTOR; i++) {
			if (sector_buffer[i].sector != sector) {
				read_sector = sector_buffer[i].sector;
				sector_errors++;
				errors++;
			}
			if (sector_buffer[i].signature != signature) {
				read_signature = sector_buffer[i].signature;
				signature_errors++;
				errors++;
			}
		}
		if (sector_errors)
			printf("Block %d (from %d to %d) sector %08x has wrong sector number %08x (%d/%d) filename %s %s\n",
					block, start_block, start_block+blocks,
					sector, read_sector,
					sector_errors, PATTERN_PER_SECTOR, 
					filename, err);
		if (signature_errors)
			printf("Block %d (from %d to %d) sector %08x signature is %08x should be %08x (%d/%d) filename %s %s\n", 
				block, start_block, start_block+blocks,
				sector, read_signature, signature, 
				signature_errors, PATTERN_PER_SECTOR, 
				filename, err);

	}
	return errors;
}

void write_file(unsigned int end_time, int random_access)
{
	int fd, pid;
	unsigned int block;
	void *buffer;

	fflush(stdout); fflush(stderr);
	pid = fork();

	if (pid < 0)
		die ("error forking child");
	if (pid != 0)			// parent
		return;

	fd = open(filename, O_RDWR, 0666);
	buffer = malloc(blocksize);

	if (random_access) {
		srandom(time(NULL) - getpid());
		while(time(NULL) < end_time) {
			block = start_block + (unsigned int)(random() % blocks);
			write_block(fd, block, buffer);
		}
	} else {
		while(time(NULL) < end_time)
			for (block = start_block; block < start_block + blocks; block++)
				write_block(fd, block, buffer);
	}
	free(buffer);
	exit(0);
}

void verify_file(unsigned int end_time, int random_access, int direct)
{
	int pid, error = 0;
	char err_msg[40];
	char *err = err_msg;
	fflush(stdout); fflush(stderr);
	pid = fork();

	if (pid < 0)
		die ("error forking child");
	if (pid != 0)			// parent
		return;

	int fd;
	unsigned int block;
	unsigned int align = (blocksize > 4096) ? blocksize : 4096;
	void *buffer = memalign(align, blocksize);

	if (direct) {
		fd = open(filename, O_RDONLY | O_DIRECT);
		strcpy(err, "direct");
		err += 6;
	} else {
		fd = open(filename, O_RDONLY);
		strcpy(err, "cached");
		err += 6;
	}	

	if (random_access) {
		strcpy(err, ",random");
		srandom(time(NULL) - getpid());
		while(time(NULL) < end_time) {
			block = start_block + (unsigned int)(random() % blocks);
			if (verify_block(fd, block, buffer, err_msg))
				error = 1;
		}
	} else {
		strcpy(err, ",linear");
		while(time(NULL) < end_time)
			for (block = start_block; block < start_block + blocks; block++)
				if (verify_block(fd, block, buffer, err_msg))
					error = 1;
	}
	free(buffer);
	exit(error);
}

void usage(void)
{
	printf("Usage: disktest\n");
	printf("    [-f filename]        filename to use     (testfile)\n");
	printf("    [-s seconds]         seconds to run for  (15)\n");
	printf("    [-m megabytes]       megabytes to use    (1)\n");
	printf("    [-M megabytes]       megabytes to skip   (0)\n");
	printf("    [-b blocksize]	 blocksize           (4096)\n");
	printf("    [-l linear tasks]    linear access tasks (4)\n");
	printf("    [-r random tasks]    random access tasks (4)\n");
	printf("    [-v]                 verify pre-existing file\n");
	printf("    [-i]                 only do init phase\n");
	printf("    [-S]                 stop immediately on error\n");
	printf("\n");
}

unsigned int double_verify(int fd, void *buffer, char *err)
{
	unsigned int block, errors = 0;

	for (block = start_block; block < start_block + blocks; block++) {
		if (verify_block(fd, block, buffer, err)) {
			if (stop_on_error)
				return 1;
			errors++;
		}
	}
	return errors;
}

int main(int argc, char *argv[])
{
	unsigned int block;
	time_t start_time, end_time;
	int tasks, opt, retcode, pid;
	void *init_buffer;

	/* Parse all input options */
	while ((opt = getopt(argc, argv, "vf:s:m:M:b:l:r:iS")) != -1) {
		switch (opt) {
			case 'v':
				verify_only = 1;
				break;
			case 'f':
				filename = optarg;
				break;
			case 's':
				seconds = atoi(optarg);
				break;
			case 'm':
				megabytes = atoi(optarg);
				break;
			case 'M':
				skip_mb = atoi(optarg);
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
			case 'i':
				init_only = 1;
				break;
			case 'S':
				stop_on_error = 1;
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
	start_block = skip_mb * (1024 * 1024 / blocksize);
	sectors_per_block = blocksize / SECTOR_SIZE;
	init_buffer = malloc(blocksize);

	if (verify_only) {
		struct stat stat_buf;

		printf("Verifying %s\n", filename);
		int fd = open(filename, O_RDONLY);
		if (fd < 0)
			die("open failed");

		if (fstat(fd, &stat_buf) != 0) 
			die("fstat failed");
		megabytes = stat_buf.st_size / (1024 * 1024);
		blocks = megabytes * (1024 * 1024 / blocksize);
		if (read(fd, init_buffer, SECTOR_SIZE) != SECTOR_SIZE) {
			fprintf(stderr, "read failed of initial sector (errno: %d) filename %s\n", errno, filename);
			exit(1);
		}
		lseek(fd, 0, SEEK_SET);
		signature = ((struct pattern *)init_buffer)->signature;

		printf("Checking %d megabytes using signature %08x\n", 
							megabytes, signature);
		if (double_verify(fd, init_buffer, "init1"))
			exit(1);
		else
			exit(0);
	}

	signature = (getpid() << 16) + ((unsigned int) time(NULL) & 0xffff);

	/* Initialise file */
	int fd = open(filename, O_RDWR | O_TRUNC | O_CREAT, 0666);
	if (fd < 0)
		die("open failed");

	start_time = time(NULL);

	printf("Ininitializing block %d to %d in file %s (signature %08x)\n", start_block, start_block+blocks, filename, signature);
	/* Initialise all file data to correct blocks */
	for (block = start_block; block < start_block+blocks; block++)
		write_block(fd, block, init_buffer);
	if(fsync(fd) != 0)
		die("fsync failed");
	if (double_verify(fd, init_buffer, "init1")) {
		if (!stop_on_error) {
			printf("First verify failed. Repeating for posterity\n");
			double_verify(fd, init_buffer, "init2");
		}
		exit(1);
	}

	printf("Wrote %d MB to %s (%d seconds)\n", megabytes, filename, (int) (time(NULL) - start_time));

	free(init_buffer);
	if (init_only)
		exit(0);
	
	end_time = time(NULL) + seconds;

	/* Fork off all linear access pattern tasks */
	for (tasks = 0; tasks < linear_tasks; tasks++)
		write_file(end_time, 0);

	/* Fork off all random access pattern tasks */
	for (tasks = 0; tasks < random_tasks; tasks++)
		write_file(end_time, 1);

	/* Verify in all four possible ways */
	verify_file(end_time, 0, 0);
	verify_file(end_time, 0, 1);
	verify_file(end_time, 1, 0);
	verify_file(end_time, 1, 1);

	for (tasks = 0; tasks < linear_tasks + random_tasks + 4; tasks++) {
		pid = wait(&retcode);
		if (retcode != 0) {
			printf("pid %d exited with status %d\n", pid, retcode);
			exit(1);
		}
	}
	return 0;
}
