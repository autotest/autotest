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

/* static arrays are not nice programming.. but they're easy */
static char configlines[5000][100];
static int configcount;

static void read_kernel_config(void)
{
	FILE *file;
	char version[100], *c;
	char filename[100];
	if (configcount)
		return;
	if (access("/proc/config.gz", R_OK) == 0) {
		file = popen("zcat /proc/config.gz 2> /dev/null", "r");
		while (file && !feof(file)) {
			char line[100];
			if (fgets(line, 100, file) == NULL)
				break;
			strcpy(configlines[configcount++], line);
		}
		pclose(file);
		return;
	}
	file = fopen("/proc/sys/kernel/osrelease", "r");
	if (!file)
		return;
	if (fgets(version, 100, file) == NULL) {
		fclose(file);
		return;
	}
	fclose(file);
	c = strchr(version, '\n');
	if (c)
		*c = 0;
	sprintf(filename, "/boot/config-%s", version);
	file = fopen(filename, "r");
	if (!file) {
		sprintf(filename, "/lib/modules/%s/build/.config", version);
		file = fopen(filename, "r");
	}
	if (!file)
		return;
	while (!feof(file)) {
		char line[100];
		if (fgets(line, 100, file) == NULL)
			break;
		strcpy(configlines[configcount++], line);
	}
	fclose(file);
}

/*
 * Suggest the user to turn on/off a kernel config option.
 * "comment" gets displayed if it's not already set to the right value 
 */
void suggest_kernel_config(char *string, int onoff, char *comment, int weight)
{
	int i;
	char searchon[100];
	char searchoff[100];
	int found = 0;

	read_kernel_config();

	sprintf(searchon, "%s=", string);
	sprintf(searchoff, "# %s is not set", string);

	for (i = 0; i < configcount; i++) {
		if (onoff && strstr(configlines[i], searchon))
			return;
		if (onoff==0 && strstr(configlines[i], searchoff))
			return;
		if (onoff==0 && strstr(configlines[i], searchon))
			found = 1;
	}
	if (onoff || found)
		add_suggestion(comment, weight, 0, NULL, NULL);
	fflush(stdout);
}
