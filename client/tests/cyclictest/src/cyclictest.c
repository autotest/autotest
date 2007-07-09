/*
 * High resolution timer test software
 *
 * (C) 2005-2007 Thomas Gleixner <tglx@linutronix.de>
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License Version
 * 2 as published by the Free Software Foundation.
 *
 */

#define VERSION_STRING "V 0.15"

#include <fcntl.h>
#include <getopt.h>
#include <pthread.h>
#include <signal.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include <linux/unistd.h>

#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/time.h>

#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))

/* Ugly, but .... */
#define gettid() syscall(__NR_gettid)
#define sigev_notify_thread_id _sigev_un._tid

extern int clock_nanosleep(clockid_t __clock_id, int __flags,
			   __const struct timespec *__req,
			   struct timespec *__rem);

#define USEC_PER_SEC		1000000
#define NSEC_PER_SEC		1000000000

#define MODE_CYCLIC		0
#define MODE_CLOCK_NANOSLEEP	1
#define MODE_SYS_ITIMER		2
#define MODE_SYS_NANOSLEEP	3
#define MODE_SYS_OFFSET		2

#define TIMER_RELTIME		0

/* Must be power of 2 ! */
#define VALBUF_SIZE		16384

#define KVARS			32
#define KVARNAMELEN		32

/* Struct to transfer parameters to the thread */
struct thread_param {
	int prio;
	int mode;
	int timermode;
	int signal;
	int clock;
	unsigned long max_cycles;
	struct thread_stat *stats;
	int bufmsk;
	unsigned long interval;
};

/* Struct for statistics */
struct thread_stat {
	unsigned long cycles;
	unsigned long cyclesread;
	long min;
	long max;
	long act;
	double avg;
	long *values;
	pthread_t thread;
	int threadstarted;
	int tid;
};

static int shutdown;
static int tracelimit = 0;
static int ftrace = 0;
static int oldtrace = 0;

/* Backup of kernel variables that we modify */
static struct kvars {
	char name[KVARNAMELEN];
	int value;
} kv[KVARS];

static char *procfileprefix = "/proc/sys/kernel/";

static int kernvar(int mode, char *name, int *value)
{
	int retval = 1;
	int procfilepath;
	char procfilename[128];

	strncpy(procfilename, procfileprefix, sizeof(procfilename));
	strncat(procfilename, name,
		sizeof(procfilename) - sizeof(procfileprefix));
	procfilepath = open(procfilename, mode);
	if (procfilepath >= 0) {
		char buffer[32];

		if (mode == O_RDONLY) {
			if (read(procfilepath, buffer, sizeof(buffer)) > 0) {
				char *endptr;
				*value = strtol(buffer, &endptr, 0);
				if (endptr != buffer)
					retval = 0;
			}
		} else if (mode == O_WRONLY) {
			snprintf(buffer, sizeof(buffer), "%d\n", *value);
			if (write(procfilepath, buffer, strlen(buffer))
			    == strlen(buffer))
				retval = 0;
		}
		close(procfilepath);
	}
	return retval;
}

static void setkernvar(char *name, int value)
{
	int i;
	int oldvalue;

	if (kernvar(O_RDONLY, name, &oldvalue))
		fprintf(stderr, "could not retrieve %s\n", name);
	else {
		for (i = 0; i < KVARS; i++) {
			if (!strcmp(kv[i].name, name))
				break;
			if (kv[i].name[0] == '\0') {
				strncpy(kv[i].name, name, sizeof(kv[i].name));
				kv[i].value = oldvalue;
				break;
			}
		}
		if (i == KVARS)
			fprintf(stderr, "could not backup %s (%d)\n", name,
				oldvalue);
	}
	if (kernvar(O_WRONLY, name, &value))
		fprintf(stderr, "could not set %s to %d\n", name, value);
}

static void restorekernvars(void)
{
	int i;

	for (i = 0; i < KVARS; i++) {
		if (kv[i].name[0] != '\0') {
			if (kernvar(O_WRONLY, kv[i].name, &kv[i].value))
				fprintf(stderr, "could not restore %s to %d\n",
					kv[i].name, kv[i].value);
		}
	}
}

static inline void tsnorm(struct timespec *ts)
{
	while (ts->tv_nsec >= NSEC_PER_SEC) {
		ts->tv_nsec -= NSEC_PER_SEC;
		ts->tv_sec++;
	}
}

static inline long calcdiff(struct timespec t1, struct timespec t2)
{
	long diff;
	diff = USEC_PER_SEC * ((int) t1.tv_sec - (int) t2.tv_sec);
	diff += ((int) t1.tv_nsec - (int) t2.tv_nsec) / 1000;
	return diff;
}

/*
 * timer thread
 *
 * Modes:
 * - clock_nanosleep based
 * - cyclic timer based
 *
 * Clock:
 * - CLOCK_MONOTONIC
 * - CLOCK_REALTIME
 * - CLOCK_MONOTONIC_HR
 * - CLOCK_REALTIME_HR
 *
 */
void *timerthread(void *param)
{
	struct thread_param *par = param;
	struct sched_param schedp;
	struct sigevent sigev;
	sigset_t sigset;
	timer_t timer;
	struct timespec now, next, interval;
	struct itimerval itimer;
	struct itimerspec tspec;
	struct thread_stat *stat = par->stats;
	int policy = par->prio ? SCHED_FIFO : SCHED_OTHER;
	int stopped = 0;

	interval.tv_sec = par->interval / USEC_PER_SEC;
	interval.tv_nsec = (par->interval % USEC_PER_SEC) * 1000;

	if (tracelimit) {
		setkernvar("trace_all_cpus", 1);
		setkernvar("trace_freerunning", 1);
		setkernvar("trace_print_on_crash", 0);
		setkernvar("trace_user_triggered", 1);
		setkernvar("trace_user_trigger_irq", -1);
		setkernvar("trace_verbose", 0);
		setkernvar("preempt_thresh", 0);
		setkernvar("wakeup_timing", 0);
		setkernvar("preempt_max_latency", 0);
		if (ftrace)
			setkernvar("mcount_enabled", 1);
		setkernvar("trace_enabled", 1);
	}

	stat->tid = gettid();

	sigemptyset(&sigset);
	sigaddset(&sigset, par->signal);
	sigprocmask(SIG_BLOCK, &sigset, NULL);

	if (par->mode == MODE_CYCLIC) {
		sigev.sigev_notify = SIGEV_THREAD_ID | SIGEV_SIGNAL;
		sigev.sigev_signo = par->signal;
		sigev.sigev_notify_thread_id = stat->tid;
		timer_create(par->clock, &sigev, &timer);
		tspec.it_interval = interval;
	}

	memset(&schedp, 0, sizeof(schedp));
	schedp.sched_priority = par->prio;
	sched_setscheduler(0, policy, &schedp);

	/* Get current time */
	clock_gettime(par->clock, &now);
	next = now;
	next.tv_sec++;

	if (par->mode == MODE_CYCLIC) {
		if (par->timermode == TIMER_ABSTIME)
			tspec.it_value = next;
		else {
			tspec.it_value.tv_nsec = 0;
			tspec.it_value.tv_sec = 1;
		}
		timer_settime(timer, par->timermode, &tspec, NULL);
	}

	if (par->mode == MODE_SYS_ITIMER) {
		itimer.it_value.tv_sec = 1;
		itimer.it_value.tv_usec = 0;
		itimer.it_interval.tv_sec = interval.tv_sec;
		itimer.it_interval.tv_usec = interval.tv_nsec / 1000;
		setitimer (ITIMER_REAL,  &itimer, NULL);
	}

	stat->threadstarted++;

	if (tracelimit) {
		if (oldtrace)
			gettimeofday(0,(struct timezone *)1);
		else
			prctl(0, 1);
	}
	while (!shutdown) {

		long diff;
		int sigs;

		/* Wait for next period */
		switch (par->mode) {
		case MODE_CYCLIC:
		case MODE_SYS_ITIMER:
			if (sigwait(&sigset, &sigs) < 0)
				goto out;
			break;

		case MODE_CLOCK_NANOSLEEP:
			if (par->timermode == TIMER_ABSTIME)
				clock_nanosleep(par->clock, TIMER_ABSTIME,
						&next, NULL);
			else {
				clock_gettime(par->clock, &now);
				clock_nanosleep(par->clock, TIMER_RELTIME,
						&interval, NULL);
				next.tv_sec = now.tv_sec + interval.tv_sec;
				next.tv_nsec = now.tv_nsec + interval.tv_nsec;
				tsnorm(&next);
			}
			break;

		case MODE_SYS_NANOSLEEP:
			clock_gettime(par->clock, &now);
			nanosleep(&interval, NULL);
			next.tv_sec = now.tv_sec + interval.tv_sec;
			next.tv_nsec = now.tv_nsec + interval.tv_nsec;
			tsnorm(&next);
			break;
		}
		clock_gettime(par->clock, &now);

		diff = calcdiff(now, next);
		if (diff < stat->min)
			stat->min = diff;
		if (diff > stat->max)
			stat->max = diff;
		stat->avg += (double) diff;

		if (!stopped && tracelimit && (diff > tracelimit)) {
			stopped++;
			if (oldtrace)
				gettimeofday(0,0);
			else
				prctl(0, 0);
			shutdown++;
		}
		stat->act = diff;
		stat->cycles++;

		if (par->bufmsk)
			stat->values[stat->cycles & par->bufmsk] = diff;

		next.tv_sec += interval.tv_sec;
		next.tv_nsec += interval.tv_nsec;
		tsnorm(&next);

		if (par->max_cycles && par->max_cycles == stat->cycles)
			break;
	}

out:
	if (par->mode == MODE_CYCLIC)
		timer_delete(timer);

	if (par->mode == MODE_SYS_ITIMER) {
		itimer.it_value.tv_sec = 0;
		itimer.it_value.tv_usec = 0;
		itimer.it_interval.tv_sec = 0;
		itimer.it_interval.tv_usec = 0;
		setitimer (ITIMER_REAL,  &itimer, NULL);
	}

	/* switch to normal */
	schedp.sched_priority = 0;
	sched_setscheduler(0, SCHED_OTHER, &schedp);

	stat->threadstarted = -1;

	return NULL;
}


/* Print usage information */
static void display_help(void)
{
	printf("cyclictest %s\n", VERSION_STRING);
	printf("Usage:\n"
	       "cyclictest <options>\n\n"
	       "-b USEC  --breaktrace=USEC send break trace command when latency > USEC\n"
	       "-c CLOCK --clock=CLOCK     select clock\n"
	       "                           0 = CLOCK_MONOTONIC (default)\n"
	       "                           1 = CLOCK_REALTIME\n"
	       "-d DIST  --distance=DIST   distance of thread intervals in us default=500\n"
	       "-f                         function trace (when -b is active)\n"
	       "-i INTV  --interval=INTV   base interval of thread in us default=1000\n"
	       "-l LOOPS --loops=LOOPS     number of loops: default=0(endless)\n"
	       "-n       --nanosleep       use clock_nanosleep\n"
	       "-p PRIO  --prio=PRIO       priority of highest prio thread\n"
	       "-q       --quiet           print only a summary on exit\n"
	       "-r       --relative        use relative timer instead of absolute\n"
	       "-s       --system          use sys_nanosleep and sys_setitimer\n"
	       "-t NUM   --threads=NUM     number of threads: default=1\n"
	       "-v       --verbose         output values on stdout for statistics\n"
	       "                           format: n:c:v n=tasknum c=count v=value in us\n");
	exit(0);
}

static int use_nanosleep;
static int timermode  = TIMER_ABSTIME;
static int use_system;
static int priority;
static int num_threads = 1;
static int max_cycles;
static int clocksel = 0;
static int verbose;
static int quiet;
static int interval = 1000;
static int distance = 500;

static int clocksources[] = {
	CLOCK_MONOTONIC,
	CLOCK_REALTIME,
};

/* Process commandline options */
static void process_options (int argc, char *argv[])
{
	int error = 0;
	for (;;) {
		int option_index = 0;
		/** Options for getopt */
		static struct option long_options[] = {
			{"breaktrace", required_argument, NULL, 'b'},
			{"clock", required_argument, NULL, 'c'},
			{"distance", required_argument, NULL, 'd'},
			{"ftrace", no_argument, NULL, 'f'},
			{"interval", required_argument, NULL, 'i'},
			{"loops", required_argument, NULL, 'l'},
			{"nanosleep", no_argument, NULL, 'n'},
			{"priority", required_argument, NULL, 'p'},
			{"quiet", no_argument, NULL, 'q'},
			{"relative", no_argument, NULL, 'r'},
			{"system", no_argument, NULL, 's'},
			{"threads", required_argument, NULL, 't'},
			{"verbose", no_argument, NULL, 'v'},
			{"help", no_argument, NULL, '?'},
			{NULL, 0, NULL, 0}
		};
		int c = getopt_long (argc, argv, "b:c:d:fi:l:np:qrst:v",
			long_options, &option_index);
		if (c == -1)
			break;
		switch (c) {
		case 'b': tracelimit = atoi(optarg); break;
		case 'c': clocksel = atoi(optarg); break;
		case 'd': distance = atoi(optarg); break;
		case 'f': ftrace = 1; break;
		case 'i': interval = atoi(optarg); break;
		case 'l': max_cycles = atoi(optarg); break;
		case 'n': use_nanosleep = MODE_CLOCK_NANOSLEEP; break;
		case 'p': priority = atoi(optarg); break;
		case 'q': quiet = 1; break;
		case 'r': timermode = TIMER_RELTIME; break;
		case 's': use_system = MODE_SYS_OFFSET; break;
		case 't': num_threads = atoi(optarg); break;
		case 'v': verbose = 1; break;
		case '?': error = 1; break;
		}
	}

	if (clocksel < 0 || clocksel > ARRAY_SIZE(clocksources))
		error = 1;

	if (priority < 0 || priority > 99)
		error = 1;

	if (num_threads < 1)
		error = 1;

	if (error)
		display_help ();
}

static void check_kernel(void)
{
	size_t len;
	char ver[256];
	int fd, maj, min, sub;

	fd = open("/proc/version", O_RDONLY, 0666);
	len = read(fd, ver, 255);
	close(fd);
	ver[len-1] = 0x0;
	sscanf(ver, "Linux version %d.%d.%d", &maj, &min, &sub);
	if (maj == 2 && min == 6 && sub < 18)
		oldtrace = 1;
}

static int check_timer(void)
{
	struct timespec ts;

	if (clock_getres(CLOCK_MONOTONIC, &ts))
		return 1;

	return (ts.tv_sec != 0 || ts.tv_nsec != 1);
}

static void sighand(int sig)
{
	shutdown = 1;
}

static void print_stat(struct thread_param *par, int index, int verbose)
{
	struct thread_stat *stat = par->stats;

	if (!verbose) {
		if (quiet != 1) {
			printf("T:%2d (%5d) P:%2d I:%ld C:%7lu "
			       "Min:%7ld Act:%5ld Avg:%5ld Max:%8ld\n",
			       index, stat->tid, par->prio, par->interval,
			       stat->cycles, stat->min, stat->act,
			       stat->cycles ?
			       (long)(stat->avg/stat->cycles) : 0, stat->max);
		}
	} else {
		while (stat->cycles != stat->cyclesread) {
			long diff = stat->values[stat->cyclesread & par->bufmsk];
			printf("%8d:%8lu:%8ld\n", index, stat->cyclesread, diff);
			stat->cyclesread++;
		}
	}
}

int main(int argc, char **argv)
{
	sigset_t sigset;
	int signum = SIGALRM;
	int mode;
	struct thread_param *par;
	struct thread_stat *stat;
	int i, ret = -1;

	if (geteuid()) {
		fprintf(stderr, "cyclictest: need to run as root!\n");
		exit(-1);
	}

	process_options(argc, argv);

	check_kernel();

	if (check_timer())
		fprintf(stderr, "WARNING: High resolution timers not available\n");

	mode = use_nanosleep + use_system;

	sigemptyset(&sigset);
	sigaddset(&sigset, signum);
	sigprocmask (SIG_BLOCK, &sigset, NULL);

	signal(SIGINT, sighand);
	signal(SIGTERM, sighand);

	par = calloc(num_threads, sizeof(struct thread_param));
	if (!par)
		goto out;
	stat = calloc(num_threads, sizeof(struct thread_stat));
	if (!stat)
		goto outpar;

	for (i = 0; i < num_threads; i++) {
		if (verbose) {
			stat[i].values = calloc(VALBUF_SIZE, sizeof(long));
			if (!stat[i].values)
				goto outall;
			par[i].bufmsk = VALBUF_SIZE - 1;
		}

		par[i].prio = priority;
		if (priority)
			priority--;
		par[i].clock = clocksources[clocksel];
		par[i].mode = mode;
		par[i].timermode = timermode;
		par[i].signal = signum;
		par[i].interval = interval;
		interval += distance;
		par[i].max_cycles = max_cycles;
		par[i].stats = &stat[i];
		stat[i].min = 1000000;
		stat[i].max = -1000000;
		stat[i].avg = 0.0;
		pthread_create(&stat[i].thread, NULL, timerthread, &par[i]);
		stat[i].threadstarted = 1;
	}

	while (!shutdown) {
		char lavg[256];
		int fd, len, allstopped = 0;

		if (!verbose && !quiet) {
			fd = open("/proc/loadavg", O_RDONLY, 0666);
			len = read(fd, &lavg, 255);
			close(fd);
			lavg[len-1] = 0x0;
			printf("%s          \n\n", lavg);
		}

		for (i = 0; i < num_threads; i++) {

			print_stat(&par[i], i, verbose);
			if(max_cycles && stat[i].cycles >= max_cycles)
				allstopped++;
		}
		usleep(10000);
		if (shutdown || allstopped)
			break;
		if (!verbose && !quiet)
			printf("\033[%dA", num_threads + 2);
	}
	ret = 0;
 outall:
	shutdown = 1;
	usleep(50000);
	if (quiet)
		quiet = 2;
	for (i = 0; i < num_threads; i++) {
		if (stat[i].threadstarted > 0)
			pthread_kill(stat[i].thread, SIGTERM);
		if (stat[i].threadstarted) {
			pthread_join(stat[i].thread, NULL);
			if (quiet)
				print_stat(&par[i], i, 0);
		}
		if (stat[i].values)
			free(stat[i].values);
	}
	free(stat);
 outpar:
	free(par);
 out:
	/* Be a nice program, cleanup */
	restorekernvars();

	exit(ret);
}
