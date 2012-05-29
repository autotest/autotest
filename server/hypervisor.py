#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the Hypervisor class

        Hypervisor: a virtual machine monitor
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)
"""


import installable_object


class Hypervisor(installable_object.InstallableObject):
    """
    This class represents a virtual machine monitor.

    Implementation details:
    This is an abstract class, leaf subclasses must implement the methods
    listed here and in parent classes which have no implementation. They
    may reimplement methods which already have an implementation. You
    must not instantiate this class but should instantiate one of those
    leaf subclasses.
    """

    host = None
    guests = None

    def __init__(self, host):
        super(Hypervisor, self).__init__()
        self.host= host


    def new_guest(self):
        pass


    def delete_guest(self, guest_hostname):
        pass


    def reset_guest(self, guest_hostname):
        pass
