#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This is a convenience module to import all available types of hosts.

Implementation details:
You should 'import hosts' instead of importing every available host module.
"""


# host abstract classes
from base_classes import Host
from remote import RemoteHost
from site_host import SiteHost

# host implementation classes
from ssh_host import SSHHost
from guest import Guest
from kvm_guest import KVMGuest

# extra logger classes
from serial import SerialHost
from netconsole import NetconsoleHost
from dmesg import DmesgHost

# bootloader classes
from bootloader import Bootloader


# generic host factory
def create_host(hostname, **args):
    from autotest_lib.client.common_lib import utils, error
    from autotest_lib.server import utils as server_utils

    # by default assume we're using SSH support
    hosts = [SSHHost]

    # use serial console support if it's available
    conmux_args = {}
    for key in ("conmux_server", "conmux_attach"):
        if key in args:
            conmux_args[key] = args[key]
    if SerialHost.host_is_supported(hostname, **conmux_args):
        hosts.append(SerialHost)
    else:
        # no serial host available, try netconsole logging if available
        def run_func(cmd):
            base_cmd = SSHHost.ssh_base_command(connect_timeout=3)
            full_cmd = '%s %s "%s"' % (base_cmd, hostname,
                                       server_utils.sh_escape(cmd))
            try:
                utils.run(full_cmd)
            except error.CmdError:
                pass

        if NetconsoleHost.host_is_supported(run_func):
            hosts.append(NetconsoleHost)
        else:
            hosts.append(DmesgHost)  # nothing available, fall back to dmesg

    # create a custom host class for this machine and make an instance of it
    host_class = type("%s_host" % hostname, tuple(hosts), {})
    return host_class(hostname, **args)
