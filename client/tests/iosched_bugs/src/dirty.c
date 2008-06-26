// Author: Suleiman Souhlal (suleiman@google.com)

#include <stdio.h>
#include <err.h>
#include <stdint.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <fcntl.h>

#define O_NOATIME     01000000 

inline uint64_t
rdtsc(void)
{
	int64_t tsc;

	__asm __volatile("rdtsc" : "=A" (tsc));
	return (tsc);
}

int
main(int argc, char **argv)
{
	struct stat st;
	uint64_t e, s, t;
	char *p, q;
	long i;
	int fd;

	if (argc < 2) {
		printf("Usage: %s <file>\n", argv[0]);
		return (1);
	}

	if ((fd = open(argv[1], O_RDWR | O_NOATIME)) < 0)
		err(1, "open");

	if (fstat(fd, &st) < 0)
		err(1, "fstat");

	p = mmap(NULL, st.st_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);

	t = 0;
	for (i = 0; i < 1000; i++) {
		*p = 0;
		msync(p, 4096, MS_SYNC);
		s = rdtsc();
		*p = 0;
		__asm __volatile(""::: "memory");
		e = rdtsc();
		if (argc > 2)
			printf("%d: %lld cycles %jd %jd\n", i, e - s, (intmax_t)s, (intmax_t)e);
		t += e - s;
	}

	printf("average time: %lld cycles\n", t / 1000);

	return (0);
}
