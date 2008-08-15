"""This class defines the Remote host class, mixing in the SiteHost class
if it is available."""

from autotest_lib.server.hosts import base_classes


class RemoteHost(base_classes.Host):
    """This class represents a remote machine on which you can run
    programs.

    It may be accessed through a network, a serial line, ...
    It is not the machine autoserv is running on.

    Implementation details:
    This is an abstract class, leaf subclasses must implement the methods
    listed here and in parent classes which have no implementation. They
    may reimplement methods which already have an implementation. You
    must not instantiate this class but should instantiate one of those
    leaf subclasses."""

    def __init__(self, hostname, *args, **dargs):
        super(RemoteHost, self).__init__(*args, **dargs)

        self.hostname = hostname
