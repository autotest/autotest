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
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <errno.h>

#include "powertop.h"


/* structure definitions copied from include/net/bluetooth/hci.h from the 2.6.20 kernel */
#define HCIGETDEVINFO   _IOR('H', 211, int)
#define BTPROTO_HCI     1

#define __u16 uint16_t
#define __u8 uint8_t
#define __u32 uint32_t

typedef struct {
        __u8 b[6];
} __attribute__((packed)) bdaddr_t;

struct hci_dev_stats {
        __u32 err_rx;
        __u32 err_tx;
        __u32 cmd_tx;
        __u32 evt_rx;
        __u32 acl_tx;
        __u32 acl_rx;
        __u32 sco_tx;
        __u32 sco_rx;
        __u32 byte_rx;
        __u32 byte_tx;
};


struct hci_dev_info {
	__u16 dev_id;
	char  name[8];

	bdaddr_t bdaddr;

	__u32 flags;
	__u8  type;

	__u8  features[8];

	__u32 pkt_type;
	__u32 link_policy;
	__u32 link_mode;

	__u16 acl_mtu;
	__u16 acl_pkts;
	__u16 sco_mtu;
	__u16 sco_pkts;

	struct hci_dev_stats stat;
};

static int previous_bytes = -1;

void turn_bluetooth_off(void)
{
	system("/usr/sbin/hciconfig hci0 down &> /dev/null");
	system("/sbin/rmmod hci_usb &> /dev/null");
}

void suggest_bluetooth_off(void)
{
	struct hci_dev_info devinfo;
	FILE *file;
	int fd;
	int ret;
	int thisbytes = 0;

	/* first check if /sys/modules/bluetooth exists, if not, don't probe bluetooth because
	   it would trigger an autoload */

	if (access("/sys/module/bluetooth",F_OK))
		return;

	fd = socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI);
	if (fd < 0)
		return;

	memset(&devinfo, 0, sizeof(devinfo));
	strcpy(devinfo.name, "hci0");
	ret = ioctl(fd, HCIGETDEVINFO, (void *) &devinfo);		
	if (ret < 0)
		goto out;

	if ( (devinfo.flags & 1) == 0 && 
		access("/sys/module/hci_usb",F_OK)) /* interface down already */
		goto out;

	thisbytes += devinfo.stat.byte_rx;
	thisbytes += devinfo.stat.byte_tx;

	if (thisbytes != previous_bytes)
		goto out;

	/* now, also check for active connections */
	file = popen("/usr/bin/hcitool con 2> /dev/null", "r");
	if (file) {
		char line[2048];
		/* first line is standard header */
		fgets(line,2048,file);
		memset(line, 0, 2048);
		fgets(line, 2047, file);
		pclose(file);
		if (strlen(line)>0)
			goto out;
	}

	add_suggestion( _("Suggestion: Disable the unused bluetooth interface with the following command:\n"
			"  hciconfig hci0 down ; rmmod hci_usb\n"
			"Bluetooth is a radio and consumes quite some power, and keeps USB busy as well.\n"), 40, 'B' , _(" B - Turn Bluetooth off "), turn_bluetooth_off);
out:
	previous_bytes = thisbytes;
	close(fd);
	return;
}
