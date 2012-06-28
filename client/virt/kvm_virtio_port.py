"""
Interfaces and helpers for the virtio_serial ports.

@copyright: 2012 Red Hat Inc.
"""
from threading import Thread
import aexpect
import logging
import os
import random
import select
import socket
import time
from autotest.client.shared import error
import virt_test_utils


SOCKET_SIZE = 2048


class VirtioPortException(Exception):
    """ General virtio_port exception """
    pass


class VirtioPortFatalException(VirtioPortException):
    """ Fatal virtio_port exception """
    pass


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
        self.port_was_opened = None

    def __str__(self):
        """
        Convert to text.
        """
        return ("%s,%s,%s,%s,%d" % ("Socket", self.name, self.is_console,
                                    self.hostfile, self.is_open()))

    def __getstate__(self):
        """
        socket is unpickable so we need to remove it and say it's closed.
        Used by autotest env.
        """
        # TODO: add port cleanup into kvm_vm.py
        if self.is_open():
            logging.warn("Force closing virtio_port socket, FIX the code to "
                         " close the socket prior this to avoid possible err.")
            self.close()
        return self.__dict__.copy()

    def is_open(self):
        """ @return: host port status (open/closed) """
        if self.sock:
            return True
        else:
            return False

    def for_guest(self):
        """
        Format data for communication with guest side.
        """
        return [self.name, self.is_console]

    def open(self):     # @ReservedAssignment
        """
        Open port on host side.
        """
        if self.is_open():
            return
        attempt = 11
        while attempt > 0:
            try:
                self.sock = socket.socket(socket.AF_UNIX,
                                          socket.SOCK_STREAM)
                self.sock.settimeout(1)
                self.sock.connect(self.hostfile)
                self.sock.setsockopt(1, socket.SO_SNDBUF, SOCKET_SIZE)
                self.sock.settimeout(None)
                self.port_was_opened = True
                return
            except Exception:
                attempt -= 1
                time.sleep(1)
        raise error.TestFail("Can't open the %s sock" % self.name)

    def clean_port(self):
        """
        Clean all data from opened port on host side.
        """
        if self.is_open():
            self.close()
        elif not self.port_was_opened:
            # BUG: Don't even try opening port which was never used. It
            # hangs for ever... (virtio_console bug)
            logging.debug("No need to clean port %s", self)
            return
        logging.debug("Cleaning port %s", self)
        self.open()
        ret = select.select([self.sock], [], [], 1.0)
        if ret[0]:
            buf = self.sock.recv(1024)
            logging.debug("Rest in socket: " + buf)

    def close(self):
        """
        Close port.
        """
        if self.is_open():
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
            self.sock = None

    def mark_as_clean(self):
        """
        Mark port as cleaned
        """
        self.port_was_opened = False


class VirtioSerial(_VirtioPort):
    """ Class for handling virtio-serialport """
    def __init__(self, name, hostfile):
        """
        @param name: Name of port for guest side.
        @param hostfile: Path to port on host side.
        """
        super(VirtioSerial, self).__init__(name, hostfile)
        self.is_console = "no"


class VirtioConsole(_VirtioPort):
    """ Class for handling virtio-console """
    def __init__(self, name, hostfile):
        """
        @param name: Name of port for guest side.
        @param hostfile: Path to port on host side.
        """
        super(VirtioConsole, self).__init__(name, hostfile)
        self.is_console = "yes"


class GuestWorker(object):
    """
    Class for executing "virtio_console_guest" script on guest
    """
    def __init__(self, vm):
        """ Initialize worker for use (including port init on guest) """
        self.vm = vm
        self.session = virt_test_utils.wait_for_login(self.vm)

        timeout = 10
        if self.session.cmd_status('ls /tmp/virtio_console_guest.pyo'):
            # Copy virtio_console_guest.py into guests
            virt_dir = os.path.join(os.environ['AUTODIR'], 'virt')
            vksmd_src = os.path.join(virt_dir, "scripts",
                                     "virtio_console_guest.py")
            dst_dir = "/tmp"

            self.vm.copy_files_to(vksmd_src, dst_dir)

            # Compile and execute worker
            logging.debug("compile virtio_console_guest.py on guest %s",
                          self.vm.name)
            self.cmd("python -OO /tmp/virtio_console_guest.py -c "
                     "&& echo -n 'PASS: Compile virtio_guest finished' || "
                     "echo -n 'FAIL: Compile virtio_guest failed'", timeout)
            self.session.sendline()

        logging.debug("Starting virtio_console_guest.py on guest %s",
                      self.vm.name)
        self._execute_worker(timeout)
        self._init_guest(timeout)

    def _execute_worker(self, timeout=10):
        """ Execute worker on guest """
        self.cmd("python /tmp/virtio_console_guest.pyo && "
                 "echo -n 'PASS: virtio_guest finished' || "
                 "echo -n 'FAIL: virtio_guest failed'", timeout)
        # Let the system rest
        # FIXME: Is this always necessarily?
        time.sleep(2)

    def _init_guest(self, timeout=10):
        """ Initialize worker on guest """
        ports = []
        for port in self.vm.virtio_ports:
            ports.append(port.for_guest())
        self.cmd("virt.init(%s)" % (ports), timeout)

    def reconnect(self, vm, timeout=10):
        """
        Reconnect to guest_worker (eg. after migration)
        @param vm: New VM object
        """
        self.vm = vm
        self.session = virt_test_utils.wait_for_login(self.vm)
        self._execute_worker(timeout)

    def cmd(self, cmd, timeout=10):
        """
        Wrapper around the self.cmd command which executes the command on
        guest. Unlike self._cmd command when the command fails it raises the
        test error.
        @param command: Command that will be executed.
        @param timeout: Timeout used to verify expected output.
        @return: Tuple (match index, data)
        """
        match, data = self._cmd(cmd, timeout)
        if match == 1 or match is None:
            raise VirtioPortException("Failed to execute '%s' on"
                                      " virtio_console_guest.py, "
                                      "vm: %s, output:\n%s" %
                                      (cmd, self.vm.name, data))
        return (match, data)

    def _cmd(self, cmd, timeout=10):
        """
        Execute given command inside the script's main loop.
        @param command: Command that will be executed.
        @param timeout: Timeout used to verify expected output.
        @return: Tuple (match index, data)
        """
        logging.debug("Executing '%s' on virtio_console_guest.py,"
                      " vm: %s, timeout: %s", cmd, self.vm.name, timeout)
        self.session.sendline(cmd)
        try:
            (match, data) = self.session.read_until_last_line_matches(
                                                ["PASS:", "FAIL:"], timeout)

        except aexpect.ExpectError, inst:
            match = None
            data = "Cmd process timeout. Data in console: " + inst.output

        self.vm.verify_kernel_crash()

        return (match, data)

    def _cleanup_ports(self):
        """
        Read all data from all ports, in both sides of each port.
        """
        for port in self.vm.virtio_ports:
            openned = port.is_open()
            port.clean_port()
            self.cmd("virt.clean_port('%s'),1024" % port.name, 10)
            if not openned:
                port.close()
                self.cmd("virt.close('%s'),1024" % port.name, 10)

    def safe_exit_loopback_threads(self, send_pts, recv_pts):
        """
        Safely executes on_guest("virt.exit_threads()") using workaround of
        the stuck thread in loopback in mode=virt.LOOP_NONE .
        @param send_pts: list of possible send sockets we need to work around.
        @param recv_pts: list of possible recv sockets we need to read-out.
        """
        # in LOOP_NONE mode it might stuck in read/write
        match, tmp = self._cmd("virt.exit_threads()", 3)
        if match is None:
            logging.warn("Workaround the stuck thread on guest")
            # Thread is stuck in read/write
            for send_pt in send_pts:
                send_pt.sock.sendall(".")
        elif match != 0:
            # Something else
            raise VirtioPortException("Unexpected fail\nMatch: %s\nData:\n%s"
                                      % (match, tmp))

        # Read-out all remaining data
        for recv_pt in recv_pts:
            while select.select([recv_pt.sock], [], [], 0.1)[0]:
                recv_pt.sock.recv(1024)

        # This will cause fail in case anything went wrong.
        self.cmd("print 'PASS: nothing'", 10)

    def cleanup_ports(self):
        """
        Clean state of all ports and set port to default state.
        Default state:
           No data on port or in port buffer.
           Read mode = blocking.
        """
        # Check if python is still alive
        match, tmp = self._cmd("is_alive()", 10)
        if (match is None) or (match != 0):
            logging.error("Python died/is stuck/have remaining threads")
            logging.debug(tmp)
            try:
                self.vm.verify_kernel_crash()

                match, tmp = self._cmd("guest_exit()", 10)
                if (match is None) or (match == 0):
                    self.session.close()
                    self.session = virt_test_utils.wait_for_login(self.vm)
                self.cmd("killall -9 python "
                         "&& echo -n PASS: python killed"
                         "|| echo -n PASS: python was already dead", 10)

                self._init_guest()
                self._cleanup_ports()

            except Exception, inst:
                logging.error(inst)
                raise VirtioPortFatalException("virtio-console driver is "
                            "irreparably blocked, further tests might FAIL.")

    def cleanup(self):
        """ Cleanup ports and quit the worker """
        # Verify that guest works
        if self.session:
            self.cleanup_ports()
        if self.vm:
            self.vm.verify_kernel_crash()
        # Quit worker
        if self.session and self.vm:
            self.cmd("guest_exit()", 10)
        self.session = None
        self.vm = None


class ThSend(Thread):
    """
    Random data sender thread.
    """
    def __init__(self, port, data, exit_event, quiet=False):
        """
        @param port: Destination port.
        @param data: The data intend to be send in a loop.
        @param exit_event: Exit event.
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
        self.exitevent = exit_event
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
    def __init__(self, port, exit_event, queues, blocklen=1024,
                 migrate_event=None):
        """
        @param port: Destination port
        @param exit_event: Exit event
        @param queues: Queues for the control data (FIFOs)
        @param blocklen: Block length
        @param migrate_event: Event indicating port was changed and is ready.
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
        self.exitevent = exit_event
        self.migrate_event = migrate_event
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
                            if self.migrate_event is None:
                                self.exitevent.set()
                                raise error.TestFail("ThSendCheck %s: Broken "
                                        "pipe. If this is expected behavior "
                                        "set migrate_event to support "
                                        "reconnection." % self.getName())
                            logging.debug("ThSendCheck %s: Broken pipe "
                                          ", reconnecting. ", self.getName())
                            attempt = 10
                            while (attempt > 1
                                   and not self.exitevent.isSet()):
                                # Wait until main thread sets the new self.port
                                if not self.migrate_event.wait(30):
                                    self.exitevent.set()
                                    raise error.TestFail("ThSendCheck %s: "
                                            "Timeout while waiting for "
                                            "migrate_event" % self.getName())
                                self.port.sock = False
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
    Receives data and throws it away.
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
    def __init__(self, port, buff, exit_event, blocklen=1024, sendlen=0,
                 migrate_event=None):
        """
        @param port: Source port.
        @param buff: Control data buffer (FIFO).
        @param exit_event: Exit event.
        @param blocklen: Block length.
        @param sendlen: Block length of the send function (on guest)
        @param migrate_event: Event indicating port was changed and is ready.
        """
        Thread.__init__(self)
        self.port = port
        self.buff = buff
        self.exitevent = exit_event
        self.migrate_event = migrate_event
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
                        if self.migrate_event is None:
                            self.exitevent.set()
                            raise error.TestFail("ThRecvCheck %s: Broken pipe."
                                    " If this is expected behavior set migrate"
                                    "_event to support reconnection." %
                                    self.getName())
                        logging.debug("ThRecvCheck %s: Broken pipe "
                                      ", reconnecting. ", self.getName())
                        # TODO BUG: data from the socket on host can be lost
                        if sendidx >= 0:
                            minsendidx = min(minsendidx, sendidx)
                            logging.debug("ThRecvCheck %s: Previous data "
                                          "loss was %d.",
                                          self.getName(),
                                          (self.sendlen - sendidx))
                        sendidx = self.sendlen
                        # Wait until main thread sets the new self.port
                        if not self.migrate_event.wait(30):
                            self.exitevent.set()
                            raise error.TestFail("ThRecvCheck %s: Timeout "
                                            "while waiting for migrate_event"
                                            % self.getName())

                        self.port.sock = False
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
