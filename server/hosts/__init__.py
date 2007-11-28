#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This is a convenience module to import all available types of hosts.

Implementation details:
You should 'import hosts' instead of importing every available host module.
"""

__author__ = """mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)"""


# host abstract classes
from base_classes import Host
from base_classes import SiteHost
from base_classes import RemoteHost

# host implementation classes
from ssh_host import SSHHost
from guest import Guest
from kvm_guest import KVMGuest

# bootloader classes
from bootloader import Bootloader
