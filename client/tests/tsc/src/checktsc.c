#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include <getopt.h>
#include <pthread.h>
#include <errno.h>
#include "sched.h"


#define MAX_CPUS		32
#define	DEFAULT_THRESHOLD	500	/* default maximum TSC skew	*/


char	*program;
long	threshold	= DEFAULT_THRESHOLD;
int	silent		= 0;
int	verbose		= 0;


struct option options[] = {
	{ "cpus",	required_argument,	0, 	'c'	},
	{ "help",	no_argument,		0, 	'h'	},
	{ "silent",	no_argument,		0, 	's'	},
	{ "threshold",	required_argument,	0, 	't'	},
	{ "verbose",	no_argument,		0, 	'v'	},
	{ 0,	0,	0,	0 }
};


void usage(void)
{
	printf("usage: %s [-hsv] [-c <cpu_set>] [-t threshold]\n", program);
}


void help(void)
{
	usage();
	printf("check TSC synchronization between CPUs\n");
	printf("  -c,--cpus        set of cpus to test (default: all)\n");
	printf("  -h,--help        show this message\n");
	printf("  -s,--silent      no output if test is successful\n");
	printf("  -t,--threshold   TSC skew threshold (default: %d cycles)\n",
		DEFAULT_THRESHOLD);
	printf("  -v,--verbose     verbose output\n");
}


void error(int err, const char *fmt, ...)
{
	va_list	ap;

	fprintf(stderr, "%s: ", program);
	va_start(ap, fmt);
	vfprintf(stderr, fmt, ap);
	va_end(ap);

	if (err)
		fprintf(stderr, ": %s\n", strerror(err));
	putc('\n', stderr);
}


/*
 * parse a string containing a comma separated list of ranges
 * of cpu numbers such as: "0,2,4-7" into a cpu_set_t
 */
int parse_cpu_set(const char *s, cpu_set_t *cpus)
{
	CPU_ZERO(cpus);

	while (*s) {
		char	*next;
		int	cpu;
		int	start, end;

		start = end = (int)strtol(s, &next, 0);
		if (s == next)
			break;
		s = next;

		if (*s == '-') {
			++s;
			end = (int)strtol(s, &next, 0);
			if (s == next)
				break;
			s = next;
		}

		if (*s == ',')
			++s;

		if (start < 0 || start >= CPU_SETSIZE) {
			error(0, "bad cpu number '%d' in cpu set", start);
			return 1;
		}

		if (end < 0 || end >= CPU_SETSIZE) {
			error(0, "bad cpu number '%d' in cpu set", end);
			return 1;
		}

		if (end < start) {
			error(0, "bad cpu range '%d-%d' in cpu set",
				start, end);
			return 1;
		}

		for (cpu = start; cpu <= end; ++cpu)
			CPU_SET(cpu, cpus);

	}

	if (*s) {
		error(0, "unexpected character '%c' in cpu set", *s);
		return 1;
	}

	return 0;
}


#define	CACHE_LINE_SIZE	256
typedef union state {
	int	state;
	char	pad[CACHE_LINE_SIZE];
} state_t;

#define barrier()	__asm__ __volatile__("" : : : "memory")

static void inline set_state(state_t *s, int v)
{
	s->state = v;
}

static void inline wait_for_state(state_t *s, int v)
{
	while (s->state != v)
		barrier();
}

#if defined(__x86_64__)
static inline uint64_t rdtsc(void)
{
	uint32_t	tsc_lo, tsc_hi;

	__asm__ __volatile__("rdtsc" : "=a" (tsc_lo), "=d" (tsc_hi));

	return ((uint64_t)tsc_hi << 32) | tsc_lo;
}
#else
static inline uint64_t rdtsc(void)
{
	uint64_t	tsc;

	__asm__ __volatile__("rdtsc" : "=A" (tsc));

	return tsc;
}
#endif

#define	READY	1
#define	DONE	2
#define	ERROR	3

state_t		master;
state_t		slave;

int64_t		slave_tsc;
int		slave_cpu;


int set_cpu_affinity(int cpu)
{
	cpu_set_t cpus;

	CPU_ZERO(&cpus);
	CPU_SET(cpu, &cpus);
	if (sched_setaffinity(0, sizeof cpus, &cpus) < 0) {
		error(errno, "sched_setaffinity() failed for CPU %d", cpu);
		return -1;
	}
	return 0;
}

#define NUM_ITERS	10

int64_t
tsc_delta(int cpu_a, int cpu_b)
{
	uint64_t	best_t0	= 0;
	uint64_t	best_t1	= ~0ULL;
	uint64_t	best_tm	= 0;
	int64_t		delta;
	uint64_t	t0, t1, tm;
	int		i;

	if (verbose)
		printf("CPU %d - CPU %d\n", cpu_a, cpu_b);

	if (set_cpu_affinity(cpu_a) < 0)
		return -1;

	slave_cpu = cpu_b;

	for (i = 0; i < NUM_ITERS; i++) {

		set_state(&master, READY);

		wait_for_state(&slave, READY);

		t0 = rdtsc();
		set_state(&master, DONE);
		wait_for_state(&slave, DONE);
		t1 = rdtsc();

		if ((t1 - t0) < (best_t1 - best_t0)) {
			best_t0 = t0;
			best_t1 = t1;
			best_tm = slave_tsc;
		}
		if (verbose)
			printf("loop %2d: roundtrip = %5Ld\n", i, t1 - t0);
	}

	delta = (best_t0/2 + best_t1/2 + (best_t0 & best_t1 & 1)) - best_tm; 

	if (!silent)
		printf("CPU %d - CPU %d = % 5Ld\n", cpu_a, cpu_b, delta);

	return delta;
}


void *
slave_thread(void *arg)
{
	int	current_cpu = -1;

	for(;;) {

		wait_for_state(&master, READY);

		if (slave_cpu < 0) {
			return NULL;
		}

		if (slave_cpu != current_cpu) {

			if (set_cpu_affinity(slave_cpu) < 0) {
				set_state(&slave, ERROR);
				return NULL;
			}

			current_cpu = slave_cpu;
		}

		set_state(&slave, READY);

		wait_for_state(&master, DONE);

		slave_tsc = rdtsc();

		set_state(&slave, DONE);
	}
	return NULL;
}


int
check_tsc(cpu_set_t *cpus)
{
	int		cpu_a, cpu_b;
	int64_t		delta;
	int		err	= 0;
	pthread_t	thread;

	if ((err = pthread_create(&thread, NULL, slave_thread, NULL))) {
		error(err, "pthread_create_failed");
		return -1;
	}
	

	for (cpu_a = 0; cpu_a < MAX_CPUS; cpu_a++) {
		if (!CPU_ISSET(cpu_a, cpus))
			continue;

		for (cpu_b = 0; cpu_b < MAX_CPUS; cpu_b++) {
			if (!CPU_ISSET(cpu_b, cpus) || cpu_a == cpu_b)
				continue;

			delta = tsc_delta(cpu_a, cpu_b);

			if (llabs(delta) > threshold) {
				++err;
			}
		}
	}

	/*
	 * tell the slave thread to exit
	 */
	slave_cpu = -1;
	set_state(&master, READY);

	pthread_join(thread, NULL);

	return err;
}


int
main(int argc, char *argv[])
{
	int		c;
	cpu_set_t	cpus;
	int		errs	= 0;
	extern int	optind;
	extern char	*optarg;

	if ((program = strrchr(argv[0], '/')) != NULL)
		++program;
	else
		program = argv[0];

	/*
	 * default to checking all cpus
	 */
	for (c = 0; c < MAX_CPUS; c++) {
		CPU_SET(c, &cpus);
	}

	while ((c = getopt_long(argc, argv, "c:hst:v", options, NULL)) != EOF) {
		switch (c) {
			case 'c':
				if (parse_cpu_set(optarg, &cpus) != 0)
					++errs;
				break;
			case 'h':
				help();
				exit(0);
			case 's':
				++silent;
				break;
			case 't':
				threshold = strtol(optarg, NULL, 0);
				break;
			case 'v':
				++verbose;
				break;
			default:
				++errs;
				break;
		}
	}

	if (errs || optind < argc) {
		usage();
		exit(1);
	}

	/*
	 * limit the set of CPUs to the ones that are currently available
	 * (Note that on some kernel versions sched_setaffinity() will fail
	 * if you specify CPUs that are not currently online so we ignore
	 * the return value and hope for the best)
	 */
	sched_setaffinity(0, sizeof cpus, &cpus);
	if (sched_getaffinity(0, sizeof cpus, &cpus) < 0) {
		error(errno, "sched_getaffinity() failed");
		exit(1);
	}

	errs = check_tsc(&cpus);

	if (!silent) {
		printf("%s\n", errs ? "FAIL" : "PASS");
	}

	return errs ? EXIT_FAILURE : EXIT_SUCCESS;
}
