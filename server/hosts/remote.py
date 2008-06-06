"""This class defines the Remote host class, mixing in the SiteHost class
if it is available."""

# site_host.py may be non-existant or empty, make sure that an appropriate
# SiteHost class is created nevertheless
try:
    from site_host import SiteHost
except ImportError:
    import base_classes
    class SiteHost(base_classes.Host):
        def __init__(self):
            super(SiteHost, self).__init__()


class RemoteHost(SiteHost):
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

    hostname= None

    def __init__(self):
        super(RemoteHost, self).__init__()
