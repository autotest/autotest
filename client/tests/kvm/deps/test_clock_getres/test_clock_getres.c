/*
 *  Test clock resolution for KVM guests that have kvm-clock as clock source
 *
 *  Copyright (c) 2010 Red Hat, Inc
 *  Author: Lucas Meneghel Rodrigues <lmr@redhat.com>
 *
 *  This program is free software; you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation; either version 2 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program; if not, see <http://www.gnu.org/licenses/>.
 */
#include <stdio.h>
#include <time.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
	struct timespec res;
	int clock_return = clock_getres(CLOCK_MONOTONIC, &res);
	char clocksource[50];
	char line[80];
	FILE *fr;
	if ((fr = fopen(
			"/sys/devices/system/clocksource/clocksource0/current_clocksource",
			"rt")) == NULL) {
		perror("fopen");
		return EXIT_FAILURE;
	}
	while (fgets(line, 80, fr) != NULL) {
		sscanf(line, "%s", &clocksource);
	}
	fclose(fr);
	if (!strncmp(clocksource, "kvm-clock", strlen("kvm-clock"))) {
		if (clock_return == 0) {
			if (res.tv_sec > 1 || res.tv_nsec > 100) {
				printf("FAIL: clock_getres returned bad clock resolution\n");
				return EXIT_FAILURE;
			} else {
				printf("PASS: check successful\n");
				return EXIT_SUCCESS;
			}
		} else {
			printf("FAIL: clock_getres failed\n");
			return EXIT_FAILURE;
		}
	} else {
		printf("FAIL: invalid clock source: %s\n", clocksource);
		return EXIT_FAILURE;
	}
}
