#
# Copyright 2012 IBM Inc. Released under the GPL v2

"""
This module defines the InstallableHost class.

Implementation details:
You should import the "hosts" package instead of importing each type of host.

        InstallableHost: a remote machine with a ssh access and a profile
"""

from autotest.server.hosts import ssh_host


class InstallableHost(ssh_host.SSHHost):
    """
    Implementation details:
    This is a leaf class in an abstract class hierarchy, it must
    implement the unimplemented methods in parent classes.
    """

    def _initialize(self, hostname, profile, *args, **dargs):
        """
        Construct a SSHHost object

        Args:
                hostname: network hostname or address of remote machine
        """
        super(InstallableHost, self)._initialize(hostname=hostname,
                                                 *args,
                                                 **dargs)
        self.profile = profile
