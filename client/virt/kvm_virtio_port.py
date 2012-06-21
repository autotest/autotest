"""
Interfaces and helpers for the virtio_serial ports.

@copyright: 2012 Red Hat Inc.
"""
import socket
import time
import select
from client.shared import error
import logging


class _VirtioPort(object):
    """
    Define structure to keep information about used port.
    """
    def __init__(self, name, hostfile):
        """
        @param vm: virtual machine object that port owned
        @param name: Name of port for guest side.
        @param hostfile: Path to port on host side.
        @param path: Path to port on host side.
        """
        self.name = name
        self.hostfile = hostfile
        self.is_console = None  # "yes", "no"
        self.sock = None
        self.is_open = False

    def for_guest(self):
        """
        Format data for communication with guest side.
        """
        return [self.name, self.is_console]

    def open(self):
        """
        Open port on host side.
        """
        attempt = 11
        while attempt > 0:
            try:
                self.sock = socket.socket(socket.AF_UNIX,
                                          socket.SOCK_STREAM)
                self.sock.connect(self.hostfile)
                self.sock.setsockopt(1, socket.SO_SNDBUF, 2048)
                self.is_open = True
                return
            except Exception:
                attempt -= 1
                time.sleep(1)
        raise error.TestFail("Can't open the %s sock" % self.name)

    def clean_port(self):
        """
        Clean all data from opened port on host side.
        """
        if self.is_open:
            self.close()
        self.open()
        ret = select.select([self.sock], [], [], 1.0)
        if ret[0]:
            buf = self.sock.recv(1024)
            logging.debug("Rest in socket: " + buf)

    def close(self):
        """
        Close port.
        """
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        self.is_open = False

    def __str__(self):
        """
        Convert to text.
        """
        return ("%s,%s,%s,%s,%d" % ("Socket", self.name, self.is_console,
                                    self.hostfile, self.is_open))


class VirtioSerial(_VirtioPort):
    def __init__(self, name, hostfile):
        super(VirtioSerial, self).__init__(name, hostfile)
        self.is_console = "no"


class VirtioConsole(_VirtioPort):
    def __init__(self, name, hostfile):
        super(VirtioConsole, self).__init__(name, hostfile)
        self.is_console = "yes"
