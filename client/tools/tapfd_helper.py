#!/usr/bin/python

import sys
import os
import re
# This 'common' module is required by autotest framework.
import common
from autotest_lib.client.virt import virt_utils

def destroy_tap(tapfd_list):
    for tapfd in tapfd_list:
        try:
            os.close(tapfd)
        # File descriptor is already closed
        except OSError:
            pass


if len(sys.argv) <= 2:
    print "Usage: %s bridge_name qemu_command_line" % sys.argv[0]
    sys.exit(255)

brname = sys.argv[1]
cmd_line = ' '.join(sys.argv[2:])

if re.findall("-netdev\s", cmd_line):
    # so we get the new qemu cli with netdev parameter.
    tap_list_re = r"tap,id=(.*?),"
    tap_replace_re = r"(tap,id=%s.*?,fd=)\d+"
else:
    # the old cli contain "-net" parameter.
    tap_list_re = r"tap,vlan=(\d+),"
    tap_replace_re = r"(tap,vlan=%s,fd=)\d+"

tap_list = re.findall(tap_list_re, cmd_line)
if not tap_list:
    print "Could not find tap device."
    sys.exit(1)

tapfd_list = []

for tap in tap_list:
    try:
        ifname = "tap-%s" % tap
        tapfd = virt_utils.open_tap("/dev/net/tun", ifname)
        virt_utils.add_to_bridge(ifname, brname)
        virt_utils.bring_up_ifname(ifname)
        pattern = tap_replace_re % tap
        cmd_line = re.sub(pattern, "\g<1>%s " % tapfd, cmd_line)
        tapfd_list.append(tapfd)
    except Exception, e:
        destroy_tap(tapfd_list)
        print "Error: %s" % e
        sys.exit(2)

try:
    # Run qemu command.
    os.system(cmd_line)
finally:
    destroy_tap(tapfd_list)
