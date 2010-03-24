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

int alpm_activated;

static void activate_alpm(void)
{
	DIR *dir;
	struct dirent *dirent;
	FILE *file;
	char filename[PATH_MAX];

	dir = opendir("/sys/class/scsi_host");
	if (!dir)
		return;

	while ((dirent = readdir(dir))) {
		if (dirent->d_name[0]=='.')
			continue;
		sprintf(filename, "/sys/class/scsi_host/%s/link_power_management_policy", dirent->d_name);
		file = fopen(filename, "w");
		if (!file)
			continue;
		fprintf(file, "min_power\n");
		fclose(file);
	}

	closedir(dir);
	alpm_activated = 1;
}

void suggest_sata_alpm(void)
{
	DIR *dir;
	struct dirent *dirent;
	FILE *file;
	char filename[PATH_MAX];
	char line[1024];
	int need_hint  = 0;

	if (alpm_activated)
		return;


	dir = opendir("/sys/class/scsi_host/");
	if (!dir)
		return;

	while ((dirent = readdir(dir))) {
		if (dirent->d_name[0]=='.')
			continue;
		sprintf(filename, "/sys/class/scsi_host/%s/link_power_management_policy", dirent->d_name);
		file = fopen(filename, "r");
		if (!file)
			continue;
		memset(line, 0, 1024);
		if (fgets(line, 1023,file)==NULL) {
			fclose(file);
			continue;
		}
		if (!strstr(line, "min_power"))
			need_hint = 1;

		fclose(file);
	}

	closedir(dir);

	if (need_hint) {
		add_suggestion(_("Suggestion: Enable SATA ALPM link power management via: \n"
				 "  echo min_power > /sys/class/scsi_host/host0/link_power_management_policy\n"
				 "or press the S key."),
				15, 'S', _(" S - SATA Link Power Management "), activate_alpm);
	}
}
