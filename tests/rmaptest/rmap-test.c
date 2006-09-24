/*
 * Create lots of VMA's mapped by lots of tasks.  To tickle objrmap and the
 * virtual scan.
 */

#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <time.h>
#include <sys/mman.h>
#include <sys/signal.h>
#include <sys/stat.h>
#include <sys/wait.h>

char *progname;
char *filename;
void *mapped_mem;

int niters;
int ntasks = 100;
int nvmas = 100;
int vmasize = 1024*1024;
int vmas_to_do = -1;
int pagesize;
int fd;
char **vma_addresses;
volatile int *nr_children_running;
int verbose;

enum access_pattern {
	ap_random,
	ap_linear,
	ap_half
} access_pattern = ap_linear;

void open_file()
{
	fd = open(filename, O_RDWR|O_TRUNC|O_CREAT, 0666);
	if (fd < 0) {
		fprintf(stderr, "%s: Cannot open `%s': %s\n",
			progname, filename, strerror(errno));
		exit(1);
	}
}

void usage(void)
{
	fprintf(stderr, "Usage: %s [-hlrvV] [-iN] [-nN] [-sN] [-tN] filename\n",
				progname);
	fprintf(stderr, "     -h:          Pattern: half of memory is busy\n");
	fprintf(stderr, "     -l:          Pattern: linear\n");
	fprintf(stderr, "     -r:          Pattern: random\n");
	fprintf(stderr, "     -iN:         Number of iterations\n");
	fprintf(stderr, "     -nN:         Number of VMAs\n");
	fprintf(stderr, "     -sN:         VMA size (pages)\n");
	fprintf(stderr, "     -tN:         Run N tasks\n");
	fprintf(stderr, "     -VN:         Number of VMAs to process\n");
	fprintf(stderr, "     -v:          Verbose\n");
	exit(1);
}

void touch_pages(int nr_vmas)
{
	int i;

	for (i = 0; i < nr_vmas; i++) {
		char *p = vma_addresses[i];
		int page;

		for (page = 0; page < vmasize; page++)
			p[page * pagesize]++;
	}
}

void msync_file(int nr_vmas)
{
	int i;

	for (i = 0; i < nr_vmas; i++) {
		char *p = vma_addresses[i];

		msync(p, vmasize * pagesize, MS_ASYNC);
	}
}

void touch_random_pages(void)
{
	int vma;
	int page;

	srand(getpid() * time(0));

	for (vma = 0; vma < vmas_to_do; vma++) {
		for (page = 0; page < vmasize; page++) {
			int rand_vma;
			int rand_page;
			char *p;

			rand_vma = rand() % nvmas;
			rand_page = rand() % vmasize;
			p = vma_addresses[rand_vma] + rand_page * pagesize;
			(*p)++;
		}
		if (verbose > 1)
			printf("vma %d/%d done\n", vma, nvmas);
	}
}

void child(int childno)
{
	int iter;

	sleep(1);
	if (access_pattern == ap_half && childno == 0) {
		while (*nr_children_running > 1) {
			touch_pages(nvmas / 2);
		}
		return;
	}

	for (iter = 0; iter < niters; iter++) {
		if (access_pattern == ap_random) {
			touch_random_pages();
		} else if (access_pattern == ap_linear) {
			touch_pages(nvmas);
		} else if (access_pattern == ap_half) {
			touch_pages(nvmas);
		}
		if (verbose > 0)
			printf("%d/%d\n", iter, niters);
	}
}

int main(int argc, char *argv[])
{
	int c;
	int i;
	loff_t offset;
	loff_t file_size;
	int childno;

	progname = argv[0];

	while ((c = getopt(argc, argv, "vrlhi:n:s:t:V:")) != -1) {
		switch (c) {
		case 'h':
			access_pattern = ap_half;
			break;
		case 'l':
			access_pattern = ap_linear;
			break;
		case 'r':
			access_pattern = ap_random;
			break;
		case 'i':
			niters = strtol(optarg, NULL, 10);
			break;
		case 'n':
			nvmas = strtol(optarg, NULL, 10);
			break;
		case 's':
			vmasize = strtol(optarg, NULL, 10);
			break;
		case 't':
			ntasks = strtol(optarg, NULL, 10);
			break;
		case 'V':
			vmas_to_do = strtol(optarg, NULL, 10);
			break;
		case 'v':
			verbose++;
			break;
		}
	}

	if (optind == argc)
		usage();
	filename = argv[optind++];
	if (optind != argc)
		usage();

	if (vmas_to_do == -1)
		vmas_to_do = nvmas;

	pagesize = getpagesize();
	open_file();

	file_size = nvmas;
	file_size *= vmasize;
	file_size += nvmas - 1;
	file_size *= pagesize;

	printf("Total file size: %lldk, Total memory: %lldk\n",
		file_size / 1024,
		((long long)nvmas * vmasize * pagesize) / 1024);

	if (ftruncate(fd, file_size) < 0) {
		perror("ftruncate");
		exit(1);
	}

	vma_addresses = malloc(nvmas * sizeof(*vma_addresses));
	nr_children_running = (int *)mmap(0, sizeof(*nr_children_running),
				PROT_READ|PROT_WRITE,
				MAP_SHARED|MAP_ANONYMOUS,
				-1,
				0);
	if (nr_children_running == MAP_FAILED) {
		perror("mmap1");
		exit(1);
	}

	offset = 0;

	for (i = 0; i < nvmas; i++) {
		char *p;

		p = mmap(0, vmasize * pagesize, PROT_READ|PROT_WRITE,
				MAP_SHARED, fd, offset);
		if (p == MAP_FAILED) {
			perror("mmap");
			exit(1);
		}
		vma_addresses[i] = p;
		offset += vmasize * pagesize + pagesize;
	}

	touch_pages(nvmas);
	msync_file(nvmas);
	*nr_children_running = ntasks;

	for (childno = 0; childno < ntasks; childno++) {
		if (fork() == 0) {
			child(childno);
			exit(0);
		}
	}

	signal(SIGINT, SIG_IGN);

	for (i = 0; i < ntasks; i++) {
		pid_t pid;
		int status;
		
		/* Catch each child error status and report. */
		pid = wait3(&status, 0, 0);
		if (pid < 0)	/* No more children? */
			break;
		(*nr_children_running)--;
	}
	exit(0);
}
