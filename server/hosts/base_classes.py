#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the base classes for the server Host hierarchy.

Implementation details:
You should import the "hosts" package instead of importing each type of host.

        Host: a machine on which you can run programs
        RemoteHost: a remote machine on which you can run programs
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)
"""

import os

from autotest_lib.client.common_lib import hosts
from autotest_lib.server import utils
from autotest_lib.server.hosts import bootloader


class Host(hosts.Host):
    """
    This class represents a machine on which you can run programs.

    It may be a local machine, the one autoserv is running on, a remote
    machine or a virtual machine.

    Implementation details:
    This is an abstract class, leaf subclasses must implement the methods
    listed here. You must not instantiate this class but should
    instantiate one of those leaf subclasses.

    When overriding methods that raise NotImplementedError, the leaf class
    is fully responsible for the implementation and should not chain calls
    to super. When overriding methods that are a NOP in Host, the subclass
    should chain calls to super(). The criteria for fitting a new method into
    one category or the other should be:
        1. If two separate generic implementations could reasonably be
           concatenated, then the abstract implementation should pass and
           subclasses should chain calls to super.
        2. If only one class could reasonably perform the stated function
           (e.g. two separate run() implementations cannot both be executed)
           then the method should raise NotImplementedError in Host, and
           the implementor should NOT chain calls to super, to ensure that
           only one implementation ever gets executed.
    """

    bootloader = None


    def __init__(self, *args, **dargs):
        super(Host, self).__init__(*args, **dargs)

        self.start_loggers()
        if self.job:
            self.job.hosts.add(self)


    def _initialize(self, target_file_owner=None,
                    *args, **dargs):
        super(Host, self)._initialize(*args, **dargs)

        self.serverdir = utils.get_server_dir()
        self.monitordir = os.path.join(os.path.dirname(__file__), "monitors")
        self.bootloader = bootloader.Bootloader(self)
        self.env = {}
        self.target_file_owner = target_file_owner


    def close(self):
        super(Host, self).close()

        if self.job:
            self.job.hosts.discard(self)
