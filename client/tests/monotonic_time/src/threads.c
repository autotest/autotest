/*
 * Copyright 2008 Google Inc. All Rights Reserved.
 * Author: md@google.com (Michael Davidson)
 */
#define _GNU_SOURCE

#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <sched.h>
#include <pthread.h>

#include "logging.h"
#include "threads.h"

#define MAX_CPUS	CPU_SETSIZE
#define	MAX_THREADS	MAX_CPUS

typedef struct thread {
	pthread_t	thread;
	cpu_set_t	cpus;
	thread_func_t	func;
	void		*arg;
} thread_t;

static thread_t	threads[MAX_THREADS];
static int	num_threads;


/*
 * Helper function to run a thread on a specific set of CPUs.
 */
static void *run_thread(void *arg)
{
	thread_t	*thread = arg;
	void		*result;

	if (sched_setaffinity(0, sizeof thread->cpus, &thread->cpus) < 0)
		WARN(errno, "sched_setaffinity() failed");

	result = thread->func(thread->arg);

	return result;
}


/*
 * Create a set of threads each of which is bound to one of
 * the CPUs specified by cpus.
 * Returns the number of threads created.
 */
int create_per_cpu_threads(cpu_set_t *cpus, thread_func_t func, void *arg)
{
	int	cpu;

	for (cpu = 0; cpu < MAX_CPUS; cpu++) {
		int		err;
		thread_t	*thread;
		if (!CPU_ISSET(cpu, cpus))
			continue;
		if (num_threads >= MAX_THREADS)
			break;

		thread		= &threads[num_threads++];
		thread->func	= func;
		thread->arg	= arg;
		CPU_ZERO(&thread->cpus);
		CPU_SET(cpu, &thread->cpus);

		err = pthread_create(&thread->thread, NULL, run_thread, thread);
		if (err) {
			WARN(err, "pthread_create() failed");
			--num_threads;
			break;
		}
	}

	return num_threads;
}


/*
 * Create nthreads threads.
 * Returns the number of threads created.
 */
int create_threads(int nthreads, thread_func_t func, void *arg)
{
	if (nthreads > MAX_THREADS)
		nthreads = MAX_THREADS;

	while (--nthreads >= 0) {
		int		err;
		thread_t	*thread;

		thread		= &threads[num_threads++];
		thread->func	= func;
		thread->arg	= arg;
		CPU_ZERO(&thread->cpus);

		err = pthread_create(&thread->thread, NULL, func, arg);
		if (err) {
			WARN(err, "pthread_create() failed");
			--num_threads;
			break;
		}
	}

	return num_threads;
}


/*
 * Join with the set of previsouly created threads.
 */
void join_threads(void)
{
	while (num_threads > 0)
		pthread_join(threads[--num_threads].thread, NULL);
}

