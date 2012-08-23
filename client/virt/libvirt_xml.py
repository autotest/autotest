import logging, os.path
from autotest.client.shared import error, xml_utils
from autotest.client.virt import libvirt_vm


class LibvirtXMLError(Exception):
    pass


class LibvirtXMLVMNameError(LibvirtXMLError):
    pass


class LibvirtXML(xml_utils.XMLBase):
    pass
