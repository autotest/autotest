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

void activate_WOL_suggestion(void) 
{
	int sock;
	struct ifreq ifr;
	struct ethtool_wolinfo wol;
	int ret;

	memset(&ifr, 0, sizeof(struct ifreq));

	sock = socket(AF_INET, SOCK_DGRAM, 0);
	if (sock<0) 
		return;

	strcpy(ifr.ifr_name, "eth0");

	/* Check if the interface is up */
	ret = ioctl(sock, SIOCGIFFLAGS, &ifr);
	if (ret<0) {
		close(sock);
		return;
	}

	if (ifr.ifr_flags & (IFF_UP | IFF_RUNNING)) {
		close(sock);
		return;
	}

	memset(&wol, 0, sizeof(wol));

	wol.cmd = ETHTOOL_GWOL;
	ifr.ifr_data = (caddr_t)&wol;
        ioctl(sock, SIOCETHTOOL, &ifr);
	wol.cmd = ETHTOOL_SWOL;
	wol.wolopts = 0;
        ioctl(sock, SIOCETHTOOL, &ifr);

	close(sock);
}



void suggest_WOL_off(void) 
{
	int sock;
	struct ifreq ifr;
	struct ethtool_wolinfo wol;
	int ret;

	memset(&ifr, 0, sizeof(struct ifreq));

	sock = socket(AF_INET, SOCK_DGRAM, 0);
	if (sock<0) 
		return;

	strcpy(ifr.ifr_name, "eth0");

	/* Check if the interface is up */
	ret = ioctl(sock, SIOCGIFFLAGS, &ifr);
	if (ret<0) {
		close(sock);
		return;
	}

	if (ifr.ifr_flags & (IFF_UP | IFF_RUNNING)) {
		close(sock);
		return;
	}

	memset(&wol, 0, sizeof(wol));

	wol.cmd = ETHTOOL_GWOL;
	ifr.ifr_data = (caddr_t)&wol;
        ioctl(sock, SIOCETHTOOL, &ifr);

	if (wol.wolopts) {
		add_suggestion(_(
			"Disable Ethernet Wake-On-Lan with the following command:\n"
			"  ethtool -s eth0 wol d \n"
			"Wake-on-Lan keeps the phy active, this costs power."), 5, 
			'W', _(" W - disable Wake-On-Lan "), activate_WOL_suggestion);


	}

	close(sock);
}

