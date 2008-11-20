#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>
#include <fcntl.h>

/* This program allocates memory with multiple calls to remap. This
 * can be used to verify if the remap api is working correctly. */

#define PAGE_SHIFT 12

#define ROUND_PAGES(memsize) ((memsize >> (PAGE_SHIFT)) << PAGE_SHIFT)

int main(int argc, char *argv[]) {
	unsigned int memsize;
	char *mem;
	int i, numpages, fd;

	if (argc != 2) {
		printf("Usage: %s <memory_size>\n", argv[0]);
		exit(EXIT_FAILURE);
	}

	memsize = strtoul(argv[1], NULL, 10);

	memsize = ROUND_PAGES(memsize);

	/* We should be limited to < 4G so any size other than 0 is ok */
	if (memsize == 0) {
		printf("Invalid memsize\n");
		exit(EXIT_FAILURE);
	}

	numpages = memsize >> PAGE_SHIFT;

	mem =  mmap(0, memsize, PROT_READ | PROT_WRITE,
			MAP_PRIVATE | MAP_ANONYMOUS,
			-1, 0);

	if (mem == (void*) -1) {
		perror("Failed to allocate anon private memory using mmap\n");
		exit(EXIT_FAILURE);
	}

	for (i = 2; i <= 16; i <<= 1) {
		mem = mremap(mem , memsize * (i >> 1),
					memsize * i,
					1 /* MREMAP_MAYMOVE */);

		if (mem == MAP_FAILED) {
			perror("Failed to remap expand anon private memory\n");
			exit(EXIT_FAILURE);
		}

		printf("Successfully remapped %d bytes @%p\n",
				memsize * i, mem);
	}

	if (munmap(mem, memsize * 16)) {
		perror("Could not unmap and free memory\n");
		exit(EXIT_FAILURE);
	}

	mem =  mmap(0, memsize, PROT_READ | PROT_WRITE,
			MAP_PRIVATE | MAP_ANONYMOUS,
			-1, 0);

	if (mem == (void*) -1) {
		perror("Failed to allocate anon private memory using mmap\n");
		exit(EXIT_FAILURE);
	}

	exit(EXIT_SUCCESS);
}
