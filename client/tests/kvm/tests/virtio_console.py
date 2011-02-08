"""
virtio_console test

@copyright: 2010 Red Hat, Inc.
"""
import array, logging, os, random, re, select, shutil, socket, sys, tempfile
import threading, time, traceback
from collections import deque
from threading import Thread

from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
import kvm_subprocess, kvm_test_utils, kvm_utils
import kvm_preprocessing, kvm_monitor


def run_virtio_console(test, params, env):
    """
    KVM virtio_console test

    1) Starts VMs with the specified number of virtio console devices
    2) Start smoke test
    3) Start loopback test
    4) Start performance test

    This test uses an auxiliary script, console_switch.py, that is copied to
    guests. This script has functions to send and write data to virtio console
    ports. Details of each test can be found on the docstrings for the test_*
    functions.

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
            if args == None:
                args = []
            res = [None, function.func_name, args]
            try:
                logging.info("Start test %s." % function.func_name)
                ret = function(*args)
                res[0] = True
                logging.info(self.result_to_string(res))
                self.result.append(res)
                self.passed += 1
                return ret
            except:
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
                    except:
                        error.TestFail("Cleanup function crash too.")
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
            Format result with foramting function

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


    class Port(object):
        """
        Define structure to keep information about used port.
        """
        def __init__(self, sock, name, port_type, path):
            """
            @param vm: virtual machine object that port owned
            @param sock: Socket of port if port is open.
            @param name: Name of port for guest side.
            @param port_type: Type of port yes = console, no= serialport.
            @param path: Path to port on host side.
            """
            self.sock = sock
            self.name = name
            self.port_type = port_type
            self.path = path
            self.is_open = False


        def for_guest(self):
            """
            Format data for communication with guest side.
            """
            return [self.name, self.port_type]


        def open(self):
            """
            Open port on host side.
            """
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(self.path)
            self.is_open = True


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
            return ("%s,%s,%s,%s,%d" % ("Socket", self.name, self.port_type,
                                        self.path, self.is_open))


    class ThSend(Thread):
        """
        Random data sender thread.
        """
        def __init__(self, port, data, event):
            """
            @param port: Destination port.
            @param data: The data intend to be send in a loop.
            @param event: Exit event.
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


        def run(self):
            logging.debug("ThSend %s: run", self.getName())
            while not self.exitevent.isSet():
                self.idx += self.port.send(self.data)
            logging.debug("ThSend %s: exit(%d)", self.getName(),
                          self.idx)


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
                ret = select.select([], [self.port], [], 1.0)
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
                        idx = self.port.send(buf)
                        buf = buf[idx:]
                        self.idx += idx
            logging.debug("ThSendCheck %s: exit(%d)", self.getName(),
                          self.idx)
            if too_much_data:
                logging.error("ThSendCheck: workaround the 'too_much_data'"
                              "bug")


    class ThRecv(Thread):
        """
        Recieves data and throws it away.
        """
        def __init__(self, port, event, blocklen=1024):
            """
            @param port: Data source port.
            @param event: Exit event.
            @param blocklen: Block length.
            """
            Thread.__init__(self)
            self.port = port
            self._port_timeout = self.port.gettimeout()
            self.port.settimeout(0.1)
            self.exitevent = event
            self.blocklen = blocklen
            self.idx = 0
        def run(self):
            logging.debug("ThRecv %s: run", self.getName())
            while not self.exitevent.isSet():
                # TODO: Workaround, it didn't work with select :-/
                try:
                    self.idx += len(self.port.recv(self.blocklen))
                except socket.timeout:
                    pass
            self.port.settimeout(self._port_timeout)
            logging.debug("ThRecv %s: exit(%d)", self.getName(), self.idx)


    class ThRecvCheck(Thread):
        """
        Random data receiver/checker thread.
        """
        def __init__(self, port, buffer, event, blocklen=1024):
            """
            @param port: Source port.
            @param buffer: Control data buffer (FIFO).
            @param length: Amount of data we want to receive.
            @param blocklen: Block length.
            """
            Thread.__init__(self)
            self.port = port
            self.buffer = buffer
            self.exitevent = event
            self.blocklen = blocklen
            self.idx = 0


        def run(self):
            logging.debug("ThRecvCheck %s: run", self.getName())
            while not self.exitevent.isSet():
                ret = select.select([self.port], [], [], 1.0)
                if ret[0] and (not self.exitevent.isSet()):
                    buf = self.port.recv(self.blocklen)
                    if buf:
                        # Compare the recvd data with the control data
                        for ch in buf:
                            ch_ = self.buffer.popleft()
                            if not ch == ch_:
                                self.exitevent.set()
                                logging.error("Failed to recv %dth character",
                                              self.idx)
                                logging.error("%s != %s", repr(ch), repr(ch_))
                                logging.error("Recv = %s", repr(buf))
                                # sender might change the buffer :-(
                                time.sleep(1)
                                ch_ = ""
                                for buf in self.buffer:
                                    ch_ += buf
                                logging.error("Queue = %s", repr(ch_))
                                raise error.TestFail("ThRecvCheck: incorrect "
                                                     "data")
                        self.idx += len(buf)
            logging.debug("ThRecvCheck %s: exit(%d)", self.getName(),
                          self.idx)


    def process_stats(stats, scale=1.0):
        """
        Process and print the statistic.

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


    def _init_guest(vm, timeout=2):
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
        data = vm_port.read_nonblocking()
        match = re.search("BUG:", data, re.MULTILINE)
        if match == None:
            return None

        match = re.search(r"BUG:.*---\[ end trace .* \]---",
                  data, re.DOTALL |re.MULTILINE)
        if match == None:
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

        except (kvm_subprocess.ExpectError):
            match = None
            data = "Timeout."

        kcrash_data = _search_kernel_crashlog(vm[3])
        if (kcrash_data != None):
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
        if match == None:
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
        #if not params.get('extra_params'):
        params['extra_params'] = ''

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
                                      "name=console-%d,id=c%d,bus=%s"
                                      % (i, i, i, pci))

        for i in  range(no_console, no_console + no_serialport):
            # Spread seroal ports between multiple PCI devices (2 per a dev)
            if not i % 2  and spread:
                pci = "virtio-serial-pci%d" % (i / 2)
                params['extra_params'] += (" -device virtio-serial-pci,id="
                                           + pci)
                pci += ".0"
            params['extra_params'] += (" -chardev socket,path=%s/%d,id=vs%d,"
                                       "server,nowait" % (tmp_dir, i, i))
            params['extra_params'] += (" -device virtserialport,chardev=vs%d,"
                                       "name=serialport-%d,id=p%d,bus=%s"
                                       % (i, i, i, pci))

        (vm, session, sserial) = _restore_vm()

        # connect the sockets
        for i in range(0, no_console):
            consoles.append(Port(None ,"console-%d" % i,
                                 "yes", "%s/%d" % (tmp_dir, i)))
        for i in range(no_console, no_console + no_serialport):
            serialports.append(Port(None ,"serialport-%d" % i,
                                    "no", "%s/%d" % (tmp_dir, i)))

        kcrash = False

        return [vm, session, tmp_dir, sserial, kcrash], [consoles, serialports]


    def _restore_vm():
        """
        Restore old virtual machine when VM is destroied.
        """
        logging.debug("Booting guest %s", params.get("main_vm"))
        kvm_preprocessing.preprocess_vm(test, params, env,
                                        params.get("main_vm"))

        vm = env.get_vm(params.get("main_vm"))

        kernel_bug = None
        try:
            session = kvm_test_utils.wait_for_login(vm, 0,
                                    float(params.get("boot_timeout", 100)),
                                    0, 2)
        except (error.TestFail):
            kernel_bug = _search_kernel_crashlog(vm.serial_console, 10)
            if kernel_bug != None:
                logging.error(kernel_bug)
            raise

        kernel_bug = _search_kernel_crashlog(vm.serial_console, 10)
        if kernel_bug != None:
            logging.error(kernel_bug)

        sserial = kvm_test_utils.wait_for_login(vm, 0,
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


    def tpooling(vm, port):
        """
        Test try pooling function.

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
        if match != None:
            raise error.TestFail("Write on guest while host disconnected "
                                 "didn't timed out.\nOutput:\n%s"
                                 % tmp)

        port.open()

        if (port.sock.recv(1024) < 10):
            raise error.TestFail("Didn't received data from guest")
        # Now the _on_guest("virt.send('%s'... command should be finished
        on_guest("print 'PASS: nothing'", vm, 10)


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
            raise error.TestFail("Received data even when non were sent\n"
                                 "Data:\n%s" % tmp)
        elif match != None:
            raise error.TestFail("Unexpected fail\nMatch: %s\nData:\n%s" %
                                 (match, tmp))
        port.sock.sendall("1234567890")
        # Now guest received the data end escaped from the recv()
        on_guest("print 'PASS: nothing'", vm, 10)


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
            raise error.TestFail("Received data even when non were sent\n"
                                 "Data:\n%s" % tmp)
        elif match == None:
            raise error.TestFail("Timed out, probably in blocking mode\n"
                                 "Data:\n%s" % tmp)
        elif match != 1:
            raise error.TestFail("Unexpected fail\nMatch: %s\nData:\n%s" %
                                 (match, tmp))
        port.sock.sendall("1234567890")
        on_guest("virt.recv('%s', 10, 1024, False)" % port.name, vm, 10)


    def tbasic_loopback(vm, send_port, recv_port, data="Smoke test data"):
        """
        Easy loop back test with loop over only two port.

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
            thread = ThSendCheck(send_pt.sock, exit_event, queues,
                                   buf_len[0])
            thread.start()
            threads.append(thread)

            for i in range(len(recv_pts)):
                thread = ThRecvCheck(recv_pts[i].sock, queues[i], exit_event,
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
                except:
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
        Read all data all port from both side of port.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Consoles which should be clean.
        """
        for ctype in consoles:
            for port in ctype:
                openned = port.is_open
                port.clean_port()
                #on_guest("virt.blocking('%s', True)" % port.name, vm, 10)
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
        print "CLEANING"
        match, tmp = _on_guest("is_alive()", vm, 10)
        if (match == None) or (match != 0):
            logging.error("Python died/is stucked/have remaining threads")
            logging.debug(tmp)
            try:
                if vm[4] == True:
                    raise error.TestFail("Kernel crash.")
                match, tmp = _on_guest("guest_exit()", vm, 10)
                if (match == None) or (match == 0):
                    vm[1].close()
                    vm[1] = kvm_test_utils.wait_for_login(vm[0], 0,
                                        float(params.get("boot_timeout", 5)),
                                        0, 10)
                on_guest("killall -9 python "
                         "&& echo -n PASS: python killed"
                         "|| echo -n PASS: python was death",
                         vm, 10)

                init_guest(vm, consoles)
                _clean_ports(vm, consoles)

            except (error.TestFail, kvm_subprocess.ExpectError,
                    Exception), inst:
                logging.error(inst)
                logging.error("Virtio-console driver is irreparably"
                              " blocked. Every comd end with sig KILL."
                              "Try reboot vm for continue in testing.")
                try:
                    vm[1] = kvm_test_utils.reboot(vm[0], vm[1], "system_reset")
                except (kvm_monitor.MonitorProtocolError):
                    logging.error("Qemu is blocked. Monitor"
                                  " no longer communicate.")
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

                if (match == None) or (match != 0):
                    raise error.TestFail("Virtio-console driver is irrepar"
                                         "ably blocked. Every comd end"
                                         " with sig KILL. Neither the "
                                         "restart did not help.")
                _clean_ports(vm, consoles)


    def clean_reload_vm(vm, consoles, expected=False):
        """
        Reloads and boots the damaged vm

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Consoles which should be clean.
        """
        if not expected:
            print "Scheduled vm reboot"
        else:
            print "SCHWARZENEGGER is CLEANING"
        vm[0].destroy(gracefully=False)
        shutil.rmtree(vm[2])    # Remove virtio sockets tmp directory
        (_vm, _consoles) = _vm_create(len(consoles[0]), len(consoles[1]))
        consoles[:] = _consoles[:]
        vm[:] = _vm[:]
        init_guest(vm, consoles)


    def test_smoke(test, vm, consoles, params):
        """
        Virtio console smoke test.

        Tests the basic functionalities (poll, read/write with and without
        connected host, etc.

        @param test: Main test object.
        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Field of virtio ports with the minimum of 2 items.
        @param params: Test parameters '$console_type:$data;...'
        """
        # PREPARE
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
            test.headline(headline)
            test.do_test(topen, [vm, send_pt], True)
            test.do_test(tclose, [vm, send_pt], True)
            test.do_test(tmulti_open, [vm, send_pt])
            test.do_test(tpooling, [vm, send_pt])
            test.do_test(tsigio, [vm, send_pt])
            test.do_test(tlseek, [vm, send_pt])
            test.do_test(trw_host_offline, [vm, send_pt])
            test.do_test(trw_nonblocking_mode, [vm, send_pt])
            test.do_test(trw_blocking_mode, [vm, send_pt])
            test.do_test(tbasic_loopback, [vm, send_pt, recv_pt, data], True)


    def test_multiport(test, vm, consoles, params):
        """
        This is group of test which test virtio_console in maximal load and
        with multiple ports.

        @param test: Main test object.
        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Field of virtio ports with the minimum of 2 items.
        @param params: Test parameters '$console_type:$data;...'
        """
        subtest.headline("test_multiport:")
        #Test Loopback
        subtest.do_test(tloopback, [vm, consoles, params[0]])

        #Test Performance
        subtest.do_test(tperf, [vm, consoles, params[1]])


    def test_destructive(test, vm, consoles):
        """
        This is group of test is destructive.

        @param test: Main test object.
        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Field of virtio ports with the minimum of 2 items.
        """
        subtest.headline("test_destructive:")


    # INITIALIZE

    tsmoke_params = params.get('virtio_console_smoke', '')
    tloopback_params = params.get('virtio_console_loopback', '')
    tperf_params = params.get('virtio_console_perf', '')

    no_serialports = 0
    no_consoles = 0
    # consoles required for Smoke test
    if (tsmoke_params.count('serialport')):
        no_serialports = max(2, no_serialports)
    if (tsmoke_params.count('console')):
        no_consoles = max(2, no_consoles)
    # consoles required for Loopback test
    for param in tloopback_params.split(';'):
        no_serialports = max(no_serialports, param.count('serialport'))
        no_consoles = max(no_consoles, param.count('console'))
    # consoles required for Performance test
    if (tperf_params.count('serialport')):
        no_serialports = max(1, no_serialports)
    if (tperf_params.count('console')):
        no_consoles = max(1, no_consoles)

    if (no_serialports + no_consoles) == 0:
        raise error.TestFail("No tests defined, probably incorrect "
                             "configuration in tests_base.cfg")

    vm, consoles = _vm_create(no_consoles, no_serialports)

    # Copy virtio_console_guest.py into guests
    pwd = os.path.join(os.environ['AUTODIR'], 'tests/kvm')
    vksmd_src = os.path.join(pwd, "scripts/virtio_console_guest.py")
    dst_dir = "/tmp"

    vm[0].copy_files_to(vksmd_src, dst_dir)

    # ACTUAL TESTING
    # Defines all available consoles; tests udev and sysfs

    subtest = SubTest()
    try:
        init_guest(vm, consoles)

        subtest.set_cleanup_func(clean_ports, [vm, consoles])
        #Test Smoke
        test_smoke(subtest, vm, consoles, tsmoke_params)

        #Test multiport functionality and performance.
        test_multiport(subtest, vm, consoles, [tloopback_params, tperf_params])

        #Test destructive test.
        # Uses stronger clean up function
        (_cleanup_func, _cleanup_args) = subtest.get_cleanup_func()
        subtest.set_cleanup_func(clean_reload_vm, [vm, consoles])
        test_destructive(subtest, vm, consoles)
        subtest.set_cleanup_func(_cleanup_func, _cleanup_args)
    finally:
        logging.info(("Summary: %d tests passed  %d test failed :\n" %
                      (subtest.passed, subtest.failed)) +
                      subtest.get_text_result())

    if subtest.is_failed():
        raise error.TestFail("Virtio_console test FAILED.")


    # CLEANUP
    vm[1].close()
    vm[0].destroy(gracefully=False)
    shutil.rmtree(vm[2])
