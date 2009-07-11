#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This is a convenience module to import all available types of hosts.

Implementation details:
You should 'import hosts' instead of importing every available host module.
"""


# host abstract classes
from base_classes import Host
from remote import RemoteHost
try:
    from site_host import SiteHost
except ImportError, e:
    pass

# host implementation classes
from ssh_host import SSHHost
from guest import Guest
from kvm_guest import KVMGuest

# extra logger classes
from serial import SerialHost
from netconsole import NetconsoleHost

# bootloader classes
from bootloader import Bootloader

# factory function
from factory import create_host
