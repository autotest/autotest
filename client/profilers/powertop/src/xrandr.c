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

int has_no_xrandr;

static void activate_noTV(void)
{
	system("xrandr --auto &> /dev/null");
	system("xrandr --output TV --off &> /dev/null");
}

void suggest_xrandr_TV_off(void)
{
	FILE *file;
	int has_tv = 0;
	int has_tv_active = 0;
	char line[1024];

	if (has_no_xrandr)
		return;

	memset(line, 0, 1024);
	file = popen("xrandr 2> /dev/null", "r");
	if (!file || feof(file)) {
		has_no_xrandr = 1;
		return;
	}
	while (!feof(file)) {
		if (fgets(line, 1024, file)==NULL)
			break;
		if (line[0]!=' ') {
			if (line[0]=='T' && line[1]=='V' && line[2]==' ')
				has_tv = 1;
			else
				has_tv = 0;
		} else {
			if (strchr(line,'*') && has_tv)
				has_tv_active = 1;
		}
		
	}
	pclose(file);
	if (has_tv_active)
		add_suggestion(_("Suggestion: disable TV out via: \n"
				 "  xrandr --output TV --off \n"
				 "or press the V key."),
				35, 'V', _(" V - Disable TV out "), activate_noTV);	
	/* check this only once if no suggestion needed */
	else
		has_no_xrandr = 1;
}
