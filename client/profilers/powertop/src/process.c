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
#include <sys/types.h>
#include <signal.h>

#include "powertop.h"

char process_to_kill[1024];

static void fancy_kill(void)
{
	FILE *file;
	char line[2048];
	char *tokill;
	int pid = 0;
	tokill = &process_to_kill[1];

	file = popen(" ps -A -o pid,command", "r");
	if (!file)
		return;
	while (!feof(file)) {
		memset(line, 0, 2048);
		if (fgets(line, 2047, file)==NULL)
			break;
		if (!strstr(line, tokill))
			continue;
		pid = strtoul(line, NULL, 10);
		
	}
	pclose(file);
	if (pid<2)
		return;
	kill(pid, SIGTERM);
}

void do_kill(void)
{
	char line[2048];

	if (process_to_kill[0] == '-') {
		fancy_kill();
	} else {
		sprintf(line, "killall %s &> /dev/null", process_to_kill);
		system(line);
	}
}

void suggest_process_death(char *process_match, char *tokill, struct line *slines, int linecount, double minwakeups, char *comment, int weight)
{
	int i;

	for (i = 0; i < linecount; i++) {
		if (slines[i].string && strstr(slines[i].string, process_match)) {
			char hotkey_string[300];
			sprintf(hotkey_string, _(" K - kill %s "), tokill);
			strcpy(process_to_kill, tokill);
			if (minwakeups < slines[i].count)
				add_suggestion(comment, weight, 'K' , hotkey_string, do_kill);
			break;
		}
	}
	fflush(stdout);
}
