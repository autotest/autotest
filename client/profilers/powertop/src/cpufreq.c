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

static void activate_ondemand(void)
{
	DIR *dir;
	struct dirent *dirent;
	FILE *file;
	char filename[PATH_MAX];

	system("/sbin/modprobe cpufreq_ondemand &> /dev/null");


	dir = opendir("/sys/devices/system/cpu");
	if (!dir)
		return;

	while ((dirent = readdir(dir))) {
		if (dirent->d_name[0]=='.')
			continue;
		sprintf(filename, "/sys/devices/system/cpu/%s/cpufreq/scaling_governor", dirent->d_name);
		file = fopen(filename, "w");
		if (!file)
			continue;
		fprintf(file, "ondemand\n");
		fclose(file);
	}

	closedir(dir);
}

void suggest_ondemand_governor(void)
{
	DIR *dir;
	struct dirent *dirent;
	FILE *file;
	char filename[PATH_MAX];
	char line[1024];

	char gov[1024];
	int ret = 0;


	gov[0] = 0;


	dir = opendir("/sys/devices/system/cpu");
	if (!dir)
		return;

	while ((dirent = readdir(dir))) {
		if (dirent->d_name[0]=='.')
			continue;
		sprintf(filename, "/sys/devices/system/cpu/%s/cpufreq/scaling_governor", dirent->d_name);
		file = fopen(filename, "r");
		if (!file)
			continue;
		memset(line, 0, 1024);
		if (fgets(line, 1023,file)==NULL) {
			fclose(file);
			continue;
		}
		if (strlen(gov)==0)
			strcpy(gov, line);
		else
			/* if the governors are inconsistent, warn */
			if (strcmp(gov, line))
				ret = 1;
		fclose(file);
	}

	closedir(dir);

	/* if the governor is set to userspace, also warn */
	if (strstr(gov, "userspace"))
		ret = 1;

	/* if the governor is set to performance, also warn */
	/* FIXME: check if this is fair on all cpus */
	if (strstr(gov, "performance"))
		ret = 1;


	if (ret) {
		add_suggestion(_("Suggestion: Enable the ondemand cpu speed governor for all processors via: \n"
				 " echo ondemand > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor \n"),
				15, 'O', _(" O - enable Ondemand governor "), activate_ondemand);
	}
}
