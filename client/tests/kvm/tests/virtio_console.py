"""
virtio_console test

@copyright: 2010 Red Hat, Inc.
"""
import array, logging, os, random, re, select, shutil, socket, sys, tempfile
import threading, time, traceback
from collections import deque
from threading import Thread

from autotest.client.shared import error
from autotest.client import utils
from autotest.client.virt import virt_test_utils, kvm_monitor, virt_env_process
from autotest.client.virt import aexpect, kvm_virtio_port


def run_virtio_console(test, params, env):
    """
    KVM virtio_console test

    1) Starts VMs with the specified number of virtio console devices
    2) Start smoke test
    3) Start loopback test
    4) Start performance test

    This test uses an auxiliary script, virtio_console_guest.py, that is copied
    to guests. This script has functions to send and write data to virtio
    console ports. Details of each test can be found on the docstrings for the
    test_* functions.

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment
    """
    class SubTest(object):
        """
        Collect result of subtest of main test.
        """
        def __init__(self):
            """
            Initialize object
            """
            self.result = []
            self.passed = 0
            self.failed = 0
            self.cleanup_func = None
            self.cleanup_args = None


        def set_cleanup_func(self, func, args):
            """
            Set cleanup function which is called when subtest fails.

            @param func: Function which should be called when test fails.
            @param args: Arguments of cleanup function.
            """
            self.cleanup_func = func
            self.cleanup_args = args


        def get_cleanup_func(self):
            """
            Returns the tupple of cleanup_func and clenaup_args

            @return: Tupple of self.cleanup_func and self.cleanup_args
            """
            return (self.cleanup_func, self.cleanup_args)


        def do_test(self, function, args=None, fatal=False, cleanup=True):
            """
            Execute subtest function.

            @param function: Object of function.
            @param args: List of arguments of function.
            @param fatal: If true exception is forwarded to main test.
            @param cleanup: If true call cleanup function after crash of test.
            @return: Return what returned executed subtest.
            @raise TestError: If collapse of test is fatal raise forward
                        exception from subtest.
            """
            if args is None:
                args = []
            res = [None, function.func_name, args]
            try:
                logging.info("Starting test %s" % function.func_name)
                ret = function(*args)
                res[0] = True
                logging.info(self.result_to_string(res))
                self.result.append(res)
                self.passed += 1
                return ret
            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                logging.error("In function (" + function.func_name + "):")
                logging.error("Call from:\n" +
                              traceback.format_stack()[-2][:-1])
                logging.error("Exception from:\n" +
                              "".join(traceback.format_exception(
                                                        exc_type, exc_value,
                                                        exc_traceback.tb_next)))
                # Clean up environment after subTest crash
                res[0] = False
                logging.info(self.result_to_string(res))
                self.result.append(res)
                self.failed += 1

                if cleanup:
                    try:
                        self.cleanup_func(*self.cleanup_args)
                    except Exception:
                        error.TestFail("Cleanup function crashed as well")
                if fatal:
                    raise


        def is_failed(self):
            """
            @return: If any of subtest not pass return True.
            """
            if self.failed > 0:
                return True
            else:
                return False


        def get_result(self):
            """
            @return: Result of subtests.
               Format:
                 tuple(pass/fail,function_name,call_arguments)
            """
            return self.result


        def result_to_string_debug(self, result):
            """
            @param result: Result of test.
            """
            sargs = ""
            for arg in result[2]:
                sargs += str(arg) + ","
            sargs = sargs[:-1]
            if result[0]:
                status = "PASS"
            else:
                status = "FAIL"
            return ("Subtest (%s(%s)): --> %s") % (result[1], sargs, status)


        def result_to_string(self, result):
            """
            @param result: Result of test.
            """
            if result[0]:
                status = "PASS"
            else:
                status = "FAIL"
            return ("Subtest (%s): --> %s") % (result[1], status)


        def headline(self, msg):
            """
            Add headline to result output.

            @param msg: Test of headline
            """
            self.result.append([msg])


        def _gen_res(self, format_func):
            """
            Format result with formatting function

            @param format_func: Func for formating result.
            """
            result = ""
            for res in self.result:
                if (len(res) == 3):
                    result += format_func(res) + "\n"
                else:
                    result += res[0] + "\n"
            return result


        def get_full_text_result(self):
            """
            @return string with text form of result
            """
            return self._gen_res(lambda str: self.result_to_string_debug(str))


        def get_text_result(self):
            """
            @return string with text form of result
            """
            return self._gen_res(lambda str: self.result_to_string(str))


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
                    for i in range(self.blocklen):
                        ch = "%c" % random.randrange(255)
                        buf += ch
                        for queue in self.queues:
                            queue.append(ch)
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
        def __init__(self, port, buffer, event, blocklen=1024, sendlen=0):
            """
            @param port: Source port.
            @param buffer: Control data buffer (FIFO).
            @param length: Amount of data we want to receive.
            @param blocklen: Block length.
            @param sendlen: Block length of the send function (on guest)
            """
            Thread.__init__(self)
            self.port = port
            self.buffer = buffer
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
                        for ch in buf:
                            ch_ = self.buffer.popleft()
                            if ch == ch_:
                                self.idx += 1
                            else:
                                # TODO BUG: data from the socket on host can
                                # be lost during migration
                                while ch != ch_:
                                    if sendidx > 0:
                                        sendidx -= 1
                                        ch_ = self.buffer.popleft()
                                    else:
                                        self.exitevent.set()
                                        logging.error("ThRecvCheck %s: "
                                                      "Failed to recv %dth "
                                                      "character",
                                                      self.getName(), self.idx)
                                        logging.error("ThRecvCheck %s: "
                                                      "%s != %s",
                                                      self.getName(),
                                                      repr(ch), repr(ch_))
                                        logging.error("ThRecvCheck %s: "
                                                      "Recv = %s",
                                                      self.getName(), repr(buf))
                                        # sender might change the buffer :-(
                                        time.sleep(1)
                                        ch_ = ""
                                        for buf in self.buffer:
                                            ch_ += buf
                                            ch_ += ' '
                                        logging.error("ThRecvCheck %s: "
                                                      "Queue = %s",
                                                      self.getName(), repr(ch_))
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


    def process_stats(stats, scale=1.0):
        """
        Process and print the stats.

        @param stats: List of measured data.
        """
        if not stats:
            return None
        for i in range((len(stats) - 1), 0, -1):
            stats[i] = stats[i] - stats[i - 1]
            stats[i] /= scale
        stats[0] /= scale
        stats = sorted(stats)
        return stats


    def _init_guest(vm, timeout=10):
        """
        Execute virtio_console_guest.py on guest, wait until it is initialized.

        @param vm: Informations about the guest.
        @param timeout: Timeout that will be used to verify if the script
                started properly.
        """
        logging.debug("compile virtio_console_guest.py on guest %s",
                      vm[0].name)

        (match, data) = _on_guest("python -OO /tmp/virtio_console_guest.py -c"
                       "&& echo -n 'PASS: Compile virtio_guest finished' ||"
                       "echo -n 'FAIL: Compile virtio_guest failed'",
                        vm, timeout)

        if match != 0:
            raise error.TestFail("Command console_switch.py on guest %s "
                                 "failed.\nreturn code: %s\n output:\n%s" %
                                 (vm[0].name, match, data))
        logging.debug("Starting virtio_console_guest.py on guest %s",
                      vm[0].name)
        vm[1].sendline()
        (match, data) = _on_guest("python /tmp/virtio_console_guest.pyo &&"
                       "echo -n 'PASS: virtio_guest finished' ||"
                       "echo -n 'FAIL: virtio_guest failed'",
                       vm, timeout)
        if match != 0:
            raise error.TestFail("Command console_switch.py on guest %s "
                                 "failed.\nreturn code: %s\n output:\n%s" %
                                 (vm[0].name, match, data))
        # Let the system rest
        time.sleep(2)


    def init_guest(vm, consoles):
        """
        Prepares guest, executes virtio_console_guest.py and initializes test.

        @param vm: Informations about the guest.
        @param consoles: Informations about consoles.
        """
        conss = []
        for mode in consoles:
            for cons in mode:
                conss.append(cons.for_guest())
        _init_guest(vm, 10)
        on_guest("virt.init(%s)" % (conss), vm, 10)


    def _search_kernel_crashlog(vm_port, timeout=2):
        """
        Find kernel crash message.

        @param vm_port : Guest output port.
        @param timeout: Timeout used to verify expected output.

        @return: Kernel crash log or None.
        """
        data = vm_port.read_nonblocking(0.1, timeout)
        match = re.search("BUG:", data, re.MULTILINE)
        if match is None:
            return None

        match = re.search(r"BUG:.*---\[ end trace .* \]---",
                  data, re.DOTALL |re.MULTILINE)
        if match is None:
            data += vm_port.read_until_last_line_matches(
                                ["---\[ end trace .* \]---"],timeout)

        match = re.search(r"(BUG:.*---\[ end trace .* \]---)",
                  data, re.DOTALL |re.MULTILINE)
        return match.group(0)



    def _on_guest(command, vm, timeout=2):
        """
        Execute given command inside the script's main loop, indicating the vm
        the command was executed on.

        @param command: Command that will be executed.
        @param vm: Informations about the guest.
        @param timeout: Timeout used to verify expected output.

        @return: Tuple (match index, data, kernel_crash)
        """
        logging.debug("Executing '%s' on virtio_console_guest.py loop," +
                      " vm: %s, timeout: %s", command, vm[0].name, timeout)
        vm[1].sendline(command)
        try:
            (match, data) = vm[1].read_until_last_line_matches(["PASS:",
                                                                "FAIL:"],
                                                               timeout)

        except aexpect.ExpectError, e:
            match = None
            data = "Cmd process timeout. Data in console: " + e.output

        kcrash_data = _search_kernel_crashlog(vm[3])
        if kcrash_data is not None:
            logging.error(kcrash_data)
            vm[4] = True

        return (match, data)


    def on_guest(command, vm, timeout=2):
        """
        Wrapper around the _on_guest command which executes the command on
        guest. Unlike _on_guest command when the command fails it raises the
        test error.

        @param command: Command that will be executed.
        @param vm: Informations about the guest.
        @param timeout: Timeout used to verify expected output.

        @return: Tuple (match index, data)
        """
        match, data = _on_guest(command, vm, timeout)
        if match == 1 or match is None:
            raise error.TestFail("Failed to execute '%s' on"
                                 " virtio_console_guest.py, "
                                 "vm: %s, output:\n%s" %
                                 (command, vm[0].name, data))

        return (match, data)


    def _guest_exit_threads(vm, send_pts, recv_pts):
        """
        Safely executes on_guest("virt.exit_threads()") using workaround of
        the stuck thread in loopback in mode=virt.LOOP_NONE .

        @param vm: Informations about the guest.
        @param send_pts: list of possible send sockets we need to work around.
        @param recv_pts: list of possible recv sockets we need to read-out.
        """
        # in LOOP_NONE mode it might stuck in read/write
        match, tmp = _on_guest("virt.exit_threads()", vm, 10)
        if match is None:
            logging.debug("Workaround the stuck thread on guest")
            # Thread is stucked in read/write
            for send_pt in send_pts:
                send_pt.sock.sendall(".")
        elif match != 0:
            # Something else
            raise error.TestFail("Unexpected fail\nMatch: %s\nData:\n%s"
                                 % (match, tmp))

        # Read-out all remaining data
        for recv_pt in recv_pts:
            while select.select([recv_pt.sock], [], [], 0.1)[0]:
                recv_pt.sock.recv(1024)

        # This will cause fail in case anything went wrong.
        on_guest("print 'PASS: nothing'", vm, 10)


    def _vm_create(no_console=3, no_serialport=3, spread=True):
        """
        Creates the VM and connects the specified number of consoles and serial
        ports.
        Ports are allocated by 2 per 1 virtio-serial-pci device starting with
        console. (3+2 => CC|CS|S; 0+2 => SS; 3+4 => CC|CS|SS|S, ...) This way
        it's easy to test communication on the same or different
        virtio-serial-pci device.
        Further in tests the consoles are being picked always from the first
        available one (3+2: 2xC => CC|cs|s <communication on the same PCI>;
        2xC,1xS => CC|cS|s <communication between 2 PCI devs)

        @param no_console: Number of desired virtconsoles.
        @param no_serialport: Number of desired virtserialports.
        @return: Tuple with (guest information, consoles information)
                guest informations = [vm, session, tmp_dir, kcrash]
                consoles informations = [consoles[], serialports[]]
        """
        consoles = []
        serialports = []
        tmp_dir = tempfile.mkdtemp(prefix="virtio-console-", dir="/tmp/")
        params['extra_params'] = standard_extra_params

        if not spread:
            pci = "virtio-serial-pci0"
            params['extra_params'] += (" -device virtio-serial-pci,id="
                                           + pci)
            pci += ".0"
        for i in range(0, no_console):
            # Spread consoles between multiple PCI devices (2 per a dev)
            if not i % 2 and spread:
                pci = "virtio-serial-pci%d" % (i / 2)
                params['extra_params'] += (" -device virtio-serial-pci,id="
                                           + pci)
                pci += ".0"
            params['extra_params'] += (" -chardev socket,path=%s/%d,id=vc%d,"
                                       "server,nowait" % (tmp_dir, i, i))
            params['extra_params'] += (" -device virtconsole,chardev=vc%d,"
                                      "name=console-%d,id=console-%d,bus=%s"
                                      % (i, i, i, pci))

        for i in  range(no_console, no_console + no_serialport):
            # Spread serial ports between multiple PCI devices (2 per each dev)
            if not i % 2  and spread:
                pci = "virtio-serial-pci%d" % (i / 2)
                params['extra_params'] += (" -device virtio-serial-pci,id="
                                           + pci)
                pci += ".0"
            params['extra_params'] += (" -chardev socket,path=%s/%d,id=vs%d,"
                                       "server,nowait" % (tmp_dir, i, i))
            params['extra_params'] += (" -device virtserialport,chardev=vs%d,"
                                       "name=serialport-%d,id=serialport-%d,"
                                       "bus=%s" % (i, i, i, pci))

        (vm, session, sserial) = _restore_vm()

        # connect the sockets
        for i in range(0, no_console):
            consoles.append(kvm_virtio_port.VirtioConsole("console-%d" % i,
                                                    "%s/%d" % (tmp_dir, i)))
        for i in range(no_console, no_console + no_serialport):
            serialports.append(kvm_virtio_port.VirtioSerial(
                                                    "serialport-%d" % i,
                                                    "%s/%d" % (tmp_dir, i)))

        kcrash = False

        return [vm, session, tmp_dir, sserial, kcrash], [consoles, serialports]


    def _restore_vm():
        """
        Restore old virtual machine when VM is destroyed.
        """
        logging.debug("Booting guest %s", params.get("main_vm"))
        virt_env_process.preprocess_vm(test, params, env,
                                        params.get("main_vm"))

        vm = env.get_vm(params.get("main_vm"))

        kernel_bug = None
        try:
            session = virt_test_utils.wait_for_login(vm, 0,
                                    float(params.get("boot_timeout", 100)),
                                    0, 2)
        except (error.TestFail):
            kernel_bug = _search_kernel_crashlog(vm.serial_console, 10)
            if kernel_bug is not None:
                logging.error(kernel_bug)
            raise

        kernel_bug = _search_kernel_crashlog(vm.serial_console, 10)
        if kernel_bug is not None:
            logging.error(kernel_bug)

        sserial = virt_test_utils.wait_for_login(vm, 0,
                                         float(params.get("boot_timeout", 20)),
                                         0, 2, serial=True)
        return [vm, session, sserial]


    def topen(vm, port):
        """
        Open virtioconsole port.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param port: Port identifier.
        """
        on_guest("virt.open('%s')" % (port.name), vm, 10)
        port.open()


    def tcheck_zero_sym(vm):
        """
        Check if port /dev/vport0p0 was created.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        """
        on_guest("virt.check_zero_sym()", vm, 10)


    def tmulti_open(vm, port):
        """
        Multiopen virtioconsole port.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param port: Port identifier.
        """
        on_guest("virt.close('%s')" % (port.name), vm, 10)
        on_guest("virt.open('%s')" % (port.name), vm, 10)
        (match, data) = _on_guest("virt.open('%s')" % (port.name), vm, 10)
        # Console is permitted to open the device multiple times
        if port.port_type == "yes": #is console?
            if match != 0: #Multiopen not pass
                raise error.TestFail("Unexpected fail of opening the console"
                                     " device for the 2nd time.\n%s" % data)
        else:
            if match != 1: #Multiopen not fail:
                raise error.TestFail("Unexpetded pass of opening the"
                                     " serialport device for the 2nd time.")
            elif not "[Errno 24]" in data:
                raise error.TestFail("Multiple opening fail but with another"
                                     " exception %s" % data)
        port.open()


    def tclose(vm, port):
        """
        Close socket.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param port: Port to open.
        """
        on_guest("virt.close('%s')" % (port.name), vm, 10)
        port.close()


    def tpolling(vm, port):
        """
        Test try polling function.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param port: Port used in test.
        """
        # Poll (OUT)
        on_guest("virt.poll('%s', %s)" % (port.name, select.POLLOUT), vm,
                 2)

        # Poll (IN, OUT)
        port.sock.sendall("test")
        for test in [select.POLLIN, select.POLLOUT]:
            on_guest("virt.poll('%s', %s)" % (port.name, test), vm, 10)

        # Poll (IN HUP)
        # I store the socket informations and close the socket
        port.close()
        for test in [select.POLLIN, select.POLLHUP]:
            on_guest("virt.poll('%s', %s)" % (port.name, test), vm, 10)

        # Poll (HUP)
        on_guest("virt.recv('%s', 4, 1024, False)" % (port.name), vm, 10)
        on_guest("virt.poll('%s', %s)" % (port.name, select.POLLHUP), vm,
                 2)

        # Reconnect the socket
        port.open()
        # Redefine socket in consoles
        on_guest("virt.poll('%s', %s)" % (port.name, select.POLLOUT), vm,
                 2)


    def tsigio(vm, port):
        """
        Test try sigio function.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param port: Port used in test.
        """
        if port.is_open:
            port.close()

        # Enable sigio on specific port
        on_guest("virt.async('%s', True, 0)" %
                 (port.name) , vm, 10)
        on_guest("virt.get_sigio_poll_return('%s')" % (port.name) , vm, 10)

        #Test sigio when port open
        on_guest("virt.set_pool_want_return('%s', select.POLLOUT)" %
                 (port.name), vm, 10)
        port.open()
        match = _on_guest("virt.get_sigio_poll_return('%s')" %
                          (port.name) , vm, 10)[0]
        if match == 1:
            raise error.TestFail("Problem with HUP on console port.")

        #Test sigio when port receive data
        on_guest("virt.set_pool_want_return('%s', select.POLLOUT |"
                 " select.POLLIN)" % (port.name), vm, 10)
        port.sock.sendall("0123456789")
        on_guest("virt.get_sigio_poll_return('%s')" % (port.name) , vm, 10)

        #Test sigio port close event
        on_guest("virt.set_pool_want_return('%s', select.POLLHUP |"
                 " select.POLLIN)" % (port.name), vm, 10)
        port.close()
        on_guest("virt.get_sigio_poll_return('%s')" % (port.name) , vm, 10)

        #Test sigio port open event and persistence of written data on port.
        on_guest("virt.set_pool_want_return('%s', select.POLLOUT |"
                 " select.POLLIN)" % (port.name), vm, 10)
        port.open()
        on_guest("virt.get_sigio_poll_return('%s')" % (port.name) , vm, 10)

        #Test event when erase data.
        on_guest("virt.clean_port('%s')" % (port.name), vm, 10)
        port.close()
        on_guest("virt.set_pool_want_return('%s', select.POLLOUT)"
                 % (port.name), vm, 10)
        port.open()
        on_guest("virt.get_sigio_poll_return('%s')" % (port.name) , vm, 10)

        # Disable sigio on specific port
        on_guest("virt.async('%s', False, 0)" %
                 (port.name) , vm, 10)


    def tlseek(vm, port):
        """
        Tests the correct handling of lseek (expected fail)

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param port: Port used in test.
        """
        # The virt.lseek returns PASS when the seek fails
        on_guest("virt.lseek('%s', 0, 0)" % (port.name), vm, 10)


    def trw_host_offline(vm, port):
        """
        Guest read/write from host when host is disconnected.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param port: Port used in test.
        """
        if port.is_open:
            port.close()

        on_guest("virt.recv('%s', 0, 1024, False)" % port.name, vm, 10)
        match, tmp = _on_guest("virt.send('%s', 10, True)" % port.name,
                                                             vm, 10)
        if match is not None:
            raise error.TestFail("Write on guest while host disconnected "
                                 "didn't time out.\nOutput:\n%s"
                                 % tmp)

        port.open()

        if (port.sock.recv(1024) < 10):
            raise error.TestFail("Didn't received data from guest")
        # Now the _on_guest("virt.send('%s'... command should be finished
        on_guest("print('PASS: nothing')", vm, 10)


    def trw_host_offline_big_data(vm, port):
        """
        Guest read/write from host when host is disconnected.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param port: Port used in test.
        """
        if port.is_open:
            port.close()

        port.clean_port()
        port.close()
        on_guest("virt.clean_port('%s'),1024" % port.name, vm, 10)
        match, tmp = _on_guest("virt.send('%s', (1024**3)*3, True, "
                               "is_static=True)" % port.name, vm, 30)
        if match is None:
            raise error.TestFail("Write on guest while host disconnected "
                                 "didn't time out.\nOutput:\n%s"
                                 % tmp)

        time.sleep(20)

        port.open()

        rlen = 0
        while rlen < (1024**3*3):
            ret = select.select([port.sock], [], [], 10.0)
            if (ret[0] != []):
                rlen += len(port.sock.recv(((4096))))
            elif rlen != (1024**3*3):
                raise error.TestFail("Not all data was received,"
                                     "only %d from %d" % (rlen, 1024**3*3))
        on_guest("print('PASS: nothing')", vm, 10)


    def trw_notconnect_guest(vm, port, consoles):
        """
        Host send data to guest port and guest not read any data from port.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param port: Port used in test.
        """
        vm[0].destroy(gracefully = False)
        (vm[0], vm[1], vm[3]) = _restore_vm()
        if not port.is_open:
            port.open()
        else:
            port.close()
            port.open()

        port.sock.settimeout(20.0)

        loads = utils.SystemLoad([(os.getpid(), 'autotest'),
                                  (vm[0].get_pid(), 'VM'), 0])
        loads.start()

        try:
            sent1 = 0
            for i in range(1000000):
                sent1 += port.sock.send("a")
        except socket.timeout:
            logging.info("Data sending to closed port timed out.")

        logging.info("Bytes sent to client: %d" % (sent1))
        logging.info("\n" + loads.get_cpu_status_string()[:-1])

        on_guest('echo -n "PASS:"', vm, 10)

        logging.info("Open and then close port %s" % (port.name))
        init_guest(vm, consoles)
        # Test of live and open and close port again
        _clean_ports(vm, consoles)
        on_guest("virt.close('%s')" % (port.name), vm, 10)

        # With serialport it is a different behavior
        on_guest("guest_exit()", vm, 10)
        port.sock.settimeout(20.0)

        loads.start()
        try:
            sent2 = 0
            for i in range(40000):
                sent2 = port.sock.send("a")
        except socket.timeout:
            logging.info("Data sending to closed port timed out.")

        logging.info("Bytes sent to client: %d" % (sent2))
        logging.info("\n" + loads.get_cpu_status_string()[:-1])
        loads.stop()
        if (sent1 != sent2):
            logging.warning("Inconsistent behavior: First sent %d bytes and "
                            "second sent %d bytes" % (sent1, sent2))

        port.sock.settimeout(None)
        (vm[0], vm[1], vm[3]) = _restore_vm()

        init_guest(vm, consoles)
        _clean_ports(vm, consoles)


    def trw_blocking_mode(vm, port):
        """
        Guest read\write data in blocking mode.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param port: Port used in test.
        """
        # Blocking mode
        if not port.is_open:
            port.open()
        on_guest("virt.blocking('%s', True)" % port.name, vm, 10)
        # Recv should timed out
        match, tmp = _on_guest("virt.recv('%s', 10, 1024, False)" %
                               port.name, vm, 10)
        if match == 0:
            raise error.TestFail("Received data even when none was sent\n"
                                 "Data:\n%s" % tmp)
        elif match is not None:
            raise error.TestFail("Unexpected fail\nMatch: %s\nData:\n%s" %
                                 (match, tmp))
        port.sock.sendall("1234567890")
        # Now guest received the data end escaped from the recv()
        on_guest("print('PASS: nothing')", vm, 10)


    def trw_nonblocking_mode(vm, port):
        """
        Guest read\write data in nonblocking mode.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param port: Port used in test.
        """
        # Non-blocking mode
        if not port.is_open:
            port.open()
        on_guest("virt.blocking('%s', False)" % port.name, vm, 10)
        # Recv should return FAIL with 0 received data
        match, tmp = _on_guest("virt.recv('%s', 10, 1024, False)" %
                              port.name, vm, 10)
        if match == 0:
            raise error.TestFail("Received data even when none was sent\n"
                                 "Data:\n%s" % tmp)
        elif match is None:
            raise error.TestFail("Timed out, probably in blocking mode\n"
                                 "Data:\n%s" % tmp)
        elif match != 1:
            raise error.TestFail("Unexpected fail\nMatch: %s\nData:\n%s" %
                                 (match, tmp))
        port.sock.sendall("1234567890")
        on_guest("virt.recv('%s', 10, 1024, False)" % port.name, vm, 10)


    def tbasic_loopback(vm, send_port, recv_port, data="Smoke test data"):
        """
        Easy loop back test with loop over only two ports.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param port: Port used in test.
        """
        if not send_port.is_open:
            send_port.open()
        if not recv_port.is_open:
            recv_port.open()
        on_guest("virt.loopback(['%s'], ['%s'], 1024, virt.LOOP_NONE)" %
                     (send_port.name, recv_port.name), vm, 10)
        send_port.sock.sendall(data)
        tmp = ""
        i = 0
        while i <= 10:
            i += 1
            ret = select.select([recv_port.sock], [], [], 1.0)
            if ret:
                tmp += recv_port.sock.recv(1024)
            if len(tmp) >= len(data):
                break
        if tmp != data:
            raise error.TestFail("Incorrect data: '%s' != '%s'",
                                 data, tmp)
        _guest_exit_threads(vm, [send_port], [recv_port])


    def trmmod(vm, consoles):
        """
        Remove and load virtio_console kernel modules.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Consoles which should be close before rmmod.
        """
        on_guest("guest_exit()", vm, 5)

        on_guest("rmmod -f virtio_console && echo -n PASS: rmmod "
                 "|| echo -n FAIL: rmmod", vm, 10)
        on_guest("modprobe virtio_console "
                 "&& echo -n PASS: modprobe || echo -n FAIL: modprobe",
                 vm, 10)

        init_guest(vm, consoles)
        try:
            cname = consoles[0][0].name
        except (IndexError):
            cname = consoles[1][0].name
        on_guest("virt.clean_port('%s'),1024" % cname, vm, 2)


    def tmax_serial_ports(vm, consoles):
        """
        Test maximum count of ports in guest machine.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Consoles which should be close before rmmod.
        """
        logging.debug("Count of serial ports: 30")
        vm[0].destroy(gracefully = False)
        (vm, consoles) = _vm_create(0, 30, False)
        try:
            init_guest(vm, consoles)
        except error.TestFail, ints:
            logging.info("Count of serial ports: 30")
            raise ints
        clean_reload_vm(vm, consoles, expected=True)


    def tmax_console_ports(vm, consoles):
        """
        Test maximum count of ports in guest machine.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Consoles which should be close before rmmod.
        """
        logging.debug("Count of console ports: 30")
        vm[0].destroy(gracefully = False)
        (vm, consoles) = _vm_create(30, 0, False)
        try:
            init_guest(vm, consoles)
        except error.TestFail, ints:
            logging.info("Count of console ports: 30")
            raise ints
        clean_reload_vm(vm, consoles, expected=True)


    def tmax_mix_serial_conosle_port(vm, consoles):
        """
        Test maximim count of ports in guest machine.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Consoles which should be close before rmmod.
        """
        logging.debug("Count of ports (serial+console): 30")
        vm[0].destroy(gracefully = False)
        (vm, consoles) = _vm_create(15, 15, False)
        try:
            init_guest(vm, consoles)
        except error.TestFail, ints:
            logging.info("Count of ports (serial+console): 30")
            raise ints
        clean_reload_vm(vm, consoles, expected=True)


    def tshutdown(vm, consoles):
        """
        Try to gently shutdown the machine. Virtio_console shouldn't block this.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Consoles which should be close before rmmod.
        """
        ports = []
        for console in consoles[0]:
            ports.append(console)
        for console in consoles[1]:
            ports.append(console)
        for port in ports:
            port.open()
        # If more than one, send data on the other ports
        for port in ports[1:]:
            on_guest("virt.close('%s')" % (port.name), vm, 2)
            on_guest("virt.open('%s')" % (port.name), vm, 2)
            try:
                os.system("dd if=/dev/random of='%s' bs=4096 &>/dev/null &"
                          % port.path)
            except Exception:
                pass
        # Just start sending, it won't finish anyway...
        _on_guest("virt.send('%s', 1024**3, True, is_static=True)"
                  % ports[0].name, vm, 1)

        # Let the computer transfer some bytes :-)
        time.sleep(2)

        # Power off the computer
        vm[0].destroy(gracefully=True)
        clean_reload_vm(vm, consoles, expected=True)


    def __tmigrate(vm, consoles, parms, offline=True):
        """
        An actual migration test. It creates loopback on guest from first port
        to all remaining ports. Than it sends and validates the data.
        During this it tries to migrate the vm n-times.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Field of virtio ports with the minimum of 2 items.
        @param parms: [media, no_migration, send-, recv-, loopback-buffer_len]
        """
        # PREPARE
        send_pt = consoles[parms[0]][0]
        recv_pts = consoles[parms[0]][1:]
        # TODO BUG: sendlen = max allowed data to be lost per one migration
        # TODO BUG: using SMP the data loss is upto 4 buffers
        # 2048 = char. dev. socket size, parms[2] = host->guest send buffer size
        sendlen = 2*2*max(2048, parms[2])
        if not offline: # TODO BUG: online migration causes more loses
            # TODO: Online migration lose n*buffer. n depends on the console
            # troughput. FIX or analyse it's cause.
            sendlen = 1000 * sendlen
        for p in recv_pts:
            if not p.is_open:
                p.open()

        if not send_pt.is_open:
            send_pt.open()

        threads = []
        queues = []
        verified = []
        for i in range(0, len(recv_pts)):
            queues.append(deque())
            verified.append(0)

        tmp = "'%s'" % recv_pts[0].name
        for recv_pt in recv_pts[1:]:
            tmp += ", '%s'" % (recv_pt.name)
        on_guest("virt.loopback(['%s'], [%s], %d, virt.LOOP_POLL)"
                 % (send_pt.name, tmp, parms[4]), vm, 10)

        exit_event = threading.Event()

        # TEST
        thread = ThSendCheck(send_pt, exit_event, queues,
                             parms[2])
        thread.start()
        threads.append(thread)

        for i in range(len(recv_pts)):
            thread = ThRecvCheck(recv_pts[i], queues[i], exit_event,
                                 parms[3], sendlen=sendlen)
            thread.start()
            threads.append(thread)

        i=0
        while i < 6:
            tmp = "%d data sent; " % threads[0].idx
            for thread in threads[1:]:
                tmp += "%d, " % thread.idx
            logging.debug("test_loopback: %s data received and verified",
                         tmp[:-2])
            i+=1
            time.sleep(2)


        for j in range(parms[1]):
            vm[0] = virt_test_utils.migrate(vm[0], env, 3600, "exec", 0,
                                             offline)
            if not vm[1]:
                raise error.TestFail("Could not log into guest after migration")
            vm[1] = virt_test_utils.wait_for_login(vm[0], 0,
                                        float(params.get("boot_timeout", 100)),
                                        0, 2)
            # OS is sometime a bit dizzy. DL=30
            _init_guest(vm, 30)

            i=0
            while i < 6:
                tmp = "%d data sent; " % threads[0].idx
                for thread in threads[1:]:
                    tmp += "%d, " % thread.idx
                logging.debug("test_loopback: %s data received and verified",
                             tmp[:-2])
                i+=1
                time.sleep(2)
            if not threads[0].isAlive():
                if exit_event.isSet():
                    raise error.TestFail("Exit event emited, check the log for"
                                         "send/recv thread failure.")
                else:
                    raise error.TestFail("Send thread died unexpectedly in "
                                         "migration %d", (j+1))
            for i in range(0, len(recv_pts)):
                if not threads[i+1].isAlive():
                    raise error.TestFail("Recv thread %d died unexpectedly in "
                                         "migration %d", i, (j+1))
                if verified[i] == threads[i+1].idx:
                    raise error.TestFail("No new data in %d console were "
                                         "transfered after migration %d"
                                         , i, (j+1))
                verified[i] = threads[i+1].idx
            logging.info("%d out of %d migration(s) passed" % ((j+1), parms[1]))
            # TODO detect recv-thread failure and throw out whole test

        # FINISH
        exit_event.set()
        # Send thread might fail to exit when the guest stucks
        i = 30
        while threads[0].isAlive():
            if i <= 0:
                raise error.TestFail("Send thread did not finish")
            time.sleep(1)
            i -= 1
        tmp = "%d data sent; " % threads[0].idx
        for thread in threads[1:]:
            thread.join()
            tmp += "%d, " % thread.idx
        logging.info("test_loopback: %s data received and verified during %d "
                     "migrations", tmp[:-2], parms[1])

        # CLEANUP
        _guest_exit_threads(vm, [send_pt], recv_pts)
        del exit_event
        del threads[:]


    def _tmigrate(vm, consoles, parms, offline):
        """
        Wrapper which parses the params for __migrate test.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Field of virtio ports with the minimum of 2 items.
        @param parms: test parameters, multiple recievers allowed.
            '[{serialport,console}]:$no_migrations:send_buf_len:recv_buf_len:
             loopback_buf_len;...'
        """
        for param in parms.split(';'):
            if not param:
                continue
            if offline:
                logging.info("test_migrate_offline: params: %s", param)
            else:
                logging.info("test_migrate_online: params: %s", param)
            param = param.split(':')
            media = 1
            if param[0].isalpha():
                if param[0] == "console":
                    param[0] = 0
                else:
                    param[0] = 1
            else:
                param = [0] + param
            for i in range(1,5):
                if not param[i].isdigit():
                    param[i] = 1
                else:
                    param[i] = int(param[i])

            __tmigrate(vm, consoles, param, offline=offline)


    def tmigrate_offline(vm, consoles, parms):
        """
        Tests whether the virtio-{console,port} are able to survive the offline
        migration.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Field of virtio ports with the minimum of 2 items.
        @param parms: test parameters, multiple recievers allowed.
            '[{serialport,console}]:$no_migrations:send_buf_len:recv_buf_len:
             loopback_buf_len;...'
        """
        _tmigrate(vm, consoles, parms, offline=True)


    def tmigrate_online(vm, consoles, parms):
        """
        Tests whether the virtio-{console,port} are able to survive the online
        migration.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Field of virtio ports with the minimum of 2 items.
        @param parms: test parameters, multiple recievers allowed.
            '[{serialport,console}]:$no_migrations:send_buf_len:recv_buf_len:
             loopback_buf_len;...'
        """
        _tmigrate(vm, consoles, parms, offline=False)


    def _virtio_dev_create(vm, ports_name, pciid, id, console="no"):
        """
        Add virtio serialport device.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param ports_name: Structure of ports.
        @param pciid: Id of virtio-serial-pci device.
        @param id: Id of port.
        @param console: if "yes" inicialize console.
        """
        port = "serialport-"
        port_type = "virtserialport"
        if console == "yes":
            port = "console-"
            port_type = "virtconsole"
        port += "%d%d" % (pciid, id)
        ret = vm[0].monitors[0].cmd("device_add %s,"
                                    "bus=virtio-serial-pci%d.0,"
                                    "id=%s,"
                                    "name=%s"
                                    % (port_type, pciid, port, port))
        ports_name.append([ port, console])
        if ret != "":
            logging.error(ret)


    def _virtio_dev_del(vm, ports_name, pciid, id):
        """
        Del virtio serialport device.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param ports_name: Structure of ports.
        @param pciid: Id of virtio-serial-pci device.
        @param id: Id of port.
        """
        port = filter(lambda x: x[0].endswith("-%d%d" % (pciid, id)),
                      ports_name)
        ret = vm[0].monitors[0].cmd("device_del %s"
                                        % (port[0][0]))
        ports_name.remove(port[0])
        if ret != "":
            logging.error(ret)


    def thotplug(vm, consoles, console="no", timeout=1):
        """
        Try hotplug function of virtio-consoles ports.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Consoles.
        @param console: If "yes" inicialize console.
        @param timeout: Timeout between hotplug operations.
        """
        logging.info("Timeout between hotplug operations t=%fs" % timeout)
        _reset_vm(vm, consoles, 1, 1)
        ports_name = []
        ports_name.append(['serialport-1','no'])
        ports_name.append(['console-0','yes'])

        logging.info("Test correct initialization of hotplug ports")
        for id in range(1,5): #count of pci device
            ret = vm[0].monitors[0].cmd("device_add virtio-serial-pci,"
                                        "id=virtio-serial-pci%d" % (id))
            if ret != "":
                logging.error(ret)
            for i in range(id*5+5): #max port 30
                _virtio_dev_create(vm, ports_name, id, i, console)
                time.sleep(timeout)

        # Test correct initialization of hotplug ports
        time.sleep(10) # Timeout for port initialization
        _init_guest(vm, 10)
        on_guest('virt.init(%s)' % (ports_name), vm, 10)

        logging.info("Delete ports when ports are used")
        # Delete ports when ports are used.
        if not consoles[0][0].is_open:
            consoles[0][0].open()
        if not consoles[1][0].is_open:
            consoles[1][0].open()
        on_guest("virt.loopback(['%s'], ['%s'], 1024,"
                 "virt.LOOP_POLL)" % (consoles[0][0].name,
                                      consoles[1][0].name), vm, 10)
        exit_event = threading.Event()
        send = ThSend(consoles[0][0].sock, "Data", exit_event, quiet = True)
        recv = ThRecv(consoles[1][0].sock, exit_event, quiet = True)
        send.start()
        time.sleep(2)
        recv.start()

        # Try to delete ports under load
        ret = vm[0].monitors[0].cmd("device_del serialport-1")
        ret += vm[0].monitors[0].cmd("device_del console-0")
        ports_name.remove(['serialport-1','no'])
        ports_name.remove(['console-0','yes'])
        if ret != "":
            logging.error(ret)

        exit_event.set()
        send.join()
        recv.join()
        on_guest("virt.exit_threads()", vm, 10)
        on_guest('guest_exit()', vm, 10)

        logging.info("Trying to add maximum count of ports to one pci device")
        # Try to add ports
        for i in range(30): # max port 30
            _virtio_dev_create(vm, ports_name, 0, i, console)
            time.sleep(timeout)
        _init_guest(vm, 10)
        time.sleep(10)
        on_guest('virt.init(%s)' % (ports_name), vm, 20)
        on_guest('guest_exit()', vm, 10)

        logging.info("Trying delete and add again part of ports")
        # Try to delete ports
        for i in range(25): # max port 30
            _virtio_dev_del(vm, ports_name, 0, i)
            time.sleep(timeout)
        _init_guest(vm, 10)
        on_guest('virt.init(%s)' % (ports_name), vm, 10)
        on_guest('guest_exit()', vm, 10)

        # Try to add ports
        for i in range(5): # max port 30
            _virtio_dev_create(vm, ports_name, 0, i, console)
            time.sleep(timeout)
        _init_guest(vm, 10)
        on_guest('virt.init(%s)' % (ports_name), vm, 10)
        on_guest('guest_exit()', vm, 10)

        logging.info("Trying to add and delete one port 100 times")
        # Try 100 times add and delete one port.
        for i in range(100):
            _virtio_dev_del(vm, ports_name, 0, 0)
            time.sleep(timeout)
            _virtio_dev_create(vm, ports_name, 0, 0, console)
            time.sleep(timeout)
        _init_guest(vm, 10)
        on_guest('virt.init(%s)' % (ports_name), vm, 10)
        on_guest('guest_exit()', vm, 10)


    def thotplug_no_timeout(vm, consoles, console="no"):
        """
        Start hotplug test without any timeout.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Consoles which should be close before rmmod.
        @param console: If "yes" inicialize console.
        """
        thotplug(vm, consoles, console, 0)


    def thotplug_virtio_pci(vm, consoles):
        """
        Test hotplug of virtio-serial-pci.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Consoles which should be close before rmmod.
        """
        vm[0].destroy(gracefully = False)
        (vm, consoles) = _vm_create(1, 1, False)
        id = 1
        ret = vm[0].monitors[0].cmd("device_add virtio-serial-pci,"
                                    "id=virtio-serial-pci%d" % (id))
        time.sleep(10)
        ret += vm[0].monitors[0].cmd("device_del virtio-serial-pci%d" % (id))
        time.sleep(10)
        ret += vm[0].monitors[0].cmd("device_add virtio-serial-pci,"
                                    "id=virtio-serial-pci%d" % (id))
        if ret != "":
            logging.error(ret)


    def tloopback(vm, consoles, params):
        """
        Virtio console loopback subtest.

        Creates loopback on the vm machine between send_pt and recv_pts
        ports and sends length amount of data through this connection.
        It validates the correctness of the data sent.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Field of virtio ports with the minimum of 2 items.
        @param params: test parameters, multiple recievers allowed.
            '$source_console_type@buffer_length:
             $destination_console_type1@$buffer_length:...:
             $loopback_buffer_length;...'
        """
        # PREPARE
        for param in params.split(';'):
            if not param:
                continue
            logging.info("test_loopback: params: %s", param)
            param = param.split(':')
            idx_serialport = 0
            idx_console = 0
            buf_len = []
            if (param[0].startswith('console')):
                send_pt = consoles[0][idx_console]
                idx_console += 1
            else:
                send_pt = consoles[1][idx_serialport]
                idx_serialport += 1
            if (len(param[0].split('@')) == 2):
                buf_len.append(int(param[0].split('@')[1]))
            else:
                buf_len.append(1024)
            recv_pts = []
            for parm in param[1:]:
                if (parm.isdigit()):
                    buf_len.append(int(parm))
                    break   # buf_len is the last portion of param
                if (parm.startswith('console')):
                    recv_pts.append(consoles[0][idx_console])
                    idx_console += 1
                else:
                    recv_pts.append(consoles[1][idx_serialport])
                    idx_serialport += 1
                if (len(parm[0].split('@')) == 2):
                    buf_len.append(int(parm[0].split('@')[1]))
                else:
                    buf_len.append(1024)
            # There must be sum(idx_*) consoles + last item as loopback buf_len
            if len(buf_len) == (idx_console + idx_serialport):
                buf_len.append(1024)

            for p in recv_pts:
                if not p.is_open:
                    p.open()

            if not send_pt.is_open:
                send_pt.open()

            if len(recv_pts) == 0:
                raise error.TestFail("test_loopback: incorrect recv consoles"
                                     "definition")

            threads = []
            queues = []
            for i in range(0, len(recv_pts)):
                queues.append(deque())

            tmp = "'%s'" % recv_pts[0].name
            for recv_pt in recv_pts[1:]:
                tmp += ", '%s'" % (recv_pt.name)
            on_guest("virt.loopback(['%s'], [%s], %d, virt.LOOP_POLL)"
                     % (send_pt.name, tmp, buf_len[-1]), vm, 10)

            exit_event = threading.Event()

            # TEST
            thread = ThSendCheck(send_pt, exit_event, queues,
                                   buf_len[0])
            thread.start()
            threads.append(thread)

            for i in range(len(recv_pts)):
                thread = ThRecvCheck(recv_pts[i], queues[i], exit_event,
                                       buf_len[i + 1])
                thread.start()
                threads.append(thread)

            time.sleep(60)
            exit_event.set()
            threads[0].join()
            tmp = "%d data sent; " % threads[0].idx
            for thread in threads[1:]:
                thread.join()
                tmp += "%d, " % thread.idx
            logging.info("test_loopback: %s data received and verified",
                         tmp[:-2])

            # Read-out all remaining data
            for recv_pt in recv_pts:
                while select.select([recv_pt.sock], [], [], 0.1)[0]:
                    recv_pt.sock.recv(1024)

            _guest_exit_threads(vm, [send_pt], recv_pts)

            del exit_event
            del threads[:]


    def tperf(vm, consoles, params):
        """
        Tests performance of the virtio_console tunel. First it sends the data
        from host to guest and than back. It provides informations about
        computer utilisation and statistic informations about the troughput.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Field of virtio ports with the minimum of 2 items.
        @param params: test parameters:
                '$console_type@$buffer_length:$test_duration;...'
        """
        for param in params.split(';'):
            if not param:
                continue
            logging.info("test_perf: params: %s", param)
            param = param.split(':')
            duration = 60.0
            if len(param) > 1:
                try:
                    duration = float(param[1])
                except Exception:
                    pass
            param = param[0].split('@')
            if len(param) > 1 and param[1].isdigit():
                buf_len = int(param[1])
            else:
                buf_len = 1024
            param = (param[0] == 'serialport')
            port = consoles[param][0]

            if not port.is_open:
                port.open()

            data = ""
            for i in range(buf_len):
                data += "%c" % random.randrange(255)

            exit_event = threading.Event()
            time_slice = float(duration) / 100

            # HOST -> GUEST
            on_guest('virt.loopback(["%s"], [], %d, virt.LOOP_NONE)' %
                     (port.name, buf_len), vm, 10)
            thread = ThSend(port.sock, data, exit_event)
            stats = array.array('f', [])
            loads = utils.SystemLoad([(os.getpid(), 'autotest'),
                                      (vm[0].get_pid(), 'VM'), 0])
            loads.start()
            _time = time.time()
            thread.start()
            for i in range(100):
                stats.append(thread.idx)
                time.sleep(time_slice)
            _time = time.time() - _time - duration
            logging.info("\n" + loads.get_cpu_status_string()[:-1])
            logging.info("\n" + loads.get_mem_status_string()[:-1])
            exit_event.set()
            thread.join()

            # Let the guest read-out all the remaining data
            while not _on_guest("virt.poll('%s', %s)" %
                                (port.name, select.POLLIN), vm, 10)[0]:
                time.sleep(1)

            _guest_exit_threads(vm, [port], [])

            if (_time > time_slice):
                logging.error(
                "Test ran %fs longer which is more than one time slice", _time)
            else:
                logging.debug("Test ran %fs longer", _time)
            stats = process_stats(stats[1:], time_slice * 1048576)
            logging.debug("Stats = %s", stats)
            logging.info("Host -> Guest [MB/s] (min/med/max) = %.3f/%.3f/%.3f",
                        stats[0], stats[len(stats) / 2], stats[-1])

            del thread

            # GUEST -> HOST
            exit_event.clear()
            stats = array.array('f', [])
            on_guest("virt.send_loop_init('%s', %d)" % (port.name, buf_len),
                     vm, 30)
            thread = ThRecv(port.sock, exit_event, buf_len)
            thread.start()
            loads.start()
            on_guest("virt.send_loop()", vm, 10)
            _time = time.time()
            for i in range(100):
                stats.append(thread.idx)
                time.sleep(time_slice)
            _time = time.time() - _time - duration
            logging.info("\n" + loads.get_cpu_status_string()[:-1])
            logging.info("\n" + loads.get_mem_status_string()[:-1])
            on_guest("virt.exit_threads()", vm, 10)
            exit_event.set()
            thread.join()
            if (_time > time_slice): # Deviation is higher than 1 time_slice
                logging.error(
                "Test ran %fs longer which is more than one time slice", _time)
            else:
                logging.debug("Test ran %fs longer", _time)
            stats = process_stats(stats[1:], time_slice * 1048576)
            logging.debug("Stats = %s", stats)
            logging.info("Guest -> Host [MB/s] (min/med/max) = %.3f/%.3f/%.3f",
                         stats[0], stats[len(stats) / 2], stats[-1])

            del thread
            del exit_event


    def _clean_ports(vm, consoles):
        """
        Read all data from all ports, in both sides of each port.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Consoles which should be clean.
        """
        for ctype in consoles:
            for port in ctype:
                openned = port.is_open
                port.clean_port()
                on_guest("virt.clean_port('%s'),1024" % port.name, vm, 10)
                if not openned:
                    port.close()
                    on_guest("virt.close('%s'),1024" % port.name, vm, 10)


    def clean_ports(vm, consoles):
        """
        Clean state of all ports and set port to default state.
        Default state:
           No data on port or in port buffer.
           Read mode = blocking.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Consoles which should be clean.
        """
        # Check if python is still alive
        logging.info("CLEANING")
        match, tmp = _on_guest("is_alive()", vm, 10)
        if (match is None) or (match != 0):
            logging.error("Python died/is stucked/have remaining threads")
            logging.debug(tmp)
            try:
                kernel_bug = _search_kernel_crashlog(vm[0].serial_console, 10)
                if kernel_bug is not None:
                    logging.error(kernel_bug)
                    raise error.TestFail("Kernel crash.")

                if vm[4] == True:
                    raise error.TestFail("Kernel crash.")
                match, tmp = _on_guest("guest_exit()", vm, 10)
                if (match is None) or (match == 0):
                    vm[1].close()
                    vm[1] = virt_test_utils.wait_for_login(vm[0], 0,
                                        float(params.get("boot_timeout", 5)),
                                        0, 10)
                on_guest("killall -9 python "
                         "&& echo -n PASS: python killed"
                         "|| echo -n PASS: python was already dead",
                         vm, 10)

                init_guest(vm, consoles)
                _clean_ports(vm, consoles)

            except (error.TestFail, aexpect.ExpectError,
                    Exception), inst:
                logging.error(inst)
                logging.error("Virtio-console driver is irreparably"
                              " blocked. Every comd end with sig KILL."
                              "Trying to reboot vm to continue testing...")
                try:
                    vm[0].destroy(gracefully = True)
                    (vm[0], vm[1], vm[3]) = _restore_vm()
                except (kvm_monitor.MonitorProtocolError):
                    logging.error("Qemu is blocked. Monitor no longer "
                                  "communicates")
                    vm[0].destroy(gracefully = False)
                    os.system("kill -9 %d" % (vm[0].get_pid()))
                    (vm[0], vm[1], vm[3]) = _restore_vm()
                init_guest(vm, consoles)
                cname = ""
                try:
                    cname = consoles[0][0].name
                except (IndexError):
                    cname = consoles[1][0].name
                match = _on_guest("virt.clean_port('%s'),1024" %
                                  cname, vm, 10)[0]

                if (match is None) or (match != 0):
                    raise error.TestFail("Virtio-console driver is irreparably "
                                         "blocked. Every comd ended with sig "
                                         "KILL. The restart didn't help")
                _clean_ports(vm, consoles)


    def _reset_vm(vm, consoles, no_console=1, no_serialport=1):
        """
        Destroy and reload vm.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Consoles which should be close and than renew.
        @param no_console: Number of desired virtconsoles.
        @param no_serialport: Number of desired virtserialports.
        """
        vm[0].destroy(gracefully=False)
        shutil.rmtree(vm[2])    # Remove virtio sockets tmp directory
        (_vm, _consoles) = _vm_create(no_console, no_serialport)
        consoles[:] = _consoles[:]
        vm[:] = _vm[:]


    def clean_reload_vm(vm, consoles, expected=False):
        """
        Reloads and boots the damaged vm

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Consoles which should be clean.
        """
        if expected:
            logging.info("Scheduled vm reboot")
        else:
            logging.info("SCHWARZENEGGER is CLEANING")
        _reset_vm(vm, consoles, len(consoles[0]), len(consoles[1]))
        init_guest(vm, consoles)


    def test_smoke(test, vm, consoles, params, global_params):
        """
        Virtio console smoke test.

        Tests the basic functionalities (poll, read/write with and without
        connected host, etc.

        @param test: Main test object.
        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Field of virtio ports with the minimum of 2 items.
        @param params: Test parameters '$console_type:$data;...'
        @param global_params: Params defined by tests_base.conf.
        """
        # PREPARE
        if (global_params.get('smoke_test') == "yes"):
            for param in params.split(';'):
                if not param:
                    continue
                headline = "test_smoke: params: %s" % (param)
                logging.info(headline)
                param = param.split(':')
                if len(param) > 1:
                    data = param[1]
                else:
                    data = "Smoke test data"
                param = (param[0] == 'serialport')
                send_pt = consoles[param][0]
                recv_pt = consoles[param][1]
                subtest.headline(headline)
                subtest.do_test(tcheck_zero_sym, [vm], cleanup=False)
                subtest.do_test(topen, [vm, send_pt], True)
                subtest.do_test(tclose, [vm, send_pt], True)
                subtest.do_test(tmulti_open, [vm, send_pt])
                subtest.do_test(tpolling, [vm, send_pt])
                subtest.do_test(tsigio, [vm, send_pt])
                subtest.do_test(tlseek, [vm, send_pt])
                subtest.do_test(trw_host_offline, [vm, send_pt])
                subtest.do_test(trw_host_offline_big_data, [vm, send_pt],
                                cleanup=False)
                subtest.do_test(trw_notconnect_guest,
                                [vm, send_pt, consoles])
                subtest.do_test(trw_nonblocking_mode, [vm, send_pt])
                subtest.do_test(trw_blocking_mode, [vm, send_pt])
                subtest.do_test(tbasic_loopback, [vm, send_pt, recv_pt, data],
                                True)


    def test_multiport(test, vm, consoles, params, global_params):
        """
        This is group of test which test virtio_console in maximal load and
        with multiple ports.

        @param test: Main test object.
        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Field of virtio ports with the minimum of 2 items.
        @param params: Test parameters '$console_type:$data;...'
        @param global_params: Params defined by tests_base.conf.
        """
        subtest.headline("test_multiport:")
        # Test Loopback
        if (global_params.get('loopback_test') == "yes"):
            subtest.do_test(tloopback, [vm, consoles, params[0]])

        # Test Performance
        if (global_params.get('perf_test') == "yes"):
            subtest.do_test(tperf, [vm, consoles, params[1]])


    def test_destructive(test, vm, consoles, global_params, params):
        """
        This is group of tests which might be destructive.

        @param test: Main test object.
        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Field of virtio ports with the minimum of 2 items.
        @param global_params: Params defined by tests_base.conf.
        @param params: Dictionary of subtest params from tests_base.conf.
        """
        subtest.headline("test_destructive:")
        # Uses stronger clean up function
        (_cleanup_func, _cleanup_args) = subtest.get_cleanup_func()
        subtest.set_cleanup_func(clean_reload_vm, [vm, consoles])

        if (global_params.get('rmmod_test') == "yes"):
            subtest.do_test(trmmod,[vm, consoles])
        if (global_params.get('max_ports_test') == "yes"):
            subtest.do_test(tmax_serial_ports, [vm, consoles])
            subtest.do_test(tmax_console_ports, [vm, consoles])
            subtest.do_test(tmax_mix_serial_conosle_port, [vm, consoles])
        if (global_params.get('shutdown_test') == "yes"):
            subtest.do_test(tshutdown, [vm, consoles])
        if (global_params.get('migrate_offline_test') == "yes"):
            subtest.do_test(tmigrate_offline,
                            [vm, consoles, params['tmigrate_offline_params']])
        if (global_params.get('migrate_online_test') == "yes"):
            subtest.do_test(tmigrate_online,
                            [vm, consoles, params['tmigrate_online_params']])
        if (global_params.get('hotplug_serial_test') == "yes"):
            subtest.do_test(thotplug, [vm, consoles])
            subtest.do_test(thotplug_no_timeout, [vm, consoles])
        if (global_params.get('hotplug_console_test') == "yes"):
            subtest.do_test(thotplug, [vm, consoles, "yes"])
            subtest.do_test(thotplug_no_timeout, [vm, consoles, "yes"])
        if (global_params.get('hotplug_pci_test') == "yes"):
            subtest.do_test(thotplug_virtio_pci, [vm, consoles])

        subtest.set_cleanup_func(_cleanup_func, _cleanup_args)


    # INITIALIZE
    if "extra_params" in params:
        standard_extra_params = params['extra_params']
    else:
        standard_extra_params = ""

    tsmoke_params = params.get('virtio_console_smoke', '')
    tloopback_params = params.get('virtio_console_loopback', '')
    tperf_params = params.get('virtio_console_perf', '')
    tmigrate_offline_params = params.get('virtio_console_migration_offline', '')
    tmigrate_online_params = params.get('virtio_console_migration_online', '')

    # destructive params
    tdestructive_params = {}
    tdestructive_params['tmigrate_offline_params'] = tmigrate_offline_params
    tdestructive_params['tmigrate_online_params'] = tmigrate_online_params

    no_serialports = int(params.get('virtio_console_no_serialports', 0))
    no_consoles = int(params.get('virtio_console_no_consoles', 0))
    # consoles required for Smoke test
    if tsmoke_params.count('serialport'):
        no_serialports = max(2, no_serialports)
    if tsmoke_params.count('console'):
        no_consoles = max(2, no_consoles)
    # consoles required for Loopback test
    for param in tloopback_params.split(';'):
        no_serialports = max(no_serialports, param.count('serialport'))
        no_consoles = max(no_consoles, param.count('console'))
    # consoles required for Performance test
    if tperf_params.count('serialport'):
        no_serialports = max(1, no_serialports)
    if tperf_params.count('console'):
        no_consoles = max(1, no_consoles)
    # consoles required for Migration offline test
    if tmigrate_offline_params.count('serial'):
        no_serialports = max(2, no_serialports)
    if tmigrate_offline_params.count('console'):
        no_consoles = max(2, no_consoles)
    if tmigrate_online_params.count('serial'):
        no_serialports = max(2, no_serialports)
    if tmigrate_online_params.count('console'):
        no_consoles = max(2, no_consoles)

    if no_serialports + no_consoles == 0:
        raise error.TestFail("No tests defined, probably incorrect "
                             "configuration in tests_base.cfg")

    vm, consoles = _vm_create(no_consoles, no_serialports)

    # Copy virtio_console_guest.py into guests
    virt_dir = os.path.join(os.environ['AUTODIR'], 'virt')
    vksmd_src = os.path.join(virt_dir, "scripts", "virtio_console_guest.py")
    dst_dir = "/tmp"

    vm[0].copy_files_to(vksmd_src, dst_dir)

    # ACTUAL TESTING
    # Defines all available consoles; tests udev and sysfs

    subtest = SubTest()
    try:
        init_guest(vm, consoles)

        subtest.set_cleanup_func(clean_ports, [vm, consoles])
        # Test Smoke
        test_smoke(subtest, vm, consoles, tsmoke_params, params)

        # Test multiport functionality and performance.
        test_multiport(subtest, vm, consoles, [tloopback_params, tperf_params],
                       params)

        #Test destructive test.
        test_destructive(subtest, vm, consoles, params, tdestructive_params)
    finally:
        logging.info(("Summary: %d tests passed  %d test failed :\n" %
                      (subtest.passed, subtest.failed)) +
                      subtest.get_text_result())

    if subtest.is_failed():
        raise error.TestFail("%d out of %d virtio console tests failed" %
                             (subtest.failed, (subtest.passed+subtest.failed)))


    # CLEANUP
    vm[1].close()
    vm[0].destroy(gracefully=False)
    shutil.rmtree(vm[2])
