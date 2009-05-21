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

import os, re, time, cStringIO, sys, traceback

from autotest_lib.client.common_lib import global_config, error
from autotest_lib.client.common_lib import host_protections
from autotest_lib.client.bin import partition
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
    DEFAULT_REBOOT_TIMEOUT = 1800
    WAIT_DOWN_REBOOT_TIMEOUT = 840
    WAIT_DOWN_REBOOT_WARNING = 540
    HOURS_TO_WAIT_FOR_RECOVERY = 2.5


    def __init__(self, *args, **dargs):
        self._initialize(*args, **dargs)
        self.start_loggers()
        if self.job:
            self.job.hosts.add(self)


    def _initialize(self, target_file_owner=None,
                    *args, **dargs):
        self.serverdir = utils.get_server_dir()
        self.monitordir = os.path.join(os.path.dirname(__file__), "monitors")
        self.bootloader = bootloader.Bootloader(self)
        self.env = {}
        self.target_file_owner = target_file_owner


    def close(self):
        if self.job:
            self.job.hosts.discard(self)


    def setup(self):
        pass


    def run(self, command):
        raise NotImplementedError('Run not implemented!')


    def run_output(self, command, *args, **dargs):
        return self.run(command, *args, **dargs).stdout.rstrip()


    def reboot(self):
        raise NotImplementedError('Reboot not implemented!')


    def sysrq_reboot(self):
        raise NotImplementedError('Sysrq reboot not implemented!')


    def reboot_setup(self, *args, **dargs):
        pass


    def reboot_followup(self, *args, **dargs):
        pass


    def get_file(self, source, dest, delete_dest=False):
        raise NotImplementedError('Get file not implemented!')


    def send_file(self, source, dest, delete_dest=False):
        raise NotImplementedError('Send file not implemented!')


    def get_tmp_dir(self):
        raise NotImplementedError('Get temp dir not implemented!')


    def is_up(self):
        raise NotImplementedError('Is up not implemented!')


    def is_shutting_down(self):
        """ Indicates is a machine is currently shutting down. """
        runlevel = int(self.run("runlevel").stdout.strip().split()[1])
        return runlevel in (0, 6)


    def get_wait_up_processes(self):
        """ Gets the list of local processes to wait for in wait_up. """
        get_config = global_config.global_config.get_config_value
        proc_list = get_config("HOSTS", "wait_up_processes",
                               default="").strip()
        processes = set(p.strip() for p in proc_list.split(","))
        processes.discard("")
        return processes


    def wait_up(self, timeout=None):
        raise NotImplementedError('Wait up not implemented!')


    def wait_down(self, timeout=None, warning_timer=None):
        raise NotImplementedError('Wait down not implemented!')


    def wait_for_restart(self, timeout=DEFAULT_REBOOT_TIMEOUT, **dargs):
        """ Wait for the host to come back from a reboot. This is a generic
        implementation based entirely on wait_up and wait_down. """
        if not self.wait_down(timeout=self.WAIT_DOWN_REBOOT_TIMEOUT,
                              warning_timer=self.WAIT_DOWN_REBOOT_WARNING):
            self.record("ABORT", None, "reboot.verify", "shut down failed")
            raise error.AutoservRebootError("Host did not shut down")
        self.wait_up(timeout)
        time.sleep(2)    # this is needed for complete reliability
        if self.wait_up(timeout):
            self.record("GOOD", None, "reboot.verify")
            self.reboot_followup(**dargs)
        else:
            self.record("ABORT", None, "reboot.verify",
                        "Host did not return from reboot")
            raise error.AutoservRebootError(
                "Host did not return from reboot")


    def verify(self):
        pass


    def verify_hardware(self):
        pass


    def verify_software(self):
        pass


    def check_diskspace(self, path, gb):
        print 'Checking for >= %s GB of space under %s on machine %s' % \
                                             (gb, path, self.hostname)
        df = self.run('df -mP %s | tail -1' % path).stdout.split()
        free_space_gb = int(df[3])/1000.0
        if free_space_gb < gb:
            raise error.AutoservHostError('Not enough free space on ' +
                                          '%s - %.3fGB free, want %.3fGB' %
                                          (path, free_space_gb, gb))
        else:
            print 'Found %s GB >= %s GB of space under %s on machine %s' % \
                                       (free_space_gb, gb, path, self.hostname)


    def get_open_func(self, use_cache=True):
        """
        Defines and returns a function that may be used instead of built-in
        open() to open and read files. The returned function is implemented
        by using self.run('cat <file>') and may cache the results for the same
        filename.

        @param use_cache Cache results of self.run('cat <filename>') for the
            same filename

        @return a function that can be used instead of built-in open()
        """
        cached_files = {}

        def open_func(filename):
            if not use_cache or filename not in cached_files:
                output = self.run('cat \'%s\'' % filename,
                                  stdout_tee=open('/dev/null', 'w')).stdout
                fd = cStringIO.StringIO(output)

                if not use_cache:
                    return fd

                cached_files[filename] = fd
            else:
                cached_files[filename].seek(0)

            return cached_files[filename]

        return open_func


    def check_partitions(self, root_part, filter_func=None):
        """ Compare the contents of /proc/partitions with those of
        /proc/mounts and raise exception in case unmounted partitions are found

        root_part: in Linux /proc/mounts will never directly mention the root
        partition as being mounted on / instead it will say that /dev/root is
        mounted on /. Thus require this argument to filter out the root_part
        from the ones checked to be mounted

        filter_func: unnary predicate for additional filtering out of
        partitions required to be mounted

        Raise: error.AutoservHostError if unfiltered unmounted partition found
        """

        print 'Checking if non-swap partitions are mounted...'

        unmounted = partition.get_unmounted_partition_list(root_part,
            filter_func=filter_func, open_func=self.get_open_func())
        if unmounted:
            raise error.AutoservHostError('Found unmounted partitions: %s' %
                                          [part.device for part in unmounted])


    def _wrap_with_verify(self, func):
        try:
            func()
        except Exception, err:
            traceback.print_exc()
        self.verify()


    def repair_filesystem_only(self):
        """perform file system repairs only"""
        def do_repair():
            TIMEOUT = int(self.HOURS_TO_WAIT_FOR_RECOVERY * 3600)
            if self.is_shutting_down():
                print 'Host is shutting down, waiting for a restart'
                self.wait_for_restart(TIMEOUT)
            else:
                self.wait_up(TIMEOUT)
            self.reboot()

        self._wrap_with_verify(do_repair)


    def repair_software_only(self):
        """perform software repairs only"""
        try:
            self.repair_filesystem_only()
        except Exception:
            # the filesystem-only repair failed, try something more drastic
            print "Filesystem-only repair failed"
            self._wrap_with_verify(self.machine_install)


    def repair_full(self):
        try:
            self.repair_software_only()
        except Exception:
            # software repair failed, try hardware repair
            print "Software only repair failed"
            self.request_hardware_repair()

            # repair failed but managed to request for hardware repairs
            raise error.AutoservHardwareRepairRequestedError(
                "repair failed but hardware repairs have been requested")


    def cleanup(self):
        pass


    def machine_install(self):
        raise NotImplementedError('Machine install not implemented!')


    def install(self, installableObject):
        installableObject.install(self)


    def get_autodir(self):
        raise NotImplementedError('Get autodir not implemented!')


    def set_autodir(self):
        raise NotImplementedError('Set autodir not implemented!')


    def start_loggers(self):
        """ Called to start continuous host logging. """
        pass


    def stop_loggers(self):
        """ Called to stop continuous host logging. """
        pass


    # some extra methods simplify the retrieval of information about the
    # Host machine, with generic implementations based on run(). subclasses
    # should feel free to override these if they can provide better
    # implementations for their specific Host types

    def get_num_cpu(self):
        """ Get the number of CPUs in the host according to /proc/cpuinfo. """

        proc_cpuinfo = self.run("cat /proc/cpuinfo",
                        stdout_tee=open('/dev/null', 'w')).stdout
        cpus = 0
        for line in proc_cpuinfo.splitlines():
            if line.startswith('processor'):
                cpus += 1
        return cpus


    def get_arch(self):
        """ Get the hardware architecture of the remote machine. """
        arch = self.run('/bin/uname -m').stdout.rstrip()
        if re.match(r'i\d86$', arch):
            arch = 'i386'
        return arch


    def get_kernel_ver(self):
        """ Get the kernel version of the remote machine. """
        return self.run('/bin/uname -r').stdout.rstrip()


    def get_cmdline(self):
        """ Get the kernel command line of the remote machine. """
        return self.run('cat /proc/cmdline').stdout.rstrip()


    # some extra helpers for doing job-related operations

    def record(self, *args, **dargs):
        """ Helper method for recording status logs against Host.job that
        silently becomes a NOP if Host.job is not available. The args and
        dargs are passed on to Host.job.record unchanged. """
        if self.job:
            self.job.record(*args, **dargs)


    def log_kernel(self):
        """ Helper method for logging kernel information into the status logs.
        Intended for cases where the "current" kernel is not really defined
        and we want to explicitly log it. Does nothing if this host isn't
        actually associated with a job. """
        if self.job:
            kernel = self.get_kernel_ver()
            self.job.record("INFO", None, None,
                            optional_fields={"kernel": kernel})


    def log_reboot(self, reboot_func):
        """ Decorator for wrapping a reboot in a group for status
        logging purposes. The reboot_func parameter should be an actual
        function that carries out the reboot.
        """
        if self.job and not hasattr(self, "RUNNING_LOG_REBOOT"):
            self.RUNNING_LOG_REBOOT = True
            try:
                self.job.run_reboot(reboot_func, self.get_kernel_ver)
            finally:
                del self.RUNNING_LOG_REBOOT
        else:
            reboot_func()


    def request_hardware_repair(self):
        """ Should somehow request (send a mail?) for hardware repairs on
        this machine.
        """
        raise NotImplementedError("request_hardware_repair not implemented")
