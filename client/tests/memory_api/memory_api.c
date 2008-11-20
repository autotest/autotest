#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>
#include <fcntl.h>

/* This file includes a simple set of memory allocation calls that
 * a user space program can use to allocate/free or move memory mappings.
 * The intent of this program is to make it easier to verify if the kernel
 * internal mappings are correct.
 */

#define PAGE_SHIFT 12

#define ROUND_PAGES(memsize) ((memsize >> (PAGE_SHIFT)) << PAGE_SHIFT)

/* approximately half of memsize, page aligned */
#define HALF_MEM(memsize) ((memsize >> (PAGE_SHIFT))<<(PAGE_SHIFT - 1))

inline void waitnext() {
	fflush(NULL);
	getchar();
}

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

	mlockall(MCL_FUTURE);

	mem = sbrk(memsize);

	if (mem == (void*) -1) {
		perror("Failed to allocate memory using sbrk\n");
		exit(EXIT_FAILURE);
	}

	printf("Successfully allocated sbrk memory %d bytes @%p\n",
				memsize,  mem);

	waitnext();

	sbrk(-(memsize));

	mem =  mmap(0, memsize, PROT_READ | PROT_WRITE,
			MAP_PRIVATE| MAP_ANONYMOUS,
			-1, 0);

	if (mem == (void*) -1) {
		perror("Failed to allocate anon private memory using mmap\n");
		exit(EXIT_FAILURE);
	}

	printf("Successfully allocated anon mmap memory %d bytes @%p\n",
				memsize,  mem);

	waitnext();

	if (-1 == mprotect(mem, HALF_MEM(memsize), PROT_READ)) {
		perror("Failed to W protect memory using mprotect\n");
		exit(EXIT_FAILURE);
	}

	printf("Successfully write protected %d bytes @%p\n",
			HALF_MEM(memsize), mem);

	waitnext();

	if (-1 == mprotect(mem, HALF_MEM(memsize),
					 PROT_READ | PROT_WRITE)) {
		perror("Failed to RW protect memory using mprotect\n");
		exit(EXIT_FAILURE);
	}

	printf("Successfully cleared write protected %d bytes @%p\n",
			memsize, mem);
	waitnext();

	/* Mark all pages with a specific pattern */
	for (i = 0; i < numpages; i++) {
		int *ptr = (int *)(mem + i*4096);
		*ptr = i;
	}

	mem = mremap(mem , memsize,
				memsize + HALF_MEM(memsize),
				1 /* MREMAP_MAYMOVE */);

	if (mem == MAP_FAILED) {
		perror("Failed to remap expand anon private memory\n");
		exit(EXIT_FAILURE);
	}

	printf("Successfully remapped %d bytes @%p\n",
			memsize + HALF_MEM(memsize), mem);

	waitnext();

	/* Mark all pages with a specific pattern */
	for (i = 0; i < numpages; i++) {
		int value = *(int*)(mem + i*4096);
		if (value != i) {
			printf("remap error expected %d got %d\n",
					i, value);
			exit(EXIT_FAILURE);
		}
	}

	if (munmap(mem, memsize + HALF_MEM(memsize))) {
		perror("Could not unmap and free memory\n");
		exit(EXIT_FAILURE);
	}


	fd = open("/dev/zero", O_RDONLY);

	mem =  mmap(0, memsize, PROT_READ | PROT_WRITE,
			MAP_PRIVATE,
			fd, 0);

	if (mem == (void*) -1) {
		perror("Failed to allocate file backed memory using mmap\n");
		exit(EXIT_FAILURE);
	}

	printf("Successfully allocated file backed mmap memory %d bytes @%p\n",
					 memsize, mem);
	waitnext();

	if (munmap(mem, memsize)) {
		perror("Could not unmap and free file backed memory\n");
		exit(EXIT_FAILURE);
	}

	exit(EXIT_SUCCESS);
}
