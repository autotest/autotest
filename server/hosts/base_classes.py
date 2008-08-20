#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the base classes for the Host hierarchy.

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

import time

from autotest_lib.client.common_lib import global_config
from autotest_lib.server import utils
from autotest_lib.server.hosts import bootloader


class Host(object):
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
    job = None

    def __init__(self, *args, **dargs):
        super(Host, self).__init__(*args, **dargs)
        self.serverdir = utils.get_server_dir()
        self.bootloader= bootloader.Bootloader(self)
        self.env = {}


    def setup(self):
        pass


    def run(self, command):
        raise NotImplementedError('Run not implemented!')


    def run_output(self, command, *args, **dargs):
        return self.run(command, *args, **dargs).stdout.rstrip()


    def reboot(self):
        raise NotImplementedError('Reboot not implemented!')


    def reboot_setup(self):
        pass


    def reboot_followup(self):
        pass


    def get_file(self, source, dest):
        raise NotImplementedError('Get file not implemented!')


    def send_file(self, source, dest):
        raise NotImplementedError('Send file not implemented!')


    def get_tmp_dir(self):
        raise NotImplementedError('Get temp dir not implemented!')


    def is_up(self):
        raise NotImplementedError('Is up not implemented!')


    def get_wait_up_processes(self):
        """
        Gets the list of local processes to wait for in wait_up.
        """
        get_config = global_config.global_config.get_config_value
        proc_list = get_config("HOSTS", "wait_up_processes",
                               default="").strip()
        processes = set(p.strip() for p in proc_list.split(","))
        processes.discard("")
        return processes


    def wait_up(self, timeout):
        raise NotImplementedError('Wait up not implemented!')


    def wait_down(self, timeout):
        raise NotImplementedError('Wait down not implemented!')


    def get_num_cpu(self):
        raise NotImplementedError('Get num CPU not implemented!')


    def machine_install(self):
        raise NotImplementedError('Machine install not implemented!')


    def install(self, installableObject):
        installableObject.install(self)


    def get_crashdumps(self, test_start_time):
        pass


    def get_autodir(self):
        raise NotImplementedError('Get autodir not implemented!')

    def set_autodir(self):
        raise NotImplementedError('Set autodir not implemented!')
