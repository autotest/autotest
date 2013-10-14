# Copyright 2009 Google Inc. Released under the GPL v2

"""
This file contains the implementation of a host object for the local machine.
"""

import glob
import os
import platform
from autotest.client.shared import hosts, error
from autotest.client import utils


class LocalHost(hosts.Host):

    def _initialize(self, hostname=None, bootloader=None, *args, **dargs):
        super(LocalHost, self)._initialize(*args, **dargs)

        # hostname will be an actual hostname when this client was created
        # by an autoserv process
        if not hostname:
            hostname = platform.node()
        self.hostname = hostname
        self.bootloader = bootloader

    def wait_up(self, timeout=None):
        # a local host is always up
        return True

    def run(self, command, timeout=3600, ignore_status=False,
            stdout_tee=utils.TEE_TO_LOGS, stderr_tee=utils.TEE_TO_LOGS,
            stdin=None, args=()):
        """
        @see shared.hosts.Host.run()
        """
        try:
            result = utils.run(
                command, timeout=timeout, ignore_status=True,
                stdout_tee=stdout_tee, stderr_tee=stderr_tee, stdin=stdin,
                args=args)
        except error.CmdError, e:
            # this indicates a timeout exception
            raise error.AutotestHostRunError('command timed out', e.result_obj)

        if not ignore_status and result.exit_status > 0:
            raise error.AutotestHostRunError('command execution error', result)

        return result

    def list_files_glob(self, path_glob):
        """
        Get a list of files on a remote host given a glob pattern path.
        """
        return glob.glob(path_glob)

    def symlink_closure(self, paths):
        """
        Given a sequence of path strings, return the set of all paths that
        can be reached from the initial set by following symlinks.

        :param paths: sequence of path strings.
        :return: a sequence of path strings that are all the unique paths that
                can be reached from the given ones after following symlinks.
        """
        paths = set(paths)
        closure = set()

        while paths:
            path = paths.pop()
            if not os.path.exists(path):
                continue
            closure.add(path)
            if os.path.islink(path):
                link_to = os.path.join(os.path.dirname(path),
                                       os.readlink(path))
                if link_to not in closure:
                    paths.add(link_to)

        return closure
