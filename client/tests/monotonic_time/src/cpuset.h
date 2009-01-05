/*
 * Copyright 2008 Google Inc. All Rights Reserved.
 * Author: md@google.com (Michael Davidson)
 */

#ifndef CPUSET_H_
#define CPUSET_H_

#define _GNU_SOURCE	/* for cpu_set macros */

#include <sched.h>

int count_cpus(const cpu_set_t *cpus);
int parse_cpu_set(const char *s, cpu_set_t *cpus);
int show_cpu_set(char *buf, size_t len, const cpu_set_t *cpus);

#endif	/* CPUSET_H_ */
