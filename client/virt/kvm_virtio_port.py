"""
Interfaces and helpers for the virtio_serial ports.

@copyright: 2012 Red Hat Inc.
"""
from client.shared import error
from threading import Thread
import logging
import random
import select
import socket
import time
import os
import virt_test_utils
import aexpect


class _VirtioPort(object):
    """
    Define structure to keep information about used port.
    """
    def __init__(self, name, hostfile):
        """
        @param name: Name of port for guest side.
        @param hostfile: Path to port on host side.
        """
        self.name = name
        self.hostfile = hostfile
        self.is_console = None  # "yes", "no"
        self.sock = None
        self.is_open = False

    def __str__(self):
        """
        Convert to text.
        """
        return ("%s,%s,%s,%s,%d" % ("Socket", self.name, self.is_console,
                                    self.hostfile, self.is_open))

    def __getstate__(self):
        """
        socket is unpickable so we need to remove it and say it's closed.
        Used by autotest env.
        """
        if self.is_open:
            logging.warn("Force closing virtio_port socket, FIX the code to "
                         " close the socket prior this to avoid possible err.")
            self.close()
        return self.__dict__.copy()

    def for_guest(self):
        """
        Format data for communication with guest side.
        """
        return [self.name, self.is_console]

    def open(self):     # @ReservedAssignment
        """
        Open port on host side.
        """
        if self.is_open:
            return
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
        self.sock = None
        self.is_open = False


class VirtioSerial(_VirtioPort):
    def __init__(self, name, hostfile):
        super(VirtioSerial, self).__init__(name, hostfile)
        self.is_console = "no"


class VirtioConsole(_VirtioPort):
    def __init__(self, name, hostfile):
        super(VirtioConsole, self).__init__(name, hostfile)
        self.is_console = "yes"


class ThSend(Thread):
    """
    Random data sender thread.
    """
    def __init__(self, port, data, event, quiet=False):
        """
        @param port: Destination port.
        @param data: The data intend to be send in a loop.
        @param event: Exit event.
        @param quiet: If true don't raise event when crash.
        """
        Thread.__init__(self)
        self.port = port
        # FIXME: socket.send(data>>127998) without read blocks thread
        if len(data) > 102400:
            data = data[0:102400]
            logging.error("Data is too long, using only first %d bytes",
                          len(data))
        self.data = data
        self.exitevent = event
        self.idx = 0
        self.quiet = quiet

    def run(self):
        logging.debug("ThSend %s: run", self.getName())
        try:
            while not self.exitevent.isSet():
                self.idx += self.port.send(self.data)
            logging.debug("ThSend %s: exit(%d)", self.getName(),
                          self.idx)
        except Exception, ints:
            if not self.quiet:
                raise ints
            logging.debug(ints)


class ThSendCheck(Thread):
    """
    Random data sender thread.
    """
    def __init__(self, port, event, queues, blocklen=1024):
        """
        @param port: Destination port
        @param event: Exit event
        @param queues: Queues for the control data (FIFOs)
        @param blocklen: Block length
        """
        Thread.__init__(self)
        self.port = port
        self.queues = queues
        # FIXME: socket.send(data>>127998) without read blocks thread
        if blocklen > 102400:
            blocklen = 102400
            logging.error("Data is too long, using blocklen = %d",
                          blocklen)
        self.blocklen = blocklen
        self.exitevent = event
        self.idx = 0

    def run(self):
        logging.debug("ThSendCheck %s: run", self.getName())
        too_much_data = False
        while not self.exitevent.isSet():
            # FIXME: workaround the problem with qemu-kvm stall when too
            # much data is sent without receiving
            for queue in self.queues:
                while not self.exitevent.isSet() and len(queue) > 1048576:
                    too_much_data = True
                    time.sleep(0.1)
            ret = select.select([], [self.port.sock], [], 1.0)
            if ret[1]:
                # Generate blocklen of random data add them to the FIFO
                # and send them over virtio_console
                buf = ""
                for _ in range(self.blocklen):
                    char = "%c" % random.randrange(255)
                    buf += char
                    for queue in self.queues:
                        queue.append(char)
                target = self.idx + self.blocklen
                while not self.exitevent.isSet() and self.idx < target:
                    try:
                        idx = self.port.sock.send(buf)
                    except Exception, inst:
                        # Broken pipe
                        if inst.errno == 32:
                            logging.debug("ThSendCheck %s: Broken pipe "
                                          "(migration?), reconnecting",
                                          self.getName())
                            attempt = 10
                            while (attempt > 1
                                   and not self.exitevent.isSet()):
                                self.port.is_open = False
                                self.port.open()
                                try:
                                    idx = self.port.sock.send(buf)
                                except Exception:
                                    attempt += 1
                                    time.sleep(10)
                                else:
                                    attempt = 0
                    buf = buf[idx:]
                    self.idx += idx
        logging.debug("ThSendCheck %s: exit(%d)", self.getName(),
                      self.idx)
        if too_much_data:
            logging.error("ThSendCheck: working around the 'too_much_data'"
                          "bug")


class ThRecv(Thread):
    """
    Recieves data and throws it away.
    """
    def __init__(self, port, event, blocklen=1024, quiet=False):
        """
        @param port: Data source port.
        @param event: Exit event.
        @param blocklen: Block length.
        @param quiet: If true don't raise event when crash.
        """
        Thread.__init__(self)
        self.port = port
        self._port_timeout = self.port.gettimeout()
        self.port.settimeout(0.1)
        self.exitevent = event
        self.blocklen = blocklen
        self.idx = 0
        self.quiet = quiet

    def run(self):
        logging.debug("ThRecv %s: run", self.getName())
        try:
            while not self.exitevent.isSet():
                # TODO: Workaround, it didn't work with select :-/
                try:
                    self.idx += len(self.port.recv(self.blocklen))
                except socket.timeout:
                    pass
            self.port.settimeout(self._port_timeout)
            logging.debug("ThRecv %s: exit(%d)", self.getName(), self.idx)
        except Exception, ints:
            if not self.quiet:
                raise ints
            logging.debug(ints)


class ThRecvCheck(Thread):
    """
    Random data receiver/checker thread.
    """
    def __init__(self, port, buff, event, blocklen=1024, sendlen=0):
        """
        @param port: Source port.
        @param buff: Control data buffer (FIFO).
        @param length: Amount of data we want to receive.
        @param blocklen: Block length.
        @param sendlen: Block length of the send function (on guest)
        """
        Thread.__init__(self)
        self.port = port
        self.buff = buff
        self.exitevent = event
        self.blocklen = blocklen
        self.idx = 0
        self.sendlen = sendlen + 1  # >=

    def run(self):
        logging.debug("ThRecvCheck %s: run", self.getName())
        attempt = 10
        sendidx = -1
        minsendidx = self.sendlen
        while not self.exitevent.isSet():
            ret = select.select([self.port.sock], [], [], 1.0)
            if ret[0] and (not self.exitevent.isSet()):
                buf = self.port.sock.recv(self.blocklen)
                if buf:
                    # Compare the received data with the control data
                    for char in buf:
                        _char = self.buff.popleft()
                        if char == _char:
                            self.idx += 1
                        else:
                            # TODO BUG: data from the socket on host can
                            # be lost during migration
                            while char != _char:
                                if sendidx > 0:
                                    sendidx -= 1
                                    _char = self.buff.popleft()
                                else:
                                    self.exitevent.set()
                                    logging.error("ThRecvCheck %s: "
                                                  "Failed to recv %dth "
                                                  "character",
                                                  self.getName(), self.idx)
                                    logging.error("ThRecvCheck %s: "
                                                  "%s != %s",
                                                  self.getName(),
                                                  repr(char), repr(_char))
                                    logging.error("ThRecvCheck %s: "
                                                  "Recv = %s",
                                                  self.getName(), repr(buf))
                                    # sender might change the buff :-(
                                    time.sleep(1)
                                    _char = ""
                                    for buf in self.buff:
                                        _char += buf
                                        _char += ' '
                                    logging.error("ThRecvCheck %s: "
                                                  "Queue = %s",
                                                  self.getName(), repr(_char))
                                    logging.info("ThRecvCheck %s: "
                                                "MaxSendIDX = %d",
                                                self.getName(),
                                                (self.sendlen - sendidx))
                                    raise error.TestFail("ThRecvCheck %s: "
                                                         "incorrect data" %
                                                         self.getName())
                    attempt = 10
                else:   # ! buf
                    # Broken socket
                    if attempt > 0:
                        attempt -= 1
                        logging.debug("ThRecvCheck %s: Broken pipe "
                                      "(migration?), reconnecting. ",
                                      self.getName())
                        # TODO BUG: data from the socket on host can be lost
                        if sendidx >= 0:
                            minsendidx = min(minsendidx, sendidx)
                            logging.debug("ThRecvCheck %s: Previous data "
                                          "loss was %d.",
                                          self.getName(),
                                          (self.sendlen - sendidx))
                        sendidx = self.sendlen
                        self.port.is_open = False
                        self.port.open()
        if sendidx >= 0:
            minsendidx = min(minsendidx, sendidx)
        if (self.sendlen - minsendidx):
            logging.error("ThRecvCheck %s: Data loss occured during socket"
                          "reconnection. Maximal loss was %d per one "
                          "migration.", self.getName(),
                          (self.sendlen - minsendidx))
        logging.debug("ThRecvCheck %s: exit(%d)", self.getName(),
                      self.idx)
