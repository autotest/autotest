/*
 * Copyright 2008 Google Inc. All Rights Reserved.
 * Author: md@google.com (Michael Davidson)
 *
 * Based on time-warp-test.c, which is:
 * Copyright (C) 2005, Ingo Molnar
 */
#define _GNU_SOURCE

#include <errno.h>
#include <pthread.h>
#include <getopt.h>
#include <sched.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>

#include "cpuset.h"
#include "spinlock.h"
#include "threads.h"
#include "logging.h"


char	*program	= "";
long	duration	= 0;
long	threshold	= 0;
int	verbose		= 0;

const char optstring[] = "c:d:ht:v";

struct option options[] = {
	{ "cpus",	required_argument,	0, 	'c'	},
	{ "duration",	required_argument,	0,	'd'	},
	{ "help",	no_argument,		0, 	'h'	},
	{ "threshold",	required_argument,	0, 	't'	},
	{ "verbose",	no_argument,		0, 	'v'	},
	{ 0,	0,	0,	0 }
};


void usage(void)
{
	printf("usage: %s [-hv] [-c <cpu_set>] [-d duration] [-t threshold] "
		"tsc|gtod|clock", program);
}


const char help_text[] =
"check time sources for monotonicity across multiple CPUs\n"
"  -c,--cpus        set of cpus to test (default: all)\n"
"  -d,--duration    test duration in seconds (default: infinite)\n"
"  -t,--threshold   error threshold (default: 0)\n"
"  -v,--verbose     verbose output\n"
"  tsc              test the TSC\n"
"  gtod             test gettimeofday()\n"
"  clock            test CLOCK_MONOTONIC\n";


void help(void)
{
	usage();
	printf("%s", help_text);
}


/*
 * get the TSC as 64 bit value with CPU clock frequency resolution
 */
#if defined(__x86_64__)
static inline uint64_t rdtsc(void)
{
	uint32_t	tsc_lo, tsc_hi;
	__asm__ __volatile__("rdtsc" : "=a" (tsc_lo), "=d" (tsc_hi));
	return ((uint64_t)tsc_hi << 32) | tsc_lo;
}
#elif defined(__i386__)
static inline uint64_t rdtsc(void)
{
	uint64_t	tsc;
	__asm__ __volatile__("rdtsc" : "=A" (tsc));
	return tsc;
}
#else
#error "rdtsc() not implemented for this architecture"
#endif


static inline uint64_t rdtsc_mfence(void)
{
	__asm__ __volatile__("mfence" ::: "memory");
	return rdtsc();
}


static inline uint64_t rdtsc_lfence(void)
{
	__asm__ __volatile__("lfence" ::: "memory");
	return rdtsc();
}


/*
 * get result from gettimeofday() as a 64 bit value
 * with microsecond resolution
 */
static inline uint64_t rdgtod(void)
{
	struct timeval tv;

	gettimeofday(&tv, NULL);
	return (uint64_t)tv.tv_sec * 1000000 + tv.tv_usec;
}


/*
 * get result from clock_gettime(CLOCK_MONOTONIC) as a 64 bit value
 * with nanosecond resolution
 */
static inline uint64_t rdclock(void)
{
	struct timespec ts;

	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (uint64_t)ts.tv_sec * 1000000000 + ts.tv_nsec;
}


/*
 * test data
 */
typedef struct test_info {
	const char	*name;		/* test name			*/
	void		(*func)(struct test_info *);	/* the test	*/
	spinlock_t	lock;
	uint64_t	last;		/* last time value		*/
	long		loops;		/* # of test loop iterations	*/
	long		warps;		/* # of backward time jumps	*/
	int64_t		worst;		/* worst backward time jump	*/
	uint64_t	start;		/* test start time		*/
	int		done;		/* flag to stop test		*/
} test_info_t;


void show_warps(struct test_info *test)
{
	INFO("new %s-warp maximum: %9"PRId64, test->name, test->worst);
}


#define	DEFINE_TEST(_name)				\
							\
void _name##_test(struct test_info *test)		\
{							\
	uint64_t t0, t1;				\
	int64_t delta;					\
							\
	spin_lock(&test->lock);				\
	t1 = rd##_name();				\
	t0 = test->last;				\
	test->last = rd##_name();			\
	test->loops++;					\
	spin_unlock(&test->lock);			\
							\
	delta = t1 - t0;				\
	if (delta < 0 && delta < -threshold) {		\
		spin_lock(&test->lock);			\
		++test->warps;				\
		if (delta < test->worst) {		\
			test->worst = delta;		\
			show_warps(test);		\
		}					\
		spin_unlock(&test->lock);		\
	}						\
	if (!((unsigned long)t0 & 31))			\
		asm volatile ("rep; nop");		\
}							\
							\
struct test_info _name##_test_info = {			\
	.name = #_name,					\
	.func = _name##_test,				\
}

DEFINE_TEST(tsc);
DEFINE_TEST(tsc_lfence);
DEFINE_TEST(tsc_mfence);
DEFINE_TEST(gtod);
DEFINE_TEST(clock);

struct test_info *tests[] = {
	&tsc_test_info,
	&tsc_lfence_test_info,
	&tsc_mfence_test_info,
	&gtod_test_info,
	&clock_test_info,
	NULL
};


void show_progress(struct test_info *test)
{
	static int	count;
	const char	progress[] = "\\|/-";
	uint64_t	elapsed = rdgtod() - test->start;

        printf(" | %.2f us, %s-warps:%ld %c\r",
                        (double)elapsed/(double)test->loops,
			test->name,
                        test->warps,
			progress[++count & 3]);
	fflush(stdout);
}


void *test_loop(void *arg)
{
	struct test_info *test = arg;
	
	while (! test->done)
		(*test->func)(test);

	return NULL;
}


int run_test(cpu_set_t *cpus, long duration, struct test_info *test)
{
	int		errs;
	int		ncpus;
	int		nthreads;
	struct timespec ts		= { .tv_sec = 0, .tv_nsec = 200000000 };
	struct timespec	*timeout	= (verbose || duration) ? &ts : NULL;
	sigset_t	signals;

	/*
	 * Make sure that SIG_INT is blocked so we can
	 * wait for it in the main test loop below.
	 */
	sigemptyset(&signals);
	sigaddset(&signals, SIGINT);
	sigprocmask(SIG_BLOCK, &signals, NULL);

	/*
	 * test start time
	 */
	test->start = rdgtod();

	/*
 	 * create the threads
 	 */
	ncpus = count_cpus(cpus);
	nthreads = create_per_cpu_threads(cpus, test_loop, test);
	if (nthreads != ncpus) {
		ERROR(0, "failed to create threads: expected %d, got %d",
			ncpus, nthreads);
		if (nthreads) {
			test->done = 1;
			join_threads();
		}
		return 1;
	}

	if (duration) {
		INFO("running %s test on %d cpus for %ld seconds",
			 test->name, ncpus, duration);
	} else {
		INFO("running %s test on %d cpus", test->name, ncpus);
	}

	/*
 	 * wait for a signal
 	 */
	while (sigtimedwait(&signals, NULL, timeout) < 0) {
		if (duration  && rdgtod() > test->start + duration * 1000000)
			break;

		if (verbose)
			show_progress(test);
	}

	/*
	 * tell the test threads that we are done and wait for them to exit
	 */
	test->done = 1;

	join_threads();

	errs = (test->warps != 0);

	if (!errs)
		printf("PASS:\n");
	else
		printf("FAIL: %s-worst-warp=%"PRId64"\n",
			test->name, test->worst);
	
	return errs;
}


int
main(int argc, char *argv[])
{
	int		c;
	cpu_set_t	cpus;
	int		errs;
	int		i;
	test_info_t	*test;
	const char	*testname;
	extern int	opterr;
	extern int	optind;
	extern char	*optarg;

	if ((program = strrchr(argv[0], '/')) != NULL)
		++program;
	else
		program = argv[0];
	set_program_name(program);

	/*
	 * default to checking all cpus
	 */
	for (c = 0; c < CPU_SETSIZE; c++) {
		CPU_SET(c, &cpus);
	}

	opterr = 0;
	errs = 0;
	while ((c = getopt_long(argc, argv, optstring, options, NULL)) != EOF) {
		switch (c) {
			case 'c':
				if (parse_cpu_set(optarg, &cpus) != 0)
					++errs;
				break;
			case 'd':
				duration = strtol(optarg, NULL, 0);
				break;
			case 'h':
				help();
				exit(0);
			case 't':
				threshold = strtol(optarg, NULL, 0);
				break;
			case 'v':
				++verbose;
				break;
			default:
				ERROR(0, "unknown option '%c'", c);
				++errs;
				break;
		}
	}

	if (errs || optind != argc-1) {
		usage();
		exit(1);
	}

	testname = argv[optind];
	for (i = 0; (test = tests[i]) != NULL; i++) {
		if (strcmp(testname, test->name) == 0)
			break;
	}

	if (!test) {
		ERROR(0, "unknown test '%s'\n", testname);
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
		ERROR(errno, "sched_getaffinity() failed");
		exit(1);
	}

	return run_test(&cpus, duration, test);
}
