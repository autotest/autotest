/*
 * Copyright 2008, Intel Corporation
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
#include <ctype.h>

#include "powertop.h"

#ifdef __i386


/*
 * Perform a CPU ID operation; with various registers set
 */
static void cpuid(      unsigned int *eax,
                        unsigned int *ebx,
                        unsigned int *ecx,
                        unsigned int *edx)
{
	/* call the cpuid instruction with the registers as input and output
	 * modification by Dwokfur based on Sam Hocevar's discussion on
	 * how to make Assemly code PIC compatible:
	 * http://sam.zoy.org/blog/2007-04-13-shlib-with-non-pic-code-have-inline-assembly-and-pic-mix-well
	 */
	__asm__("pushl %%ebx	\n\t" /* save %ebx */
		"cpuid		\n\t"
		"movl %%ebx, %1	\n\t" /* save what cpuid just put in %ebx */
		"popl %%ebx	\n\t" /* restore the old %ebx */
		: "=a" (*eax),
		  "=r" (*ebx),
		  "=c" (*ecx),
		  "=d" (*edx)
		: "0" (*eax),
		  "1" (*ebx),
		  "2" (*ecx),
		  "3" (*edx)
		);
}

#endif


void print_intel_cstates(void)
{
#ifdef __i386__ 

        int bios_table[8];
        int bioscount = 0;
	DIR *cpudir;
	DIR *dir;
	struct dirent *entry;
	FILE *file = NULL;
	char line[4096];
	char filename[128], *f;
	int len, i;
	unsigned int eax, ebx, ecx, edx;
	
	memset(bios_table, 0, sizeof(bios_table)); 


	cpudir = opendir("/sys/devices/system/cpu");
	if (!cpudir)
		return;

	/* Loop over cpuN entries */
	while ((entry = readdir(cpudir))) {
		if (strlen(entry->d_name) < 3)
			continue;

		if (!isdigit(entry->d_name[3]))
			continue;

		len = sprintf(filename, "/sys/devices/system/cpu/%s/cpuidle",
			      entry->d_name);

		dir = opendir(filename);
		if (!dir)
			return;

		/* For each C-state, there is a stateX directory which
		 * contains a 'usage' and a 'time' (duration) file */
		while ((entry = readdir(dir))) {
			if (strlen(entry->d_name) < 3)
				continue;
			sprintf(filename + len, "/%s/desc", entry->d_name);
			file = fopen(filename, "r");
			if (file) {

				memset(line, 0, 4096);
				f = fgets(line, 4096, file);
				fclose(file);
				if (f == NULL)
					break;
			
				f = strstr(line, "MWAIT ");
				if (f) {
					f += 6;
					bios_table[(strtoull(f, NULL, 16)>>4) + 1]++;
					bioscount++;
				}
			}
		}
		closedir(dir);

	}
	closedir(cpudir);
	if (!bioscount)
		return;

	eax = 5;
	ebx = 0; ecx = 0; edx = 0;
	cpuid(&eax, &ebx, &ecx, &edx);
	if (!edx || ((ecx&1) == 0))
		return;
	
	printf(_("Your CPU supports the following C-states : "));
	i = 0;
	while (edx) {
		if (edx&7)
			printf("C%i ", i);
		edx = edx >> 4;
		i++;
	}
	printf("\n");
	printf(_("Your BIOS reports the following C-states : "));
	for (i = 0; i < 8; i++)
		if (bios_table[i])
			printf("C%i ", i);
	printf("\n");
#endif
}
