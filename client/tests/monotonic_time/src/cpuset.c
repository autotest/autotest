/*
 * Copyright 2008 Google Inc. All Rights Reserved.
 * Author: md@google.com (Michael Davidson)
 */
#define _GNU_SOURCE	/* for cpu_set macros */

#include <sched.h>
#include <stdlib.h>
#include <stdio.h>
#include "cpuset.h"
#include "logging.h"

/*
 * Return the number of cpus in a cpu_set
 */
int count_cpus(const cpu_set_t *cpus)
{
	int	count	= 0;
	int	cpu;

	for (cpu = 0; cpu < CPU_SETSIZE; cpu++)
		if (CPU_ISSET(cpu, cpus))
			++count;

	return count;
}

/*
 * Parse a string containing a comma separated list of ranges
 * of cpu numbers such as: "0,2,4-7" into a cpu_set_t.
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
			ERROR(0, "bad cpu number '%d' in cpu set", start);
			return 1;
		}

		if (end < 0 || end >= CPU_SETSIZE) {
			ERROR(0, "bad cpu number '%d' in cpu set", end);
			return 1;
		}

		if (end < start) {
			ERROR(0, "bad range '%d-%d' in cpu set", start, end);
			return 1;
		}

		for (cpu = start; cpu <= end; ++cpu)
			CPU_SET(cpu, cpus);

	}

	if (*s) {
		ERROR(0, "unexpected character '%c' in cpu set", *s);
		return 1;
	}

	return 0;
}


static int show_range(char *buf, size_t len, const char *prefix,
			int start, int end)
{
	int	n;

	if (start == end)
		n = snprintf(buf, len, "%s%d", prefix, start);
	else
		n = snprintf(buf, len, "%s%d-%d", prefix, start, end);

	if (n < len)
		return n;

	return -1;
}

/*
 * Turn a cpu_set_t into a human readable string containing a
 * comma separated list of ranges of cpu numbers.
 *
 * Returns the number of bytes written to the buffer,
 * not including the terminating '\0' character,
 * or -1 if there was not enough space in the  buffer.
 */
int show_cpu_set(char *buf, size_t len, const cpu_set_t *cpus)
{
	char	*bufp	= buf;
	int	start	= -1;
	int	end	= -1;
	char	*sep	= "";
	int	cpu;

	for (cpu = 0; cpu < CPU_SETSIZE; cpu++) {
		if (CPU_ISSET(cpu, cpus)) {
			if (start < 0)
				start = cpu;
			end = cpu;
		} else if (start >= 0) {
			int	n;
			if ((n = show_range(bufp, len, sep, start, end)) < 0)
				return -1;
			len -= n;
			bufp += n;
			sep = ",";
			start = end = -1;
		}
	}

	if (start >= 0) {
		int	n;
		if ((n = show_range(bufp, len, sep, start, end)) < 0)
			return -1;
		bufp += n;
	}

	return bufp - buf;
}
