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
#include <linux/types.h>
#include <net/if.h>
#include <linux/sockios.h>
#include <sys/ioctl.h>

/* work around a bug in debian -- it exposes kernel internal types to userspace */
#define u64 __u64 
#define u32 __u32  
#define u16 __u16  
#define u8 __u8
#include <linux/ethtool.h>
#undef u64
#undef u32
#undef u16
#undef u8



#include "powertop.h"


static char wireless_nic[32];
static char rfkill_path[PATH_MAX];
static char powersave_path[PATH_MAX];

static int rfkill_enabled(void)
{
	FILE *file;
	char val;
	if (strlen(rfkill_path)<2)
		return 0;
	if (access(rfkill_path, W_OK))
		return 0;

	file = fopen(rfkill_path, "r");
	if (!file)
		return 0;
	val = fgetc(file);
	fclose(file);
	if (val != '0') /* already rfkill'd */
		return 1;
	return 0;
}

int check_unused_wiresless_up(void)
{
	FILE *file;
	char val;
	char line[1024];
	if (strlen(rfkill_path)<2)
		return 0;
	if (access(rfkill_path, W_OK))
		return 0;

	file = fopen(rfkill_path, "r");
	if (!file)
		return 0;
	val = fgetc(file);
	fclose(file);
	if (val != '0') /* already rfkill'd */
		return -1;
	
	sprintf(line,"iwconfig %s 2> /dev/null", wireless_nic);
	file = popen(line, "r");
	if (!file)
		return 0;
	while (!feof(file)) {
		memset(line, 0, 1024);
		if (fgets(line, 1023, file) == 0)
			break;
		if (strstr(line, "Mode:Managed") && strstr(line,"Access Point: Not-Associated")) {
			pclose(file);
			return 1;
		}		
	}
	pclose(file);	
	return 0;
}


static int need_wireless_suggest(char *iface)
{
	FILE *file;
	char line[1024];
	int ret = 0;

	if (rfkill_enabled())
		return 0;

	sprintf(line, "/sbin/iwpriv %s get_power 2> /dev/null", iface);
	file = popen(line, "r");
	if (!file)
		return 0;
	while (!feof(file)) {
		memset(line, 0, 1024);
		if (fgets(line, 1023, file)==NULL)
			break;
		if (strstr(line, "Power save level: 6 (AC)")) {
			ret = 1;
			break;
		}
	}
	pclose(file);
	return ret;
}


static int need_wireless_suggest_new(void)
{
	FILE *file;
	char val;
	if (strlen(powersave_path)<2)
		return 0;
	if (access(powersave_path, W_OK))
		return 0;

	if (rfkill_enabled())
		return 0;

	file = fopen(powersave_path, "r");
	if (!file)
		return 0;
	val = fgetc(file);
	fclose(file);
	if (val <= '5' && val >= '0') /* already in powersave */
		return 0;
	
	return 1;
}

void find_4965(void)
{
	static int tried_4965 = 0;
	DIR *dir;
	struct dirent *dirent;
	char pathname[PATH_MAX];

	if (tried_4965++)
		return;

	dir = opendir("/sys/bus/pci/drivers/iwl4965");
	while (dir && (dirent = readdir(dir))) {
		if (dirent->d_name[0]=='.')
			continue;
		sprintf(pathname, "/sys/bus/pci/drivers/iwl4965/%s/power_level", dirent->d_name);
		if (!access(pathname, W_OK))
			strcpy(powersave_path, pathname);
	}
	if (dir)
		closedir(dir);
	dir = opendir("/sys/bus/pci/drivers/iwl3945");
	if (!dir)
		return;
	while ((dirent = readdir(dir))) {
		if (dirent->d_name[0]=='.')
			continue;
		sprintf(pathname, "/sys/bus/pci/drivers/iwl3945/%s/power_level", dirent->d_name);
		if (!access(pathname, W_OK))
			strcpy(powersave_path, pathname);
	}

	closedir(dir);

}


void find_wireless_nic(void) 
{
	static int found = 0;
	FILE *file;
	int sock;
	struct ifreq ifr;
	struct ethtool_value ethtool;
	struct ethtool_drvinfo driver;
	int ifaceup = 0;
	int ret;

	if (found++)
		return;

	wireless_nic[0] = 0;
	rfkill_path[0] = 0;
	powersave_path[0] = 0;

	strcpy(wireless_nic, "wlan0");

	file = popen("/sbin/iwpriv -a 2> /dev/null", "r");
	if (!file)
		return;
	while (!feof(file)) {
		char line[1024];
		memset(line, 0, 1024);
		if (fgets(line, 1023, file)==NULL)
			break;
		if (strstr(line, "get_power:Power save level")) {
			char *c;
			c = strchr(line, ' ');
			if (c) *c = 0;
			strcpy(wireless_nic, line);
		}
		if (strstr(line, "wlan0:"))
			strcpy(wireless_nic, "wlan0");
	}
	pclose(file);

	
	if (strlen(wireless_nic)==0)
		return;


	memset(&ifr, 0, sizeof(struct ifreq));
	memset(&ethtool, 0, sizeof(struct ethtool_value));

	sock = socket(AF_INET, SOCK_DGRAM, 0);
	if (sock<0) 
		return;

	strcpy(ifr.ifr_name, wireless_nic);

	/* Check if the interface is up */
	ret = ioctl(sock, SIOCGIFFLAGS, &ifr);
	if (ret<0) {
		close(sock);
		return;
	}

	ifaceup = 0;
	if (ifr.ifr_flags & (IFF_UP | IFF_RUNNING))
		ifaceup = 1;

	memset(&driver, 0, sizeof(driver));
	driver.cmd = ETHTOOL_GDRVINFO;
        ifr.ifr_data = (void*) &driver;
        ret = ioctl(sock, SIOCETHTOOL, &ifr);

	sprintf(rfkill_path,"/sys/bus/pci/devices/%s/rfkill/rfkill0/state", driver.bus_info);
	sprintf(powersave_path,"/sys/bus/pci/devices/%s/power_level", driver.bus_info);
	close(sock);
}

void activate_wireless_suggestion(void)
{
	char line[1024];
	sprintf(line, "/sbin/iwpriv %s set_power 5 2> /dev/null", wireless_nic);
	system(line);
}
void activate_wireless_suggestion_new(void)
{
	FILE *file;
	file = fopen(powersave_path, "w");
	if (!file)
		return;
	fprintf(file,"1\n");
	fclose(file);
}

void activate_rfkill_suggestion(void)
{	
	FILE *file;
	file = fopen(rfkill_path, "w");
	if (!file)
		return;
	fprintf(file,"1\n");
	fclose(file);
}
void suggest_wireless_powersave(void)
{
	char sug[1024];
	int ret;

	if (strlen(wireless_nic)==0) 
		find_wireless_nic();
	find_4965();
	ret = check_unused_wiresless_up();

	if (ret >= 0 && need_wireless_suggest(wireless_nic)) {
		sprintf(sug, _("Suggestion: Enable wireless power saving mode by executing the following command:\n "
			       " iwpriv %s set_power 5 \n"
			       "This will sacrifice network performance slightly to save power."), wireless_nic);
		add_suggestion(sug, 20, 'W', _(" W - Enable wireless power saving "), activate_wireless_suggestion);
	}
	if (ret >= 0 && need_wireless_suggest_new()) {
		sprintf(sug, _("Suggestion: Enable wireless power saving mode by executing the following command:\n "
			       " echo 5 > %s \n"
			       "This will sacrifice network performance slightly to save power."), powersave_path);
		add_suggestion(sug, 20, 'W', _(" W - Enable wireless power saving "), activate_wireless_suggestion_new);
	}
	if (ret>0) {
		sprintf(sug, _("Suggestion: Disable the unused WIFI radio by executing the following command:\n "
			       " echo 1 > %s \n"), rfkill_path);
		add_suggestion(sug, 60, 'I', _(" I - disable WIFI Radio "), activate_rfkill_suggestion);

	}
}
