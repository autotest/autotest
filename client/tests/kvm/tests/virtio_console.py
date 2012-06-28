# TODO: Why VM recreation doesn't work?
"""
Collection of virtio_console and virtio_serialport tests.

@copyright: 2010-2012 Red Hat Inc.
"""
from collections import deque
import array
import logging
import os
import random
import select
import socket
import threading
import time
from autotest.client import utils
from autotest.client.shared import error
from autotest.client.virt import kvm_virtio_port, virt_env_process
from autotest.client.virt import virt_test_utils


@error.context_aware
def run_virtio_console(test, params, env):
    """
    KVM virtio_console test

    This test contain multiple tests. The name of the executed test is set
    by 'virtio_console_test' cfg variable. Main function with the set name
    with prefix 'test_' thus it's easy to find out which functions are
    tests and which are helpers.

    Every test has it's own cfg parameters, please see the actual test's
    docstring for details.

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment
    @raise error.TestNAError: if function with test_$testname is not present
    """
    ######################################################################
    # General helpers
    ######################################################################
    def get_vm_with_ports(no_consoles=0, no_serialports=0, spread=None,
                           quiet=False, strict=False):
        """
        Checks whether existing 'main_vm' fits the requirements, modifies
        it if needed and returns the VM object.
        @param no_console: Number of desired virtconsoles.
        @param no_serialport: Number of desired virtserialports.
        @param spread: Spread consoles across multiple virtio-serial-pcis.
        @param quiet: Notify user about VM recreation.
        @param strict: Whether no_consoles have to match or just exceed.
        @return: vm object matching the requirements.
        """
        # check the number of running VM's consoles
        vm = env.get_vm(params.get("main_vm"))

        if not vm:
            _no_serialports = -1
            _no_consoles = -1
        else:
            _no_serialports = 0
            _no_consoles = 0
            for port in vm.virtio_ports:
                if isinstance(port, kvm_virtio_port.VirtioSerial):
                    _no_serialports += 1
                else:
                    _no_consoles += 1
        _spread = int(params.get('virtio_port_spread', 2))
        if spread is None:
            spread = _spread
        if strict:
            if (_no_serialports != no_serialports or
                    _no_consoles != no_consoles):
                _no_serialports = -1
                _no_consoles = -1
        # If not enough ports, modify params and recreate VM
        if (_no_serialports < no_serialports or _no_consoles < no_consoles
                or spread != _spread):
            if not quiet:
                out = "tests reqirements are different from cfg: "
                if _no_serialports < no_serialports:
                    out += "serial_ports(%d), " % no_serialports
                if _no_consoles < no_consoles:
                    out += "consoles(%d), " % no_consoles
                if spread != _spread:
                    out += "spread(%s), " % spread
                logging.warning(out[:-2] + ". Modify config to speedup tests.")

            params['virtio_ports'] = ""
            if spread:
                params['virtio_port_spread'] = spread
            else:
                params['virtio_port_spread'] = 0

            for i in xrange(max(no_consoles, _no_consoles)):
                name = "console-%d" % i
                params['virtio_ports'] += " %s" % name
                params['virtio_port_type_%s' % name] = "console"

            for i in xrange(max(no_serialports, _no_serialports)):
                name = "serialport-%d" % i
                params['virtio_ports'] += " %s" % name
                params['virtio_port_type_%s' % name] = "serialport"

            if quiet:
                logging.debug("Recreating VM with more virtio ports.")
            else:
                logging.warning("Recreating VM with more virtio ports.")
            virt_env_process.preprocess_vm(test, params, env,
                                            params.get("main_vm"))
            vm = env.get_vm(params.get("main_vm"))

        vm.verify_kernel_crash()
        return vm

    def get_vm_with_worker(no_consoles=0, no_serialports=0, spread=None,
                               quiet=False):
        """
        Checks whether existing 'main_vm' fits the requirements, modifies
        it if needed and returns the VM object and guest_worker.
        @param no_console: Number of desired virtconsoles.
        @param no_serialport: Number of desired virtserialports.
        @param spread: Spread consoles across multiple virtio-serial-pcis.
        @param quiet: Notify user about VM recreation.
        @param strict: Whether no_consoles have to match or just exceed.
        @return: tuple (vm object matching the requirements,
                        initialized GuestWorker of the vm)
        """
        vm = get_vm_with_ports(no_consoles, no_serialports, spread, quiet)
        guest_worker = kvm_virtio_port.GuestWorker(vm)
        return vm, guest_worker

    def get_vm_with_single_port(port_type='serialport'):
        """
        Wrapper which returns vm, guest_worker and virtio_ports with at lest
        one port of the type specified by fction parameter.
        @param port_type: type of the desired virtio port.
        @return: tuple (vm object with at least 1 port of the port_type,
                        initialized GuestWorker of the vm,
                        list of virtio_ports of the port_type type)
        """
        if port_type == 'serialport':
            vm, guest_worker = get_vm_with_worker(no_serialports=1)
            virtio_ports = get_virtio_ports(vm)[1][0]
        else:
            vm, guest_worker = get_vm_with_worker(no_consoles=1)
            virtio_ports = get_virtio_ports(vm)[0][0]
        return vm, guest_worker, virtio_ports

    def get_virtio_ports(vm):
        """
        Returns separated virtconsoles and virtserialports
        @param vm: VM object
        @return: tuple (all virtconsoles, all virtserialports)
        """
        consoles = []
        serialports = []
        for port in vm.virtio_ports:
            if isinstance(port, kvm_virtio_port.VirtioSerial):
                serialports.append(port)
            else:
                consoles.append(port)
        return (consoles, serialports)

    @error.context_aware
    def cleanup(vm=None, guest_worker=None):
        """
        Cleanup function.
        @param vm: VM whose ports should be cleaned
        @param guest_worker: guest_worker which should be cleaned/exited
        """
        error.context("Cleaning virtio_ports.", logging.debug)
        logging.debug("Cleaning virtio_ports")
        if guest_worker:
            guest_worker.cleanup()
        if vm:
            for port in vm.virtio_ports:
                port.clean_port()
                port.close()
                port.mark_as_clean()

    ######################################################################
    # Smoke tests
    ######################################################################
    def test_open():
        """
        Try to open virtioconsole port.
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        (vm, guest_worker, port) = get_vm_with_single_port(
                                        params.get('virtio_console_params'))
        guest_worker.cmd("virt.open('%s')" % (port.name))
        port.open()
        cleanup(vm, guest_worker)

    def test_check_zero_sym():
        """
        Check if port /dev/vport0p0 was created.
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        if params.get('virtio_console_params') == 'serialport':
            vm, guest_worker = get_vm_with_worker(no_serialports=1)
        else:
            vm, guest_worker = get_vm_with_worker(no_consoles=1)
        guest_worker.cmd("virt.check_zero_sym()", 10)
        cleanup(vm, guest_worker)

    def test_multi_open():
        """
        Try to open the same port twice.
        @note: It should pass with virtconsole and fail with virtserialport
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        (vm, guest_worker, port) = get_vm_with_single_port(
                                        params.get('virtio_console_params'))
        guest_worker.cmd("virt.close('%s')" % (port.name), 10)
        guest_worker.cmd("virt.open('%s')" % (port.name), 10)
        (match, data) = guest_worker._cmd("virt.open('%s')" % (port.name), 10)
        # Console is permitted to open the device multiple times
        if port.is_console == "yes":    # is console?
            if match != 0:  # Multiple open didn't pass
                raise error.TestFail("Unexpected fail of opening the console"
                                     " device for the 2nd time.\n%s" % data)
        else:
            if match != 1:  # Multiple open didn't fail:
                raise error.TestFail("Unexpended pass of opening the"
                                     " serialport device for the 2nd time.")
            elif not "[Errno 24]" in data:
                raise error.TestFail("Multiple opening fail but with another"
                                     " exception %s" % data)
        port.open()
        cleanup(vm, guest_worker)

    def test_close():
        """
        Close the socket on the guest side
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        (vm, guest_worker, port) = get_vm_with_single_port(
                                        params.get('virtio_console_params'))
        guest_worker.cmd("virt.close('%s')" % (port.name), 10)
        port.close()
        cleanup(vm, guest_worker)

    def test_polling():
        """
        Test correct results of poll with different cases.
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        (vm, guest_worker, port) = get_vm_with_single_port(
                                        params.get('virtio_console_params'))
        # Poll (OUT)
        port.open()
        guest_worker.cmd("virt.poll('%s', %s)" % (port.name, select.POLLOUT),
                         2)

        # Poll (IN, OUT)
        port.sock.sendall("test")
        for test in [select.POLLIN, select.POLLOUT]:
            guest_worker.cmd("virt.poll('%s', %s)" % (port.name, test), 10)

        # Poll (IN HUP)
        # I store the socket informations and close the socket
        port.close()
        for test in [select.POLLIN, select.POLLHUP]:
            guest_worker.cmd("virt.poll('%s', %s)" % (port.name, test), 10)

        # Poll (HUP)
        guest_worker.cmd("virt.recv('%s', 4, 1024, False)" % (port.name), 10)
        guest_worker.cmd("virt.poll('%s', %s)" % (port.name, select.POLLHUP),
                         2)

        # Reconnect the socket
        port.open()
        # Redefine socket in consoles
        guest_worker.cmd("virt.poll('%s', %s)" % (port.name, select.POLLOUT),
                         2)
        cleanup(vm, guest_worker)

    def test_sigio():
        """
        Test whether port use generates sigio signals correctly.
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        (vm, guest_worker, port) = get_vm_with_single_port(
                                        params.get('virtio_console_params'))
        if port.is_open():
            port.close()

        # Enable sigio on specific port
        guest_worker.cmd("virt.async('%s', True, 0)" % (port.name), 10)
        guest_worker.cmd("virt.get_sigio_poll_return('%s')" % (port.name), 10)

        # Test sigio when port open
        guest_worker.cmd("virt.set_pool_want_return('%s', select.POLLOUT)" %
                         (port.name), 10)
        port.open()
        match = guest_worker._cmd("virt.get_sigio_poll_return('%s')" %
                                  (port.name), 10)[0]
        if match == 1:
            raise error.TestFail("Problem with HUP on console port.")

        # Test sigio when port receive data
        guest_worker.cmd("virt.set_pool_want_return('%s', select.POLLOUT |"
                         " select.POLLIN)" % (port.name), 10)
        port.sock.sendall("0123456789")
        guest_worker.cmd("virt.get_sigio_poll_return('%s')" % (port.name), 10)

        # Test sigio port close event
        guest_worker.cmd("virt.set_pool_want_return('%s', select.POLLHUP |"
                         " select.POLLIN)" % (port.name), 10)
        port.close()
        guest_worker.cmd("virt.get_sigio_poll_return('%s')" % (port.name), 10)

        # Test sigio port open event and persistence of written data on port.
        guest_worker.cmd("virt.set_pool_want_return('%s', select.POLLOUT |"
                         " select.POLLIN)" % (port.name), 10)
        port.open()
        guest_worker.cmd("virt.get_sigio_poll_return('%s')" % (port.name), 10)

        # Test event when erase data.
        guest_worker.cmd("virt.clean_port('%s')" % (port.name), 10)
        port.close()
        guest_worker.cmd("virt.set_pool_want_return('%s', select.POLLOUT)"
                         % (port.name), 10)
        port.open()
        guest_worker.cmd("virt.get_sigio_poll_return('%s')" % (port.name), 10)

        # Disable sigio on specific port
        guest_worker.cmd("virt.async('%s', False, 0)" % (port.name), 10)
        cleanup(vm, guest_worker)

    def test_lseek():
        """
        Tests the correct handling of lseek
        @note: lseek should fail
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        # The virt.lseek returns PASS when the seek fails
        (vm, guest_worker, port) = get_vm_with_single_port(
                                        params.get('virtio_console_params'))
        guest_worker.cmd("virt.lseek('%s', 0, 0)" % (port.name), 10)
        cleanup(vm, guest_worker)

    def test_rw_host_offline():
        """
        Try to read from/write to host on guest when host is disconnected.
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        (vm, guest_worker, port) = get_vm_with_single_port(
                                        params.get('virtio_console_params'))
        if port.is_open():
            port.close()

        guest_worker.cmd("virt.recv('%s', 0, 1024, False)" % port.name, 10)
        match, tmp = guest_worker._cmd("virt.send('%s', 10, True)" % port.name,
                                       10)
        if match is not None:
            raise error.TestFail("Write on guest while host disconnected "
                                 "didn't time out.\nOutput:\n%s"
                                 % tmp)

        port.open()

        if (port.sock.recv(1024) < 10):
            raise error.TestFail("Didn't received data from guest")
        # Now the cmd("virt.send('%s'... command should be finished
        guest_worker.cmd("print('PASS: nothing')", 10)
        cleanup(vm, guest_worker)

    def test_rw_host_offline_big_data():
        """
        Try to read from/write to host on guest when host is disconnected
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        (vm, guest_worker, port) = get_vm_with_single_port(
                                        params.get('virtio_console_params'))
        if port.is_open():
            port.close()

        port.clean_port()
        port.close()
        guest_worker.cmd("virt.clean_port('%s'),1024" % port.name, 10)
        match, tmp = guest_worker._cmd("virt.send('%s', (1024**3)*3, True, "
                               "is_static=True)" % port.name, 30)
        if match is None:
            raise error.TestFail("Write on guest while host disconnected "
                                 "didn't time out.\nOutput:\n%s"
                                 % tmp)

        time.sleep(20)

        port.open()

        rlen = 0
        while rlen < (1024 ** 3 * 3):
            ret = select.select([port.sock], [], [], 10.0)
            if (ret[0] != []):
                rlen += len(port.sock.recv(((4096))))
            elif rlen != (1024 ** 3 * 3):
                raise error.TestFail("Not all data was received,"
                                     "only %d from %d" % (rlen, 1024 ** 3 * 3))
        guest_worker.cmd("print('PASS: nothing')", 10)
        cleanup(vm, guest_worker)

    def test_rw_blocking_mode():
        """
        Try to read/write data in blocking mode.
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        # Blocking mode
        (vm, guest_worker, port) = get_vm_with_single_port(
                                        params.get('virtio_console_params'))
        port.open()
        guest_worker.cmd("virt.blocking('%s', True)" % port.name, 10)
        # Recv should timed out
        match, tmp = guest_worker._cmd("virt.recv('%s', 10, 1024, False)" %
                               port.name, 10)
        if match == 0:
            raise error.TestFail("Received data even when none was sent\n"
                                 "Data:\n%s" % tmp)
        elif match is not None:
            raise error.TestFail("Unexpected fail\nMatch: %s\nData:\n%s" %
                                 (match, tmp))
        port.sock.sendall("1234567890")
        # Now guest received the data end escaped from the recv()
        guest_worker.cmd("print('PASS: nothing')", 10)
        cleanup(vm, guest_worker)

    def test_rw_nonblocking_mode():
        """
        Try to read/write data in non-blocking mode.
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        # Non-blocking mode
        (vm, guest_worker, port) = get_vm_with_single_port(
                                        params.get('virtio_console_params'))
        port.open()
        guest_worker.cmd("virt.blocking('%s', False)" % port.name, 10)
        # Recv should return FAIL with 0 received data
        match, tmp = guest_worker._cmd("virt.recv('%s', 10, 1024, False)" %
                              port.name, 10)
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
        guest_worker.cmd("virt.recv('%s', 10, 1024, False)" % port.name, 10)
        cleanup(vm, guest_worker)

    def test_basic_loopback():
        """
        Simple loop back test with loop over two ports.
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        if params.get('virtio_console_params') == 'serialport':
            vm, guest_worker = get_vm_with_worker(no_serialports=2)
            send_port, recv_port = get_virtio_ports(vm)[1][:2]
        else:
            vm, guest_worker = get_vm_with_worker(no_consoles=2)
            send_port, recv_port = get_virtio_ports(vm)[0][:2]

        data = "Smoke test data"
        send_port.open()
        recv_port.open()
        # Set nonblocking mode
        send_port.sock.setblocking(0)
        recv_port.sock.setblocking(0)
        guest_worker.cmd("virt.loopback(['%s'], ['%s'], 1024, virt.LOOP_NONE)"
                         % (send_port.name, recv_port.name), 10)
        send_port.sock.sendall(data)
        tmp = ""
        i = 0
        while i <= 10:
            i += 1
            ret = select.select([recv_port.sock], [], [], 1.0)
            if ret:
                try:
                    tmp += recv_port.sock.recv(1024)
                except IOError, failure_detail:
                    logging.warn("Got err while recv: %s", failure_detail)
            if len(tmp) >= len(data):
                break
        if tmp != data:
            raise error.TestFail("Incorrect data: '%s' != '%s'",
                                 data, tmp)
        guest_worker.safe_exit_loopback_threads([send_port], [recv_port])
        cleanup(vm, guest_worker)

    ######################################################################
    # Loopback tests
    ######################################################################
    @error.context_aware
    def test_loopback():
        """
        Virtio console loopback test.

        Creates loopback on the vm machine between send_pt and recv_pts
        ports and sends length amount of data through this connection.
        It validates the correctness of the sent data.
        @param cfg: virtio_console_params - semicolon separated loopback
                        scenarios, only $source_console_type and (multiple)
                        destination_console_types are mandatory.
                            '$source_console_type@buffer_length:
                             $destination_console_type1@$buffer_length:...:
                             $loopback_buffer_length;...'
        @param cfg: virtio_console_test_time - how long to send the data
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        # PREPARE
        test_params = params.get('virtio_console_params')
        if not test_params:
            raise error.TestFail('No virtio_console_params specified')
        test_time = int(params.get('virtio_console_test_time', 60))
        no_serialports = 0
        no_consoles = 0
        for param in test_params.split(';'):
            no_serialports = max(no_serialports, param.count('serialport'))
            no_consoles = max(no_consoles, param.count('console'))
        vm, guest_worker = get_vm_with_worker(no_consoles, no_serialports)

        (consoles, serialports) = get_virtio_ports(vm)

        for param in test_params.split(';'):
            if not param:
                continue
            error.context("test_loopback: params %s" % param, logging.info)
            # Prepare
            param = param.split(':')
            idx_serialport = 0
            idx_console = 0
            buf_len = []
            if (param[0].startswith('console')):
                send_pt = consoles[idx_console]
                idx_console += 1
            else:
                send_pt = serialports[idx_serialport]
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
                    recv_pts.append(consoles[idx_console])
                    idx_console += 1
                else:
                    recv_pts.append(serialports[idx_serialport])
                    idx_serialport += 1
                if (len(parm[0].split('@')) == 2):
                    buf_len.append(int(parm[0].split('@')[1]))
                else:
                    buf_len.append(1024)
            # There must be sum(idx_*) consoles + last item as loopback buf_len
            if len(buf_len) == (idx_console + idx_serialport):
                buf_len.append(1024)

            for port in recv_pts:
                port.open()

            send_pt.open()

            if len(recv_pts) == 0:
                raise error.TestFail("test_loopback: incorrect recv consoles"
                                     "definition")

            threads = []
            queues = []
            for i in range(0, len(recv_pts)):
                queues.append(deque())

            # Start loopback
            tmp = "'%s'" % recv_pts[0].name
            for recv_pt in recv_pts[1:]:
                tmp += ", '%s'" % (recv_pt.name)
            guest_worker.cmd("virt.loopback(['%s'], [%s], %d, virt.LOOP_POLL)"
                             % (send_pt.name, tmp, buf_len[-1]), 10)

            exit_event = threading.Event()

            # TEST
            thread = kvm_virtio_port.ThSendCheck(send_pt, exit_event, queues,
                                   buf_len[0])
            thread.start()
            threads.append(thread)

            for i in range(len(recv_pts)):
                thread = kvm_virtio_port.ThRecvCheck(recv_pts[i], queues[i],
                                                    exit_event, buf_len[i + 1])
                thread.start()
                threads.append(thread)

            time.sleep(test_time)
            exit_event.set()
            # TEST END
            logging.debug('Joining th1')
            threads[0].join()
            tmp = "%d data sent; " % threads[0].idx
            for thread in threads[1:]:
                logging.debug('Joining th%s', thread)
                thread.join()
                tmp += "%d, " % thread.idx
            logging.info("test_loopback: %s data received and verified",
                         tmp[:-2])

            # Read-out all remaining data
            for recv_pt in recv_pts:
                while select.select([recv_pt.sock], [], [], 0.1)[0]:
                    recv_pt.sock.recv(1024)

            guest_worker.safe_exit_loopback_threads([send_pt], recv_pts)

            del exit_event
            del threads[:]
        cleanup(vm, guest_worker)

    def _process_stats(stats, scale=1.0):
        """
        Process the stats to human readable form.
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

    @error.context_aware
    def test_perf():
        """
        Tests performance of the virtio_console tunnel. First it sends the data
        from host to guest and than back. It provides informations about
        computer utilization and statistic informations about the throughput.

        @param cfg: virtio_console_params - semicolon separated scenarios:
                        '$console_type@$buffer_length:$test_duration;...'
        @param cfg: virtio_console_test_time - default test_duration time
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        test_params = params.get('virtio_console_params')
        if not test_params:
            raise error.TestFail('No virtio_console_params specified')
        test_time = int(params.get('virtio_console_test_time', 60))
        no_serialports = 0
        no_consoles = 0
        if test_params.count('serialport'):
            no_serialports = 1
        if test_params.count('serialport'):
            no_consoles = 1
        vm, guest_worker = get_vm_with_worker(no_consoles, no_serialports)
        (consoles, serialports) = get_virtio_ports(vm)
        consoles = [consoles, serialports]

        for param in test_params.split(';'):
            if not param:
                continue
            error.context("test_perf: params %s" % param, logging.info)
            # Prepare
            param = param.split(':')
            duration = test_time
            if len(param) > 1:
                try:
                    duration = float(param[1])
                except ValueError:
                    pass
            param = param[0].split('@')
            if len(param) > 1 and param[1].isdigit():
                buf_len = int(param[1])
            else:
                buf_len = 1024
            param = (param[0] == 'serialport')
            port = consoles[param][0]

            port.open()

            data = ""
            for _ in range(buf_len):
                data += "%c" % random.randrange(255)

            exit_event = threading.Event()
            time_slice = float(duration) / 100

            # HOST -> GUEST
            guest_worker.cmd('virt.loopback(["%s"], [], %d, virt.LOOP_NONE)'
                             % (port.name, buf_len), 10)
            thread = kvm_virtio_port.ThSend(port.sock, data, exit_event)
            stats = array.array('f', [])
            loads = utils.SystemLoad([(os.getpid(), 'autotest'),
                                      (vm.get_pid(), 'VM'), 0])
            loads.start()
            _time = time.time()
            thread.start()
            for _ in range(100):
                stats.append(thread.idx)
                time.sleep(time_slice)
            _time = time.time() - _time - duration
            logging.info("\n" + loads.get_cpu_status_string()[:-1])
            logging.info("\n" + loads.get_mem_status_string()[:-1])
            exit_event.set()
            thread.join()

            # Let the guest read-out all the remaining data
            while not guest_worker._cmd("virt.poll('%s', %s)"
                                        % (port.name, select.POLLIN), 10)[0]:
                time.sleep(1)

            guest_worker.safe_exit_loopback_threads([port], [])

            if (_time > time_slice):
                logging.error("Test ran %fs longer which is more than one "
                              "time slice", _time)
            else:
                logging.debug("Test ran %fs longer", _time)
            stats = _process_stats(stats[1:], time_slice * 1048576)
            logging.debug("Stats = %s", stats)
            logging.info("Host -> Guest [MB/s] (min/med/max) = %.3f/%.3f/%.3f",
                         stats[0], stats[len(stats) / 2], stats[-1])

            del thread

            # GUEST -> HOST
            exit_event.clear()
            stats = array.array('f', [])
            guest_worker.cmd("virt.send_loop_init('%s', %d)"
                             % (port.name, buf_len), 30)
            thread = kvm_virtio_port.ThRecv(port.sock, exit_event, buf_len)
            thread.start()
            loads.start()
            guest_worker.cmd("virt.send_loop()", 10)
            _time = time.time()
            for _ in range(100):
                stats.append(thread.idx)
                time.sleep(time_slice)
            _time = time.time() - _time - duration
            logging.info("\n" + loads.get_cpu_status_string()[:-1])
            logging.info("\n" + loads.get_mem_status_string()[:-1])
            guest_worker.cmd("virt.exit_threads()", 10)
            exit_event.set()
            thread.join()
            if (_time > time_slice):    # Deviation is higher than 1 time_slice
                logging.error(
                "Test ran %fs longer which is more than one time slice", _time)
            else:
                logging.debug("Test ran %fs longer", _time)
            stats = _process_stats(stats[1:], time_slice * 1048576)
            logging.debug("Stats = %s", stats)
            logging.info("Guest -> Host [MB/s] (min/med/max) = %.3f/%.3f/%.3f",
                         stats[0], stats[len(stats) / 2], stats[-1])

            del thread
            del exit_event
        cleanup(vm, guest_worker)

    ######################################################################
    # Migration tests
    ######################################################################
    @error.context_aware
    def _tmigrate(use_serialport, no_ports, no_migrations, blocklen, offline):
        """
        An actual migration test. It creates loopback on guest from first port
        to all remaining ports. Than it sends and validates the data.
        During this it tries to migrate the vm n-times.

        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param consoles: Field of virtio ports with the minimum of 2 items.
        @param parms: [media, no_migration, send-, recv-, loopback-buffer_len]
        """
        # PREPARE
        if use_serialport:
            vm, guest_worker = get_vm_with_worker(no_serialports=no_ports)
            ports = get_virtio_ports(vm)[1]
        else:
            vm, guest_worker = get_vm_with_worker(no_consoles=no_ports)
            ports = get_virtio_ports(vm)[0]

        # TODO BUG: sendlen = max allowed data to be lost per one migration
        # TODO BUG: using SMP the data loss is upto 4 buffers
        # 2048 = char.dev. socket size, parms[2] = host->guest send buffer size
        sendlen = 2 * 2 * max(kvm_virtio_port.SOCKET_SIZE, blocklen)
        if not offline:     # TODO BUG: online migration causes more loses
            # TODO: Online migration lose n*buffer. n depends on the console
            # troughput. FIX or analyse it's cause.
            sendlen = 1000 * sendlen
        for port in ports[1:]:
            port.open()

        ports[0].open()

        threads = []
        queues = []
        verified = []
        for i in range(0, len(ports[1:])):
            queues.append(deque())
            verified.append(0)

        tmp = "'%s'" % ports[1:][0].name
        for recv_pt in ports[1:][1:]:
            tmp += ", '%s'" % (recv_pt.name)
        guest_worker.cmd("virt.loopback(['%s'], [%s], %d, virt.LOOP_POLL)"
                         % (ports[0].name, tmp, blocklen), 10)

        exit_event = threading.Event()

        # TEST
        thread = kvm_virtio_port.ThSendCheck(ports[0], exit_event, queues,
                                             blocklen,
                                             migrate_event=threading.Event())
        thread.start()
        threads.append(thread)

        for i in range(len(ports[1:])):
            thread = kvm_virtio_port.ThRecvCheck(ports[1:][i], queues[i],
                                            exit_event, blocklen,
                                            sendlen=sendlen,
                                            migrate_event=threading.Event())
            thread.start()
            threads.append(thread)

        i = 0
        while i < 6:
            tmp = "%d data sent; " % threads[0].idx
            for thread in threads[1:]:
                tmp += "%d, " % thread.idx
            logging.debug("test_loopback: %s data received and verified",
                         tmp[:-2])
            i += 1
            time.sleep(2)

        for j in range(no_migrations):
            error.context("Performing migration number %s/%s"
                          % (j, no_migrations))
            vm = virt_test_utils.migrate(vm, env, 3600, "exec", 0,
                                         offline)
            if not vm:
                raise error.TestFail("Migration failed")

            # Set new ports to Sender and Recver threads
            # TODO: get ports in this function and use the right ports...
            if use_serialport:
                ports = get_virtio_ports(vm)[1]
            else:
                ports = get_virtio_ports(vm)[0]
            for i in range(len(threads)):
                threads[i].port = ports[i]
                threads[i].migrate_event.set()

            # OS is sometime a bit dizzy. DL=30
            #guest_worker.reconnect(vm, timeout=30)

            i = 0
            while i < 6:
                tmp = "%d data sent; " % threads[0].idx
                for thread in threads[1:]:
                    tmp += "%d, " % thread.idx
                logging.debug("test_loopback: %s data received and verified",
                             tmp[:-2])
                i += 1
                time.sleep(2)
            if not threads[0].isAlive():
                if exit_event.isSet():
                    raise error.TestFail("Exit event emited, check the log for"
                                         "send/recv thread failure.")
                else:
                    raise error.TestFail("Send thread died unexpectedly in "
                                         "migration %d", (j + 1))
            for i in range(0, len(ports[1:])):
                if not threads[i + 1].isAlive():
                    raise error.TestFail("Recv thread %d died unexpectedly in "
                                         "migration %d", i, (j + 1))
                if verified[i] == threads[i + 1].idx:
                    raise error.TestFail("No new data in %d console were "
                                         "transfered after migration %d",
                                         i, (j + 1))
                verified[i] = threads[i + 1].idx
            logging.info("%d out of %d migration(s) passed", (j + 1),
                         no_migrations)
            # If we get to this point let's assume all threads were reconnected
            for thread in threads:
                thread.migrate_event.clear()
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
                     "migrations", tmp[:-2], no_migrations)

        # CLEANUP
        guest_worker.safe_exit_loopback_threads([ports[0]], ports[1:])
        del exit_event
        del threads[:]
        cleanup(vm, guest_worker)

    def _test_migrate(offline):
        """
        Migration test wrapper, see the actual test_migrate_* tests for details
        """
        no_migrations = int(params.get("virtio_console_no_migrations", 5))
        no_ports = int(params.get("virtio_console_no_ports", 2))
        blocklen = int(params.get("virtio_console_blocklen", 1024))
        use_serialport = params.get('virtio_console_params') == "serialport"
        _tmigrate(use_serialport, no_ports, no_migrations, blocklen, offline)

    def test_migrate_offline():
        """
        Tests whether the virtio-{console,port} are able to survive the offline
        migration.
        @param cfg: virtio_console_no_migrations - how many times to migrate
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_console_blocklen - send/recv block length
        @param cfg: virtio_console_no_ports - minimum number of loopback ports
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        _test_migrate(offline=True)

    def test_migrate_online():
        """
        Tests whether the virtio-{console,port} are able to survive the online
        migration.
        @param cfg: virtio_console_no_migrations - how many times to migrate
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_console_blocklen - send/recv block length
        @param cfg: virtio_console_no_ports - minimum number of loopback ports
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        _test_migrate(offline=False)

    def _virtio_dev_add(vm, pci_id, port_id, console="no"):
        """
        Adds virtio serialport device.
        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param pci_id: Id of virtio-serial-pci device.
        @param port_id: Id of port.
        @param console: if "yes" inicialize console.
        """
        port = "serialport-"
        port_type = "virtserialport"
        if console == "yes":
            port = "console-"
            port_type = "virtconsole"
        port += "%d-%d" % (pci_id, port_id)
        ret = vm.monitors[0].cmd("device_add %s,"
                                    "bus=virtio_serial_pci%d.0,"
                                    "id=%s,"
                                    "name=%s"
                                    % (port_type, pci_id, port, port))
        if console == "no":
            vm.virtio_ports.append(kvm_virtio_port.VirtioSerial(port, None))
        else:
            vm.virtio_ports.append(kvm_virtio_port.VirtioConsole(port, None))
        if ret != "":
            logging.error(ret)

    def _virtio_dev_del(vm, pci_id, port_id):
        """
        Removes virtio serialport device.
        @param vm: Target virtual machine [vm, session, tmp_dir, ser_session].
        @param pci_id: Id of virtio-serial-pci device.
        @param port_id: Id of port.
        """
        for port in vm.virtio_ports:
            if port.name.endswith("-%d-%d" % (pci_id, port_id)):
                ret = vm.monitors[0].cmd("device_del %s" % (port.name))
                vm.virtio_ports.remove(port)
                if ret != "":
                    logging.error(ret)
                return
        raise error.TestFail("Removing port which is not in vm.virtio_ports"
                             " ...-%d-%d" % (pci_id, port_id))

    def test_hotplug():
        """
        Check the hotplug/unplug of virtio-consoles ports.
        TODO: co vsechno to opravdu testuje?
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_console_pause - pause between monitor commands
        """
        # TODO: Rewrite this test. It was left as it was before the virtio_port
        # conversion and looked too messy to repair it during conversion.
        # TODO: Split this test into multiple variants
        # TODO: Think about customizable params
        # TODO: use qtree to detect the right virtio-serial-pci name
        # TODO: QMP
        if params.get("virtio_console_params") == "serialport":
            console = "no"
        else:
            console = "yes"
        pause = int(params.get("virtio_console_pause", 1))
        logging.info("Timeout between hotplug operations t=%fs", pause)

        vm = get_vm_with_ports(1, 1, spread=0, quiet=True, strict=True)
        consoles = get_virtio_ports(vm)
        # send/recv might block for ever, set non-blocking mode
        consoles[0][0].open()
        consoles[1][0].open()
        consoles[0][0].sock.setblocking(0)
        consoles[1][0].sock.setblocking(0)
        logging.info("Test correct initialization of hotplug ports")
        for bus_id in range(1, 5):  # count of pci device
            ret = vm.monitors[0].cmd("device_add virtio-serial-pci,"
                                        "id=virtio_serial_pci%d" % (bus_id))
            if ret != "":
                logging.error(ret)
            for i in range(bus_id * 5 + 5):     # max ports 30
                _virtio_dev_add(vm, bus_id, i, console)
                time.sleep(pause)
        # Test correct initialization of hotplug ports
        time.sleep(10)  # Timeout for port initialization
        guest_worker = kvm_virtio_port.GuestWorker(vm)

        logging.info("Delete ports when ports are used")
        # Delete ports when ports are used.
        guest_worker.cmd("virt.loopback(['%s'], ['%s'], 1024,"
                 "virt.LOOP_POLL)" % (consoles[0][0].name,
                                      consoles[1][0].name), 10)
        exit_event = threading.Event()
        send = kvm_virtio_port.ThSend(consoles[0][0].sock, "Data", exit_event,
                                      quiet=True)
        recv = kvm_virtio_port.ThRecv(consoles[1][0].sock, exit_event,
                                      quiet=True)
        send.start()
        time.sleep(2)
        recv.start()

        # Try to delete ports under load
        ret = vm.monitors[0].cmd("device_del %s" % consoles[1][0].name)
        ret += vm.monitors[0].cmd("device_del %s" % consoles[0][0].name)
        vm.virtio_ports = vm.virtio_ports[2:]
        if ret != "":
            logging.error(ret)

        exit_event.set()
        send.join()
        recv.join()
        guest_worker.cmd("virt.exit_threads()", 10)
        guest_worker.cmd('guest_exit()', 10)

        logging.info("Trying to add maximum count of ports to one pci device")
        # Try to add ports
        for i in range(30):     # max port 30
            _virtio_dev_add(vm, 0, i, console)
            time.sleep(pause)
        guest_worker = kvm_virtio_port.GuestWorker(vm)
        guest_worker.cmd('guest_exit()', 10)

        logging.info("Trying delete and add again part of ports")
        # Try to delete ports
        for i in range(25):     # max port 30
            _virtio_dev_del(vm, 0, i)
            time.sleep(pause)
        guest_worker = kvm_virtio_port.GuestWorker(vm)
        guest_worker.cmd('guest_exit()', 10)

        # Try to add ports
        for i in range(5):      # max port 30
            _virtio_dev_add(vm, 0, i, console)
            time.sleep(pause)
        guest_worker = kvm_virtio_port.GuestWorker(vm)
        guest_worker.cmd('guest_exit()', 10)

        logging.info("Trying to add and delete one port 100 times")
        # Try 100 times add and delete one port.
        for i in range(100):
            _virtio_dev_del(vm, 0, 0)
            time.sleep(pause)
            _virtio_dev_add(vm, 0, 0, console)
            time.sleep(pause)
        guest_worker = kvm_virtio_port.GuestWorker(vm)
        cleanup(guest_worker=guest_worker)
        # VM is broken (params mismatches actual state)
        vm.destroy()

    @error.context_aware
    def test_hotplug_virtio_pci():
        """
        Tests hotplug/unplug of the virtio-serial-pci bus.
        @param cfg: virtio_console_pause - pause between monitor commands
        @param cfg: virtio_console_loops - how many loops to run
        """
        # TODO: QMP
        # TODO: check qtree for device presense
        pause = int(params.get("virtio_console_pause", 10))
        vm = get_vm_with_ports()
        idx = 1
        for i in xrange(int(params.get("virtio_console_loops", 2))):
            error.context("Hotpluging virtio_pci (iteration %d)" % i)
            ret = vm.monitors[0].cmd("device_add virtio-serial-pci,"
                                        "id=virtio_serial_pci%d" % (idx))
            time.sleep(pause)
            ret += vm.monitors[0].cmd("device_del virtio_serial_pci%d"
                                         % (idx))
            time.sleep(pause)
            if ret != "":
                raise error.TestFail("Error occured while hotpluging virtio-"
                                     "pci. Iteration %s, monitor output:\n%s"
                                     % (i, ret))

    ######################################################################
    # Destructive tests
    ######################################################################
    def test_rw_notconnect_guest():
        """
        Try to send to/read from guest on host while guest not recvs/sends any
        data.
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        vm = env.get_vm(params.get("main_vm"))
        use_serialport = params.get('virtio_console_params') == "serialport"
        if use_serialport:
            vm = get_vm_with_ports(no_serialports=1, strict=True)
        else:
            vm = get_vm_with_ports(no_consoles=1, strict=True)
        if use_serialport:
            port = get_virtio_ports(vm)[1][0]
        else:
            port = get_virtio_ports(vm)[0][1]
        if not port.is_open():
            port.open()
        else:
            port.close()
            port.open()

        port.sock.settimeout(20.0)

        loads = utils.SystemLoad([(os.getpid(), 'autotest'),
                                  (vm.get_pid(), 'VM'), 0])
        loads.start()

        try:
            sent1 = 0
            for _ in range(1000000):
                sent1 += port.sock.send("a")
        except socket.timeout:
            logging.info("Data sending to closed port timed out.")

        logging.info("Bytes sent to client: %d", sent1)
        logging.info("\n" + loads.get_cpu_status_string()[:-1])

        logging.info("Open and then close port %s", port.name)
        guest_worker = kvm_virtio_port.GuestWorker(vm)
        # Test of live and open and close port again
        guest_worker.cleanup()
        port.sock.settimeout(20.0)

        loads.start()
        try:
            sent2 = 0
            for _ in range(40000):
                sent2 = port.sock.send("a")
        except socket.timeout:
            logging.info("Data sending to closed port timed out.")

        logging.info("Bytes sent to client: %d", sent2)
        logging.info("\n" + loads.get_cpu_status_string()[:-1])
        loads.stop()
        if (sent1 != sent2):
            logging.warning("Inconsistent behavior: First sent %d bytes and "
                            "second sent %d bytes", sent1, sent2)

        port.sock.settimeout(None)
        guest_worker = kvm_virtio_port.GuestWorker(vm)
        cleanup(vm, guest_worker)

    def test_rmmod():
        """
        Remove and load virtio_console kernel module.
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        (vm, guest_worker, port) = get_vm_with_single_port(
                                        params.get('virtio_console_params'))
        guest_worker.cleanup()
        session = vm.wait_for_login()
        if session.cmd_status('lsmod | grep virtio_console'):
            raise error.TestNAError("virtio_console not loaded, probably "
                                    " not compiled as module. Can't test it.")
        session.cmd("rmmod -f virtio_console")
        session.cmd("modprobe virtio_console")
        guest_worker = kvm_virtio_port.GuestWorker(vm)
        guest_worker.cmd("virt.clean_port('%s'),1024" % port.name, 2)
        cleanup(vm, guest_worker)

    def test_max_ports():
        """
        Try to start and initialize machine with maximum supported number of
        virtio ports. (30)
        @param cfg: virtio_console_params - which type of virtio port to test
        """
        port_count = 30
        if params.get('virtio_console_params') == "serialport":
            logging.debug("Count of serialports: %d", port_count)
            vm = get_vm_with_ports(0, port_count, quiet=True)
        else:
            logging.debug("Count of consoles: %d", port_count)
            vm = get_vm_with_ports(port_count, 0, quiet=True)
        guest_worker = kvm_virtio_port.GuestWorker(vm)
        cleanup(vm, guest_worker)

    def test_max_serials_and_conosles():
        """
        Try to start and initialize machine with maximum supported number of
        virtio ports with 15 virtconsoles and 15 virtserialports.
        """
        port_count = 15
        logging.debug("Count of virtports: %d %d", port_count, port_count)
        vm = get_vm_with_ports(port_count, port_count, quiet=True)
        guest_worker = kvm_virtio_port.GuestWorker(vm)
        cleanup(vm, guest_worker)

    def test_shutdown():
        """
        Try to gently shutdown the machine while sending data through virtio
        port.
        @note: VM should shutdown safely.
        @param cfg: virtio_console_params - which type of virtio port to test
        @param cfg: virtio_port_spread - how many devices per virt pci (0=all)
        """
        if params.get('virtio_console_params') == 'serialport':
            vm, guest_worker = get_vm_with_worker(no_serialports=1)
        else:
            vm, guest_worker = get_vm_with_worker(no_consoles=1)
        ports, _ports = get_virtio_ports(vm)
        ports.extend(_ports)
        for port in ports:
            port.open()
        # If more than one, send data on the other ports
        for port in ports[1:]:
            guest_worker.cmd("virt.close('%s')" % (port.name), 2)
            guest_worker.cmd("virt.open('%s')" % (port.name), 2)
            try:
                os.system("dd if=/dev/random of='%s' bs=4096 &>/dev/null &"
                          % port.path)
            except Exception:
                pass
        # Just start sending, it won't finish anyway...
        guest_worker._cmd("virt.send('%s', 1024**3, True, is_static=True)"
                          % ports[0].name, 1)

        # Let the computer transfer some bytes :-)
        time.sleep(2)

        # Power off the computer
        vm.destroy(gracefully=True)
        # close the virtio ports on the host side
        for port in vm.virtio_ports:
            port.close()

    ######################################################################
    # Main
    # Executes test specified by virtio_console_test variable in cfg
    ######################################################################
    fce = None
    _fce = "test_" + params.get('virtio_console_test', '').strip()
    error.context("Executing test: %s" % _fce, logging.info)
    if _fce not in locals():
        raise error.TestNAError("Test %s doesn't exist. Check 'virtio_console_"
                                "test' variable in subtest.cfg" % _fce)
    else:
        fce = locals()[_fce]
        return fce()
