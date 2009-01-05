/*
 * Copyright 2008 Google Inc. All Rights Reserved.
 * Author: md@google.com (Michael Davidson)
 */

#ifndef THREADS_H_
#define THREADS_H_

typedef void  *(*thread_func_t)(void *);

int create_threads(int num_threads, thread_func_t func, void *arg);
int create_per_cpu_threads(cpu_set_t *cpus, thread_func_t func, void *arg);
void join_threads(void);

#endif /* THREADS_H_ */
