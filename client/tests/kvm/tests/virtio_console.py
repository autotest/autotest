"""
virtio_console test

@copyright: Red Hat 2010
"""
import array, logging, os, random, re, select, shutil, socket, sys, tempfile
import threading, time
from collections import deque
from threading import Thread

import kvm_subprocess, kvm_test_utils, kvm_utils, kvm_preprocessing
from autotest_lib.client.common_lib import error


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
    class th_send(Thread):
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
            logging.debug("th_send %s: run", self.getName())
            while not self.exitevent.isSet():
                self.idx += self.port.send(self.data)
            logging.debug("th_send %s: exit(%d)", self.getName(),
                          self.idx)


    class th_send_check(Thread):
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
            logging.debug("th_send_check %s: run", self.getName())
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
            logging.debug("th_send_check %s: exit(%d)", self.getName(),
                          self.idx)
            if too_much_data:
                logging.error("th_send_check: workaround the 'too_much_data'"
                              "bug")


    class th_recv(Thread):
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
            logging.debug("th_recv %s: run", self.getName())
            while not self.exitevent.isSet():
                # TODO: Workaround, it didn't work with select :-/
                try:
                    self.idx += len(self.port.recv(self.blocklen))
                except socket.timeout:
                    pass
            self.port.settimeout(self._port_timeout)
            logging.debug("th_recv %s: exit(%d)", self.getName(), self.idx)


    class th_recv_check(Thread):
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
            logging.debug("th_recv_check %s: run", self.getName())
            while not self.exitevent.isSet():
                ret = select.select([self.port], [], [], 1.0)
                if ret and (not self.exitevent.isSet()):
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
                                raise error.TestFail("th_recv_check: incorrect "
                                                     "data")
                        self.idx += len(buf)
            logging.debug("th_recv_check %s: exit(%d)", self.getName(),
                          self.idx)


    class cpu_load():
        """
        Get average cpu load between start and get_load.
        """
        def __init__ (self):
            self.old_load = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            self.startTime = 0
            self.endTime = 0


        def _get_cpu_load(self):
            # Let's see if we can calc system load.
            try:
                f = open("/proc/stat", "r")
                tmp = f.readlines(200)
                f.close()
            except:
                logging.critical("Error reading /proc/stat")
                error.TestFail("average_cpu_load: Error reading /proc/stat")

            # 200 bytes should be enough because the information we need
            # is typically stored in the first line
            # Info about individual processors (not yet supported) is in
            # the second (third, ...?) line
            for line in tmp:
                if line[0:4] == "cpu ":
                    reg = re.compile('[0-9]+')
                    load_values = reg.findall(line)
                    # extract values from /proc/stat
                    load = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
                    for i in range(8):
                        load[i] = int(load_values[i]) - self.old_load[i]

                    for i in range(8):
                        self.old_load[i] = int(load_values[i])
                    return load


        def start (self):
            """
            Start CPU usage measurement
            """
            self.old_load = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            self.startTime = time.time()
            self._get_cpu_load()


        def get_load(self):
            """
            Get and reset CPU usage

            @return: return group cpu (user[%], system[%], sum[%], testTime[s])
            """
            self.endTime = time.time()
            testTime = self.endTime - self.startTime
            load = self._get_cpu_load()

            user = load[0] / testTime
            system = load[2] / testTime
            sum = user + system

            return (user, system, sum, testTime)


    class pid_load():
        """
        Get average process cpu load between start and get_load
        """
        def __init__ (self, pid, name):
            self.old_load = [0, 0]
            self.startTime = 0
            self.endTime = 0
            self.pid = pid
            self.name = name


        def _get_cpu_load(self, pid):
            # Let's see if we can calc system load.
            try:
                f = open("/proc/%d/stat" % (pid), "r")
                line = f.readline()
                f.close()
            except:
                logging.critical("Error reading /proc/%d/stat", pid)
                error.TestFail("average_process_cpu_load: Error reading "
                               "/proc/stat")
            else:
                reg = re.compile('[0-9]+')
                load_values = reg.findall(line)
                del load_values[0:11]
                # extract values from /proc/stat
                load = [0, 0]
                for i in range(2):
                    load[i] = int(load_values[i]) - self.old_load[i]

                for i in range(2):
                    self.old_load[i] = int(load_values[i])
                return load


        def start (self):
            """
            Start CPU usage measurement
            """
            self.old_load = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            self.startTime = time.time()
            self._get_cpu_load(self.pid)


        def get_load(self):
            """
            Get and reset CPU usage.

            @return: Group cpu
                    (pid, user[%], system[%], sum[%], testTime[s])
            """
            self.endTime = time.time()
            testTime = self.endTime - self.startTime
            load = self._get_cpu_load(self.pid)

            user = load[0] / testTime
            system = load[1] / testTime
            sum = user + system

            return (self.name, self.pid, user, system, sum, testTime)


    def print_load(process, system):
        """
        Print load in tabular mode.

        @param process: List of process statistic tuples.
        @param system: Tuple of system cpu usage.
        """

        logging.info("%-10s %6s %5s %5s %5s %11s",
                     "NAME", "PID", "USER", "SYS", "SUM", "TIME")
        for pr in process:
            logging.info("%-10s %6d %4.0f%% %4.0f%% %4.0f%% %10.3fs" % pr)
        logging.info("TOTAL:     ------ %4.0f%% %4.0f%% %4.0f%% %10.3fs" %
                     system)


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


    def init_guest(vm, timeout=2):
        """
        Execute virtio_guest.py on guest, wait until it is initialized.

        @param vm: Informations about the guest.
        @param timeout: Timeout that will be used to verify if the script
                started properly.
        """
        logging.debug("compile virtio_guest.py on guest %s", vm[0].name)
        vm[1].sendline("python -OO /tmp/virtio_guest.py -c &&"
                       "echo -n 'PASS: Compile virtio_guest finished' ||"
                       "echo -n 'FAIL: Compile virtio_guest failed'")
        (match, data) = vm[1].read_until_last_line_matches(["PASS:", "FAIL:"],
                                                           timeout)
        if match == 1 or match is None:
            raise error.TestFail("Command console_switch.py on guest %s failed."
                                 "\nreturn code: %s\n output:\n%s" %
                                 (vm[0].name, match, data))
        logging.debug("Starting virtio_guest.py on guest %s", vm[0].name)
        vm[1].sendline("python /tmp/virtio_guest.pyo &&"
                       "echo -n 'PASS: virtio_guest finished' ||"
                       "echo -n 'FAIL: virtio_guest failed'")
        (match, data) = vm[1].read_until_last_line_matches(["PASS:", "FAIL:"],
                                                           timeout)
        if match == 1 or match is None:
            raise error.TestFail("Command console_switch.py on guest %s failed."
                                 "\nreturn code: %s\n output:\n%s" %
                                 (vm[0].name, match, data))
        # Let the system rest
        time.sleep(2)


    def _on_guest(command, vm, timeout=2):
        """
        Execute given command inside the script's main loop, indicating the vm
        the command was executed on.

        @param command: Command that will be executed.
        @param vm: Informations about the guest.
        @param timeout: Timeout used to verify expected output.

        @return: Tuple (match index, data)
        """
        logging.debug("Executing '%s' on virtio_guest.py loop, vm: %s," +
                      "timeout: %s", command, vm[0].name, timeout)
        vm[1].sendline(command)
        (match, data) = vm[1].read_until_last_line_matches(["PASS:", 
                                                    "FAIL:[Failed to execute]"],
                                                    timeout)
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
            raise error.TestFail("Failed to execute '%s' on virtio_guest.py, "
                                 "vm: %s, output:\n%s" %
                                 (command, vm[0].name, data))

        return (match, data)


    def socket_readall(sock, read_timeout, mesagesize):
        """
        Read everything from the socket.

        @param sock: Socket.
        @param read_timeout: Read timeout.
        @param mesagesize: Size of message.
        """
        sock_decriptor = sock.fileno()
        sock.settimeout(read_timeout)
        message = ""
        try:
            while (len(message) < mesagesize):
                message += sock.recv(mesagesize)
        except Exception as inst:
            if (inst.args[0] == "timed out"):
                logging.debug("Reading timeout")
            else:
                logging.debug(inst)
        sock.setblocking(1)
        return message


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
                send_pt[0].sendall(".")
        elif match != 0:
            # Something else
            raise error.TestFail("Unexpected fail\nMatch: %s\nData:\n%s"
                                 % (match, tmp))

        # Read-out all remaining data
        for recv_pt in recv_pts:
            while select.select([recv_pt[0]], [], [], 0.1)[0]:
                recv_pt[0].recv(1024)

        # This will cause fail in case anything went wrong.
        on_guest("print 'PASS: nothing'", vm, 10)


    def _vm_create(no_console=3, no_serialport=3):
        """
        Creates the VM and connects the specified number of consoles and serial
        ports.

        @param no_console: Number of desired virtconsoles.
        @param no_serialport: Number of desired virtserialports.
        @return: Tuple with (guest information, consoles information)
                guest informations = [vm, session, tmp_dir]
                consoles informations = [consoles[], serialports[]]
        """
        consoles = []
        serialports = []
        tmp_dir = tempfile.mkdtemp(prefix="virtio-console-", dir="/tmp/")
        if not params.get('extra_params'):
            params['extra_params'] = ''
        params['extra_params'] += " -device virtio-serial"

        for i in  range(0, no_console):
            params['extra_params'] += (" -chardev socket,path=%s/%d,id=vc%d,"
                                       "server,nowait" % (tmp_dir, i, i))
            params['extra_params'] += (" -device virtconsole,chardev=vc%d,"
                                      "name=console-%d,id=c%d" % (i, i, i))

        for i in  range(no_console, no_console + no_serialport):
            params['extra_params'] += (" -chardev socket,path=%s/%d,id=vs%d,"
                                       "server,nowait" % (tmp_dir, i, i))
            params['extra_params'] += (" -device virtserialport,chardev=vs%d,"
                                       "name=serialport-%d,id=p%d" % (i, i, i))


        logging.debug("Booting first guest %s", params.get("main_vm"))
        kvm_preprocessing.preprocess_vm(test, params, env,
                                        params.get("main_vm"))


        vm = kvm_utils.env_get_vm(env, params.get("main_vm"))

        session = kvm_test_utils.wait_for_login(vm, 0,
                                         float(params.get("boot_timeout", 240)),
                                         0, 2)

        # connect the sockets
        for i in range(0, no_console):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect("%s/%d" % (tmp_dir, i))
            consoles.append([sock, "console-%d" % i, "yes"])
        for i in range(no_console, no_console + no_serialport):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect("%s/%d" % (tmp_dir, i))
            serialports.append([sock, "serialport-%d" % i, "no"])

        return [vm, session, tmp_dir], [consoles, serialports]


    def test_smoke(vm, consoles, params):
        """
        Virtio console smoke test.

        Tests the basic functionalities (poll, read/write with and without
        connected host, etc.

        @param vm: target virtual machine [vm, session, tmp_dir]
        @param consoles: a field of virtio ports with the minimum of 2 items
        @param params: test parameters '$console_type:$data;...'
        """
        logging.info("Smoke test: Tests the basic capabilities of "
                     "virtio_consoles.")
        # PREPARE
        for param in params.split(';'):
            if not param:
                continue
            logging.info("test_smoke: params: %s", param)
            param = param.split(':')
            if len(param) > 1:
                data = param[1]
            else:
                data = "Smoke test data"
            param = (param[0] == 'serialport')
            send_pt = consoles[param][0]
            recv_pt = consoles[param][1]

            # TEST
            # Poll (OUT)
            on_guest("virt.poll('%s', %s)" % (send_pt[1], select.POLLOUT), vm,
                     2)

            # Poll (IN, OUT)
            send_pt[0].sendall("test")
            for test in [select.POLLIN, select.POLLOUT]:
                on_guest("virt.poll('%s', %s)" % (send_pt[1], test), vm, 2)

            # Poll (IN HUP)
            # I store the socket informations and close the socket
            sock = send_pt[0]
            send_pt[0] = sock.getpeername()
            sock.shutdown(2)
            sock.close()
            del sock
            for test in [select.POLLIN, select.POLLHUP]:
                on_guest("virt.poll('%s', %s)" % (send_pt[1], test), vm, 2)

            # Poll (HUP)
            on_guest("virt.recv('%s', 4, 1024, False)" % (send_pt[1]), vm, 2)
            on_guest("virt.poll('%s', %s)" % (send_pt[1], select.POLLHUP), vm,
                     2)

            # Reconnect the socket
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(send_pt[0])
            send_pt[0] = sock
            # Redefine socket in consoles
            consoles[param][0] = send_pt
            on_guest("virt.poll('%s', %s)" % (send_pt[1], select.POLLOUT), vm,
                     2)

            # Read/write without host connected
            # I store the socket informations and close the socket
            sock = send_pt[0]
            send_pt[0] = sock.getpeername()
            sock.shutdown(2)
            sock.close()
            del sock
            # Read should pass
            on_guest("virt.recv('%s', 0, 1024, False)" % send_pt[1], vm, 2)
            # Write should timed-out
            match, tmp = _on_guest("virt.send('%s', 10, False)"
                                    % send_pt[1], vm, 2)
            if match != None:
                raise error.TestFail("Read on guest while host disconnected "
                                     "didn't timed out.\nOutput:\n%s"
                                     % tmp)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(send_pt[0])
            send_pt[0] = sock

            # Redefine socket in consoles
            consoles[param][0] = send_pt
            if (send_pt[0].recv(1024) < 10):
                raise error.TestFail("Didn't received data from guest")
            # Now the _on_guest("virt.send('%s'... command should be finished
            on_guest("print 'PASS: nothing'", vm, 2)

            # Non-blocking mode
            on_guest("virt.blocking('%s', False)" % send_pt[1], vm, 2)
            # Recv should return FAIL with 0 received data
            match, tmp = _on_guest("virt.recv('%s', 10, 1024, False)" %
                                   send_pt[1], vm, 2)
            if match == 0:
                raise error.TestFail("Received data even when non were sent\n"
                                     "Data:\n%s" % tmp)
            elif match == None:
                raise error.TestFail("Timed out, probably in blocking mode\n"
                                     "Data:\n%s" % tmp)
            elif match != 1:
                raise error.TestFail("Unexpected fail\nMatch: %s\nData:\n%s" %
                                     (match, tmp))
            send_pt[0].sendall("1234567890")
            on_guest("virt.recv('%s', 10, 1024, False)" % send_pt[1], vm, 2)

            # Blocking mode
            on_guest("virt.blocking('%s', True)" % send_pt[1], vm, 2)
            # Recv should timed out
            match, tmp = _on_guest("virt.recv('%s', 10, 1024, False)" %
                                   send_pt[1], vm, 2)
            if match == 0:
                raise error.TestFail("Received data even when non were sent\n"
                                     "Data:\n%s" % tmp)
            elif match != None:
                raise error.TestFail("Unexpected fail\nMatch: %s\nData:\n%s" %
                                     (match, tmp))
            send_pt[0].sendall("1234567890")
            # Now guest received the data end escaped from the recv()
            on_guest("print 'PASS: nothing'", vm, 2)

            # Basic loopback test
            on_guest("virt.loopback(['%s'], ['%s'], 1024, virt.LOOP_NONE)" %
                     (send_pt[1], recv_pt[1]), vm, 2)
            send_pt[0].sendall(data)
            tmp = ""
            i = 0
            while i <= 10:
                i += 1
                ret = select.select([recv_pt[0]], [], [], 1.0)
                if ret:
                    tmp += recv_pt[0].recv(1024)
                if len(tmp) >= len(data):
                    break
            if tmp != data:
                raise error.TestFail("Incorrect data: '%s' != '%s'",
                                     data, tmp)
            _guest_exit_threads(vm, [send_pt], [recv_pt])

        return consoles


    def test_loopback(vm, consoles, params):
        """
        Virtio console loopback test.

        Creates loopback on the vm machine between send_pt and recv_pts
        ports and sends length amount of data through this connection.
        It validates the correctness of the data sent.

        @param vm: target virtual machine [vm, session, tmp_dir]
        @param consoles: a field of virtio ports with the minimum of 2 items
        @param params: test parameters, multiple recievers allowed.
            '$source_console_type@buffer_length:
             $destination_console_type1@$buffer_length:...:
             $loopback_buffer_length;...'
        """
        logging.info("Loopback test: Creates a loopback between sender port "
                     "and receiving port, send data through this connection, "
                     "verify data correctness.")
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

            if len(recv_pts) == 0:
                raise error.TestFail("test_loopback: incorrect recv consoles"
                                     "definition")

            threads = []
            queues = []
            for i in range(0, len(recv_pts)):
                queues.append(deque())

            tmp = "'%s'" % recv_pts[0][1]
            for recv_pt in recv_pts[1:]:
                tmp += ", '%s'" % (recv_pt[1])
            on_guest("virt.loopback(['%s'], [%s], %d, virt.LOOP_POLL)"
                     % (send_pt[1], tmp, buf_len[-1]), vm, 2)

            exit_event = threading.Event()

            # TEST
            thread = th_send_check(send_pt[0], exit_event, queues, buf_len[0])
            thread.start()
            threads.append(thread)

            for i in range(len(recv_pts)):
                thread = th_recv_check(recv_pts[i][0], queues[i], exit_event,
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
                while select.select([recv_pt[0]], [], [], 0.1)[0]:
                    recv_pt[0].recv(1024)

            _guest_exit_threads(vm, [send_pt], recv_pts)

            del exit_event
            del threads[:]


    def test_perf(vm, consoles, params):
        """
        Tests performance of the virtio_console tunel. First it sends the data
        from host to guest and than back. It provides informations about
        computer utilisation and statistic informations about the troughput.

        @param vm: target virtual machine [vm, session, tmp_dir]
        @param consoles: a field of virtio ports with the minimum of 2 items
        @param params: test parameters:
                '$console_type@$buffer_length:$test_duration;...'
        """
        logging.info("Performance test: Measure performance for the "
                     "virtio console tunnel")
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

            data = ""
            for i in range(buf_len):
                data += "%c" % random.randrange(255)

            exit_event = threading.Event()
            slice = float(duration)/100

            # HOST -> GUEST
            on_guest('virt.loopback(["%s"], [], %d, virt.LOOP_NONE)' %
                     (port[1], buf_len), vm, 2)
            thread = th_send(port[0], data, exit_event)
            stats = array.array('f', [])
            loads = []
            loads.append(cpu_load())
            loads.append(pid_load(os.getpid(), 'autotest'))
            loads.append(pid_load(vm[0].get_pid(), 'VM'))

            for load in loads:
                load.start()
            _time = time.time()
            thread.start()
            for i in range(100):
                stats.append(thread.idx)
                time.sleep(slice)
            _time = time.time() - _time - duration
            print_load([loads[1].get_load(), loads[2].get_load()],
                       loads[0].get_load())
            exit_event.set()
            thread.join()

            # Let the guest read-out all the remaining data
            while not _on_guest("virt.poll('%s', %s)" %
                                (port[1], select.POLLIN), vm, 2)[0]:
                time.sleep(1)

            _guest_exit_threads(vm, [port], [])

            if (_time > slice):
                logging.error(
                "Test ran %fs longer which is more than one slice", _time)
            else:
                logging.debug("Test ran %fs longer", _time)
            stats = process_stats(stats[1:], slice*1048576)
            logging.debug("Stats = %s", stats)
            logging.info("Host -> Guest [MB/s] (min/med/max) = %.3f/%.3f/%.3f",
                         stats[0], stats[len(stats)/2], stats[-1])

            del thread

            # GUEST -> HOST
            exit_event.clear()
            stats = array.array('f', [])
            on_guest("virt.send_loop_init('%s', %d)" % (port[1], buf_len),
                     vm, 30)
            thread = th_recv(port[0], exit_event, buf_len)
            thread.start()
            for load in loads:
                load.start()
            on_guest("virt.send_loop()", vm, 2)
            _time = time.time()
            for i in range(100):
                stats.append(thread.idx)
                time.sleep(slice)
            _time = time.time() - _time - duration
            print_load([loads[1].get_load(), loads[2].get_load()],
                       loads[0].get_load())
            on_guest("virt.exit_threads()", vm, 2)
            exit_event.set()
            thread.join()
            if (_time > slice): # Deviation is higher than 1 slice
                logging.error(
                "Test ran %fs longer which is more than one slice", _time)
            else:
                logging.debug("Test ran %fs longer" % _time)
            stats = process_stats(stats[1:], slice*1048576)
            logging.debug("Stats = %s", stats)
            logging.info("Guest -> Host [MB/s] (min/med/max) = %.3f/%.3f/%.3f",
                         stats[0], stats[len(stats)/2], stats[-1])

            del thread

            del exit_event
            del loads[:]


    # INITIALIZE
    test_smoke_params = params.get('virtio_console_smoke', '')
    test_loopback_params = params.get('virtio_console_loopback', '')
    test_perf_params = params.get('virtio_console_perf', '')

    no_serialports = 0
    no_consoles = 0
    # consoles required for Smoke test
    if (test_smoke_params.count('serialport')):
        no_serialports = max(2, no_serialports)
    if (test_smoke_params.count('console')):
        no_consoles = max(2, no_consoles)
    # consoles required for Loopback test
    for param in test_loopback_params.split(';'):
        no_serialports = max(no_serialports, param.count('serialport'))
        no_consoles = max(no_consoles, param.count('console'))
    # consoles required for Performance test
    if (test_perf_params.count('serialport')):
        no_serialports = max(1, no_serialports)
    if (test_perf_params.count('console')):
        no_consoles = max(1, no_consoles)

    if (no_serialports + no_consoles) == 0:
        raise error.TestFail("No tests defined, probably incorrect "
                             "configuration in tests_base.cfg")

    vm, consoles = _vm_create(no_consoles, no_serialports)

    # Copy allocator.py into guests
    pwd = os.path.join(os.environ['AUTODIR'], 'tests/kvm')
    vksmd_src = os.path.join(pwd, "scripts/virtio_guest.py")
    dst_dir = "/tmp"
    if not vm[0].copy_files_to(vksmd_src, dst_dir):
        raise error.TestFail("copy_files_to failed %s" % vm[0].name)

    # ACTUAL TESTING
    # Defines all available consoles; tests udev and sysfs
    conss = []
    for mode in consoles:
        for cons in mode:
            conss.append(cons[1:3])
    init_guest(vm, 10)
    on_guest("virt.init(%s)" % (conss), vm, 10)

    consoles = test_smoke(vm, consoles, test_smoke_params)
    test_loopback(vm, consoles, test_loopback_params)
    test_perf(vm, consoles, test_perf_params)

    # CLEANUP
    vm[1].close()
    vm[0].destroy(gracefully=False)
    shutil.rmtree(vm[2])

