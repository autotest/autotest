"""
    Intermediate module for working with XML-related virsh functions/methods.

    All classes defined here should inherrit from LibvirtXMLBase and utilize
    the XMLTreeFile interface to recover external source XML in case internal
    errors are detected.  Errors originating within this module should raise
    LibvirtXMLError or subclasses of this exception.  Pleae refer to the
    xml_utils module documentation for more information on working with
    XMLTreeFile instances.
"""

import logging, os.path
from autotest.client.shared import error, xml_utils
from autotest.client.virt import libvirt_vm, virsh

class LibvirtXMLError(Exception):
    """
    Error originating within libvirt_xml module
    """

    def __init__(self, details=''):
        self.details = details
        super(LibvirtXMLError, self).__init__()


    def __str__(self):
        return str(self.details)


class LibvirtXMLBase(xml_utils.XMLTreeFile):
    """
    Base class for common attributes/methods applying to all sub-classes
    """

    @classmethod
    def generate_uuid(cls):
        """
        Returns generated uuid value
        """
        try:
            return open("/proc/sys/kernel/random/uuid").read().strip()
        except IOError:
            return "" #assume libvirt will fill in empty uuids


class LibvirtXML(LibvirtXMLBase):
    """
    Represents capabilities of libvirt
    """

    # Cache this data upon first __new__ call
    _XML = None

    def __new__(cls):
        if cls._XML is None:
            cls._XML = virsh.capabilities()
        # older python super doesn't work on class objects
        return LibvirtXMLBase.__new__(cls)

    def __init__(self):
        """Returns copy of libvirtd capabilities XML"""
        # protect against accidental modification
        super(LibvirtXML, self).__init__(self._XML)

