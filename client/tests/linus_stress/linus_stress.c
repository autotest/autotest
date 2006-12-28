#include <sys/mman.h>
#include <sys/fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <time.h>

#define TARGETSIZE (100 << 20)
#define CHUNKSIZE (1460)
#define NRCHUNKS (TARGETSIZE / CHUNKSIZE)
#define SIZE (NRCHUNKS * CHUNKSIZE)

static void fillmem(void *start, int nr)
{
	memset(start, nr, CHUNKSIZE);
}

#define page_offset(buf, off) (0xfff & ((unsigned)(unsigned long)(buf)+(off)))

static int chunkorder[NRCHUNKS];

static int order(int nr)
{
	int i;
	if (nr < 0 || nr >= NRCHUNKS)
		return -1;
	for (i = 0; i < NRCHUNKS; i++)
		if (chunkorder[i] == nr)
			return i;
	return -2;
}

static void checkmem(void *buf, int nr)
{
	unsigned int start = ~0u, end = 0;
	unsigned char c = nr, *p = buf, differs = 0;
	int i;
	for (i = 0; i < CHUNKSIZE; i++) {
		unsigned char got = *p++;
		if (got != c) {
			if (i < start)
				start = i;
			if (i > end)
				end = i;
			differs = got;
		}
	}
	if (start < end) {
		printf("Chunk %d corrupted (%u-%u)  (%u-%u)            \n", nr, start, end,
			page_offset(buf, start), page_offset(buf, end));
		printf("Expected %u, got %u\n", c, differs);
		printf("Written as (%d)%d(%d)\n", order(nr-1), order(nr), order(nr+1));
	}
}

static char *remap(int fd, char *mapping)
{
	if (mapping) {
		munmap(mapping, SIZE);
		posix_fadvise(fd, 0, SIZE, POSIX_FADV_DONTNEED);
	}
	return mmap(NULL, SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
}

int main(int argc, char **argv)
{
	char *mapping;
	int fd, i;

	/*
	 * Make some random ordering of writing the chunks to the
	 * memory map..
	 *
	 * Start with fully ordered..
	 */
	for (i = 0; i < NRCHUNKS; i++)
		chunkorder[i] = i;

	/* ..and then mix it up randomly */
	srandom(time(NULL));
	for (i = 0; i < NRCHUNKS; i++) {
		int index = (unsigned int) random() % NRCHUNKS;
		int nr = chunkorder[index];
		chunkorder[index] = chunkorder[i];
		chunkorder[i] = nr;
	}

	fd = open("mapfile", O_RDWR | O_TRUNC | O_CREAT, 0666);
	if (fd < 0)
		return -1;
	if (ftruncate(fd, SIZE) < 0)
		return -1;
	mapping = remap(fd, NULL);
	if (-1 == (int)(long)mapping)
		return -1;

	for (i = 0; i < NRCHUNKS; i++) {
		int chunk = chunkorder[i];
		printf("Writing chunk %d/%d (%d%%)     \r", i, NRCHUNKS, 100*i/NRCHUNKS);
		fillmem(mapping + chunk * CHUNKSIZE, chunk);
	}
	printf("\n");

	/* Unmap, drop, and remap.. */
	mapping = remap(fd, mapping);

	/* .. and check */
	for (i = 0; i < NRCHUNKS; i++) {
		int chunk = i;
		printf("Checking chunk %d/%d (%d%%)     \r", i, NRCHUNKS, 100*i/NRCHUNKS);
		checkmem(mapping + chunk * CHUNKSIZE, chunk);
	}
	printf("\n");
	
	return 0;
}

