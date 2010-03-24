/*
 * Copyright 2007, Intel Corporation
 *
 * This file is part of PowerTOP
 *
 * This program file is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation; version 2 of the License.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
 * for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program in a file named COPYING; if not, write to the
 * Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor,
 * Boston, MA 02110-1301 USA
 *
 * Authors:
 * 	Arjan van de Ven <arjan@linux.intel.com>
 */

#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sys/types.h>
#include <dirent.h>

#include "powertop.h"

struct cpufreqdata {
	uint64_t	frequency;
	uint64_t	count;
};

struct cpufreqdata freqs[16];
struct cpufreqdata oldfreqs[16];

struct cpufreqdata delta[16];

char cpufreqstrings[6][80];
int topfreq = -1;

static void zap(void)
{	
	memset(freqs, 0, sizeof(freqs));
}

int sort_by_count (const void *av, const void *bv)
{
        const struct cpufreqdata       *a = av, *b = bv;
        return b->count - a->count;
} 

int sort_by_freq (const void *av, const void *bv)
{
        const struct cpufreqdata       *a = av, *b = bv;
        return b->frequency - a->frequency;
} 

static char *HzToHuman(unsigned long hz)
{	
	static char buffer[1024];
	memset(buffer, 0, 1024);
	unsigned long long Hz;

	Hz = hz;

	/* default: just put the Number in */
	sprintf(buffer,_("%9lli"), Hz);

	if (Hz>1000)
		sprintf(buffer, _("%6lli Mhz"), (Hz+500)/1000);

	if (Hz>1500000)
		sprintf(buffer, _("%6.2f Ghz"), (Hz+5000.0)/1000000);


	return buffer;
}


void  do_cpufreq_stats(void)
{
	DIR *dir;
	struct dirent *dirent;
	FILE *file;
	char filename[PATH_MAX];
	char line[1024];

	int ret = 0;
	int maxfreq = 0;
	uint64_t total_time = 0;

	memcpy(&oldfreqs, &freqs, sizeof(freqs));
	memset(&cpufreqstrings, 0, sizeof(cpufreqstrings));
	sprintf(cpufreqstrings[0], _("P-states (frequencies)\n"));

	for (ret = 0; ret<16; ret++)
		freqs[ret].count = 0;

	dir = opendir("/sys/devices/system/cpu");
	if (!dir)
		return;

	while ((dirent = readdir(dir))) {
		int i;
		if (dirent->d_name[0]=='.')
			continue;
		sprintf(filename, "/sys/devices/system/cpu/%s/cpufreq/stats/time_in_state", dirent->d_name);
		file = fopen(filename, "r");
		if (!file)
			continue;
		memset(line, 0, 1024);

		i = 0;
		while (!feof(file)) {
			uint64_t f,count;
			char *c;
			if (fgets(line, 1023,file)==NULL)
				break;
			f = strtoull(line, &c, 10);
			if (!c)
				break;
			count = strtoull(c, NULL, 10);

			if (freqs[i].frequency && freqs[i].frequency != f) {
				zap();
				break;
			}

			freqs[i].frequency = f;
			freqs[i].count += count;

			if (f && maxfreq < i)
				maxfreq = i;
			i++;
			if (i>15)
				break;
		}
		fclose(file);
	}

	closedir(dir);

	for (ret = 0; ret < 16; ret++) {
		delta[ret].count = freqs[ret].count - oldfreqs[ret].count;
		total_time += delta[ret].count;
		delta[ret].frequency = freqs[ret].frequency;
		if (freqs[ret].frequency != oldfreqs[ret].frequency)
			return;  /* duff data */
	}


	if (!total_time)
		return;

	qsort(&delta, maxfreq+1, sizeof(struct cpufreqdata), sort_by_count);
	if (maxfreq>4)
		maxfreq=4;
	qsort(&delta, maxfreq+1, sizeof(struct cpufreqdata), sort_by_freq);

	topfreq = -1;
	for (ret = 0 ; ret<=maxfreq; ret++) {
		sprintf(cpufreqstrings[ret+1], "%6s   %5.1f%%\n", HzToHuman(delta[ret].frequency), delta[ret].count * 100.0 / total_time);
		if (delta[ret].count > total_time/2)
			topfreq = ret;
	}

}
