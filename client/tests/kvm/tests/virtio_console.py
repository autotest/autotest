import socket, random, array, sys, os, tempfile, shutil, threading, select, re
import logging, time
from threading import Thread
from collections import deque
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils, kvm_utils, kvm_preprocessing


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
        def __init__(self, port, length, buffers, blocklen=32):
            """
            @param port: Destination port.
            @param length: Amount of data we want to send.
            @param buffers: Buffers for the control data (FIFOs).
            @param blocklen: Block length.
            """
            Thread.__init__(self)
            self.ExitState = True
            self.port = port[0]
            self.length = length
            self.buffers = buffers
            self.blocklen = blocklen


        def run(self):
            logging.debug("th_send %s: run", self.getName())
            idx = 0
            while idx < self.length:
                ret = select.select([], [self.port], [], 1.0)
                if ret:
                    # Generate blocklen of random data add them to the FIFO
                    # and send tham over virtio_console
                    buf = ""
                    for i in range(min(self.blocklen, self.length-idx)):
                        ch = "%c" % random.randrange(255)
                        buf += ch
                        for buffer in self.buffers:
                            buffer.append(ch)
                    idx += len(buf)
                    self.port.sendall(buf)
            logging.debug("th_send %s: exit(%d)", self.getName(), idx)
            if idx >= self.length:
                self.ExitState = False


    class th_send_loop(Thread):
        """
        Send data in the loop until the exit event is set
        """
        def __init__(self, port, data, event):
            """
            @param port: destination port
            @param data: the data intend to be send in a loop
            @param event: exit event
            """
            Thread.__init__(self)
            self.port = port
            self.data = data
            self.exitevent = event
            self.idx = 0


        def run(self):
            logging.debug("th_send_loop %s: run", self.getName())
            while not self.exitevent.isSet():
                self.idx += self.port.send(self.data)
            logging.debug("th_send_loop %s: exit(%d)", self.getName(),
                          self.idx)


    class th_recv(Thread):
        """
        Random data reciever/checker thread
        """
        def __init__(self, port, buffer, length, blocklen=32):
            """
            @param port: source port
            @param buffer: control data buffer (FIFO)
            @param length: amount of data we want to receive
            @param blocklen: block length
            """
            Thread.__init__(self)
            self.ExitState = True
            self.port = port[0]
            self.buffer = buffer
            self.length = length
            self.blocklen = blocklen


        def run(self):
            logging.debug("th_recv %s: run", self.getName())
            idx = 0
            while idx < self.length:
                ret = select.select([self.port], [], [], 1.0)
                if ret:
                    buf = self.port.recv(self.blocklen)
                    if buf:
                        # Compare the recvd data with the control data
                        for ch in buf:
                            if not ch == self.buffer.popleft():
                                error.TestFail("th_recv: incorrect data")
                    idx += len(buf)
            logging.debug("th_recv %s: exit(%d)", self.getName(), idx)
            if (idx >= self.length) and (len(self.buffer) == 0):
                self.ExitState = False


    class th_recv_null(Thread):
        """
        Receives data and throws it away.
        """
        def __init__(self, port, event, blocklen=32):
            """
            @param port: Data source port.
            @param event: Exit event.
            @param blocklen: Block length.
            """
            Thread.__init__(self)
            self.port = port[0]
            self._port_timeout = self.port.gettimeout()
            self.port.settimeout(0.1)
            self.exitevent = event
            self.blocklen = blocklen
            self.idx = 0


        def run(self):
            logging.debug("th_recv_null %s: run", self.getName())
            while not self.exitevent.isSet():
                # Workaround, it didn't work with select :-/
                try:
                    self.idx += len(self.port.recv(self.blocklen))
                except socket.timeout:
                    pass
            self.port.settimeout(self._port_timeout)
            logging.debug("th_recv_null %s: exit(%d)", self.getName(),
                          self.idx)

    seqTest = threading.Lock();


    class average_cpu_load():
        """
        Get average cpu load between start and get_load
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


        def start ( self ):
            """
            Start CPU usage measurement
            """
            self.startTime = time.time();
            self._get_cpu_load()


        def get_load(self):
            """
            Get and reset CPU usage
            @return: return group cpu (user[%], system[%], sum[%], testTime[s])
            """
            self.endTime = time.time()
            testTime =  self.endTime-self.startTime
            load = self._get_cpu_load()

            user = load[0] / testTime
            system = load[2] / testTime
            sum = user + system

            return (user, system, sum, testTime)


    class average_process_cpu_load():
        """
        Get average process cpu load between start and get_load
        """
        def __init__ (self, pid, name):
            self.old_load = [0, 0]
            self.startTime = 0
            self.endTime = 0
            self.pid = pid
            self.name = name


        def _get_cpu_load(self,pid):
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
                load = [0,0]
                for i in range(2):
                    load[i] = int(load_values[i])-self.old_load[i]

                for i in range(2):
                    self.old_load[i] = int(load_values[i])
                return load


        def start ( self ):
            """
            Start CPU usage measurement
            """
            self.startTime = time.time();
            self._get_cpu_load(self.pid)


        def get_load(self):
            """
            Get and reset CPU usage.

            @return: Group cpu
                    (pid, user[%], system[%], sum[%], testTime[s])
            """
            self.endTime = time.time()
            testTime =  self.endTime - self.startTime
            load = self._get_cpu_load(self.pid)

            user = load[0] / testTime
            system = load[1] / testTime
            sum = user + system

            return (self.name, self.pid, user, system, sum, testTime)


    def print_load(process, system):
        """
        Print load in tabular mode.

        @param process: list of process statistic tuples
        @param system: tuple of system cpu usage
        """

        logging.info("%-10s %6s %5s %5s %5s %11s",
                     "NAME", "PID","USER","SYS","SUM","TIME")
        for pr in process:
            logging.info("%-10s %6d %4.0f%% %4.0f%% %4.0f%% %10.3fs" % pr)
        logging.info("TOTAL:     ------ %4.0f%% %4.0f%% %4.0f%% %10.3fs" %
                     system)


    def process_stats(stats, scale=1.0):
        """
        Process and print the stats.

        @param stats: List of measured data.
        """
        if not stats:
            return None
        for i in range((len(stats)-1),0,-1):
            stats[i] = stats[i] - stats[i-1]
            stats[i] /= scale
        stats[0] /= scale
        stats = sorted(stats)
        return stats


    def _start_console_switch(vm, timeout=2):
        """
        Execute console_switch.py on guest, wait until it is initialized.

        @param vm: Informations about the guest.
        @param timeout: Timeout that will be used to verify if the script
                started properly.
        """
        logging.debug("Starting console_switch.py on guest %s", vm[0].name)
        vm[1].sendline("python /tmp/console_switch.py")
        (match, data) = vm[1].read_until_last_line_matches(["PASS:", "FAIL:"],
                                                           timeout)
        if match == 1 or match is None:
            raise error.TestFail("Command console_switch.py on guest %s failed."
                                 "\nreturn code: %s\n output:\n%s" %
                                 (vm[0].name, match, data))


    def _execute_console_switch(command, vm, timeout=2):
        """
        Execute given command inside the script's main loop, indicating the vm
        the command was executed on.

        @param command: Command that will be executed.
        @param vm: Informations about the guest
        @param timeout: Timeout used to verify expected output.

        @return: Tuple (match index, data)
        """
        logging.debug("Executing '%s' on console_switch.py loop, vm: %s,"
                      "timeout: %s", command, vm[0].name, timeout)
        vm[1].sendline(command)
        (match, data) = vm[1].read_until_last_line_matches(["PASS:","FAIL:"],
                                                             timeout)
        if match == 1 or match is None:
            raise error.TestFail("Failed to execute '%s' on console_switch.py, "
                                 "vm: %s, output:\n%s" %
                                 (command, vm[0].name, data))
        return (match, data)


    def socket_readall(sock, read_timeout, mesagesize):
        """
       Read everything from the socket.

        @param sock: socket
        @param read_timeout: read timeout
        @param mesagesize: size of message
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


    def _vm_create(no_console=3, no_serialport=3):
        """
        Creates the VM and connects the specified number of consoles and serial
        ports.

        @param no_console: number of desired virtconsoles
        @param no_serialport: number of desired virtserialports
        @return tuple with (guest information, consoles information)
            guest informations = [vm, session, tmp_dir]
            consoles informations = [consoles[], serialports[]]
        """
        consoles = []
        serialports = []
        tmp_dir = tempfile.mkdtemp(prefix="virtio-console-", dir="/tmp/")
        if not params.get('extra_params'):
            params['extra_params'] = ''
        params['extra_params'] += " -device virtio-serial"

        for i in range(0, no_console):
            params['extra_params'] += (" -chardev socket,path=%s/%d,id=c%d,"
                                       "server,nowait" % (tmp_dir, i, i))
            params['extra_params'] += (" -device virtconsole,chardev=c%d,"
                                       "name=org.fedoraproject.console.%d,"
                                       "id=c%d" % (i, i, i))

        for i in  range(no_console, no_console + no_serialport):
            params['extra_params'] += (" -chardev socket,path=%s/%d,id=p%d,"
                                       "server,nowait" % (tmp_dir, i, i))
            params['extra_params'] += (" -device virtserialport,chardev=p%d,"
                                       "name=org.fedoraproject.data.%d,id=p%d" %
                                       (i, i, i))

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
            consoles.append([sock, "org.fedoraproject.console.%d" % i, "yes"])

        for i in range(no_console, no_console + no_serialport):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect("%s/%d" % (tmp_dir, i))
            serialports.append([sock, "org.fedoraproject.data.%d" % i, "no"])

        return [vm, session, tmp_dir], [consoles, serialports]


    def test_smoke(vm, consoles, params):
        """
        Virtio console smoke test.

        Creates loopback on the vm machine between the ports[>=2] provided and
        sends the data

        @param vm: target virtual machine [vm, session, tmp_dir]
        @param consoles: a field of virtio ports with the minimum of 2 items
        @param params: test parameters '$console_type:$data;...'
        """
        logging.info("Smoke test: Send data on the sender port, "
                     "verify data integrity on the receiving port")
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
            _start_console_switch(vm, 10.0)

            # TEST
            _execute_console_switch('start_switch([%s], [%s])' %
                                   (str(send_pt[1:3]), str(recv_pt[1:3])),
                                   vm, 2.0)

            send_pt[0].sendall(data)
            d = socket_readall(recv_pt[0], 1.0, len(data))
            if data != d:
                raise error.TestFail("test_smoke: received data on port %s "
                                     "does not match data sent through "
                                     "port %s" % (recv_pt, send_pt))

            vm[1].sendline('die()')

        logging.info("test_smoke: PASS")


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
                 $destination_console_type1@buffer_length:...:
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
                buf_len.append(32)
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
                    buf_len.append(32)
            # There must be sum(idx_*) consoles + last item as loopback buf_len
            if len(buf_len) == (idx_console + idx_serialport):
                buf_len.append(32)

            if len(recv_pts) == 0:
                raise error.TestFail("test_loopback: incorrect recv consoles"
                                     "definition")
            threads = []
            buffers = []
            for i in range(0, len(recv_pts)):
                buffers.append(deque())

            _start_console_switch(vm, 10.0)
            tmp = str(recv_pts[0][1:3])
            for recv_pt in recv_pts[1:]:
                tmp += ", " + str(recv_pt[1:3])
            _execute_console_switch('start_switch([%s], [%s], %d)' %
                                    (str(send_pt[1:3]), tmp, buf_len[-1]),
                                    vm, 2.0)

            # TEST
            thread = th_send(send_pt, 1048576, buffers, buf_len[0])
            thread.start()
            threads.append(thread)

            for i in range(len(recv_pts)):
                thread = th_recv(recv_pts[i], buffers[i], 1048576,
                                 buf_len[i+1])
                thread.start()
                threads.append(thread)

            dead_threads = False
            # Send + recv threads, DL 60s
            for i in range(60):
                for t in threads:
                    if not t.is_alive():
                        if t.ExitState:
                            error.TestFail("test_loopback: send/recv thread "
                                           "failed")
                        dead_threads = True
                if dead_threads:
                    break
                tmp = ""
                for buf in buffers:
                    tmp += str(len(buf)) + ", "
                logging.debug("test_loopback: buffer length (%s)", tmp[:-2])
                time.sleep(1)

            if not dead_threads:
                raise error.TestFail("test_loopback: send/recv timeout")
            # at this point at least one thread died. It should be the send one.

            # Wait for recv threads to finish their's work
            for i in range(60):
                dead_threads = True
                for t in threads:
                    if t.is_alive():
                        dead_threads = False
                # There are no living threads
                if dead_threads:
                    break
                tmp = ""
                for buf in buffers:
                    tmp += str(len(buf)) + ", "
                logging.debug("test_loopback: buffer length (%s)", tmp[:-2])
                time.sleep(1)

            for t in threads:
                if t.ExitState:
                    raise error.TestFail("test_loopback: recv thread failed")

            # At least one thread is still alive
            if not dead_threads:
                raise error.TestFail("test_loopback: recv timeout")

            vm[1].sendline("die()")

        logging.info("test_loopback: PASS")


    def test_perf(vm, consoles, params):
        """
        Virtio console performance test.

        Tests performance of the virtio_console tunel. First it sends the data
        from host to guest and then back. It provides informations about
        computer utilization and statistic information about the throughput.

        @param vm: target virtual machine [vm, session, tmp_dir]
        @param consoles: a field of virtio ports with the minimum of 2 items
        @param params: test parameters:
                '$console_type@buffer_length:$test_duration;...'
        """
        logging.info("Performance test: Measure performance for the "
                     "virtio console tunnel")
        # PREPARE
        for param in params.split(';'):
            if not param:
                continue
            logging.info("test_perf: params: %s", param)
            param = param.split(':')
            if len(param) > 1 and param[1].isdigit():
                duration = float(param[1])
            else:
                duration = 30.0
            param = param[0].split('@')
            if len(param) > 1 and param[1].isdigit():
                buf_len = int(param[1])
            else:
                buf_len = 32
            if param[0] == "serialport":
                port = consoles[1][0]
            else:
                port = consoles[0][0]
            data = array.array("L")
            for i in range(max((buf_len / data.itemsize), 1)):
                data.append(random.randrange(sys.maxint))

            ev = threading.Event()
            thread = th_send_loop(port[0], data.tostring(), ev)

            _start_console_switch(vm, 10.0)

            _execute_console_switch('start_switch([%s], [], %d)' %
                                    (str(port[1:3]), buf_len), vm, 2.0)

            # TEST
            # Host -> Guest
            load = []
            stats = array.array('f', [])
            slice = float(duration)/100
            load.append(average_cpu_load())
            load.append(average_process_cpu_load(os.getpid(), 'autotest'))
            load.append(average_process_cpu_load(vm[0].get_pid(), 'VM'))
            for ld in load:
                ld.start()
            _time = time.time()
            thread.start()
            for i in range(100):
                stats.append(thread.idx)
                time.sleep(slice)
            _time = time.time() - _time - duration
            print_load([load[1].get_load(), load[2].get_load()],
                       load[0].get_load())
            ev.set()
            thread.join()
            if (_time > slice):
                logging.error("test_perf: test ran %fs longer "
                              "(more than 1 slice)", _time)
            else:
                logging.debug("test_perf: test ran %fs longer "
                              "(less than 1 slice)", _time)
            stats = process_stats(stats[1:], slice*1024*1024)
            logging.info("Host -> Guest [MB/s] min/med/max = %.3f/%.3f/%.3f",
                         stats[0], stats[len(stats)/2], stats[-1])
            time.sleep(5)
            vm[1].sendline("die()")

            # Guest -> Host
            _start_console_switch(vm, 10.0)
            _execute_console_switch('sender_prepare(%s, %d)' %
                                    (str(port[1:3]), buf_len), vm, 10)
            stats = array.array('f', [])
            ev.clear()
            thread = th_recv_null(port, ev, buf_len)
            thread.start()
            # reset load measures
            for ld in load:
                ld.get_load()
            _execute_console_switch('sender_start()', vm, 2)
            _time = time.time()
            for i in range(100):
                stats.append(thread.idx)
                time.sleep(slice)
            _time = time.time() - _time - duration
            print_load([load[1].get_load(), load[2].get_load()],
                       load[0].get_load())
            vm[1].sendline("die()")
            time.sleep(5)
            ev.set()
            thread.join()
            if (_time > slice): # Deviation is higher than 1 slice
                logging.error("test_perf: test ran %fs longer "
                              "(more than 1 slice)", _time)
            else:
                logging.debug("test_perf: test ran %fs longer "
                              "(less than 1 slice)", _time)
            stats = process_stats(stats[1:], slice*1024*1024)
            logging.info("Guest -> Host [MB/s] min/med/max = %.3f/%.3f/%.3f",
                         stats[0], stats[len(stats)/2], stats[-1])
            for ld in load:
                del(ld)

        logging.info("test_perf: PASS")


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

    vm, consoles = _vm_create(no_consoles, no_serialports)

    # Copy console_switch.py into guests
    pwd = os.path.join(os.environ['AUTODIR'], 'tests/kvm')
    vksmd_src = os.path.join(pwd, "scripts/console_switch.py")
    dst_dir = "/tmp"
    if not vm[0].copy_files_to(vksmd_src, dst_dir):
        raise error.TestFail("copy_files_to failed %s" % vm[0].name)

    # ACTUAL TESTING
    test_smoke(vm, consoles, test_smoke_params)
    test_loopback(vm, consoles, test_loopback_params)
    test_perf(vm, consoles, test_perf_params)

    # CLEANUP
    vm[1].close()
    vm[0].destroy(gracefully=False)
    shutil.rmtree(vm[2])
