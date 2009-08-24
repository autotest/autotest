# Copyright 2009 Google Inc. Released under the GPL v2

"""
This file contains the implementation of a host object for the local machine.
"""

import platform
from autotest_lib.client.common_lib import hosts, error
from autotest_lib.client.bin import utils

class LocalHost(hosts.Host):
    def _initialize(self, hostname=None, *args, **dargs):
        super(LocalHost, self)._initialize(*args, **dargs)

        # hostname will be an actual hostname when this client was created
        # by an autoserv process
        if not hostname:
            hostname = platform.node()
        self.hostname = hostname


    def wait_up(self, timeout=None):
        # a local host is always up
        return True


    def run(self, command, timeout=3600, ignore_status=False,
            stdout_tee=utils.TEE_TO_LOGS, stderr_tee=utils.TEE_TO_LOGS,
            stdin=None):
        """
        @see common_lib.hosts.Host.run()
        """
        result = utils.run(command, timeout=timeout, ignore_status=True,
                stdout_tee=stdout_tee, stderr_tee=stderr_tee, stdin=stdin)

        if not ignore_status and result.exit_status > 0:
            raise error.AutotestHostRunError('command execution error', result)

        return result
