import logging, os, signal
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
from autotest_lib.client.virt import aexpect, virt_utils

def run_netperf(test, params, env):
    """
    Network stress test with netperf.

    1) Boot up a VM with multiple nics.
    2) Launch netserver on guest.
    3) Execute multiple netperf clients on host in parallel
       with different protocols.
    4) Output the test result.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    login_timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=login_timeout)
    session.close()
    session_serial = vm.wait_for_serial_login(timeout=login_timeout)

    netperf_dir = os.path.join(os.environ['AUTODIR'], "tests/netperf2")
    setup_cmd = params.get("setup_cmd")

    firewall_flush = "iptables -F"
    session_serial.cmd_output(firewall_flush)
    try:
        utils.run("iptables -F")
    except:
        pass

    for i in params.get("netperf_files").split():
        vm.copy_files_to(os.path.join(netperf_dir, i), "/tmp")

    try:
        session_serial.cmd(firewall_flush)
    except aexpect.ShellError:
        logging.warning("Could not flush firewall rules on guest")

    session_serial.cmd(setup_cmd % "/tmp", timeout=200)
    session_serial.cmd(params.get("netserver_cmd") % "/tmp")

    if "tcpdump" in env and env["tcpdump"].is_alive():
        # Stop the background tcpdump process
        try:
            logging.debug("Stopping the background tcpdump")
            env["tcpdump"].close()
        except:
            pass

    def netperf(i=0):
        guest_ip = vm.get_address(i)
        logging.info("Netperf_%s: netserver %s" % (i, guest_ip))
        result_file = os.path.join(test.resultsdir, "output_%s_%s"
                                   % (test.iteration, i ))
        list_fail = []
        result = open(result_file, "w")
        result.write("Netperf test results\n")

        for p in params.get("protocols").split():
            packet_size = params.get("packet_size", "1500")
            for size in packet_size.split():
                cmd = params.get("netperf_cmd") % (netperf_dir, p,
                                                   guest_ip, size)
                logging.info("Netperf_%s: protocol %s" % (i, p))
                try:
                    netperf_output = utils.system_output(cmd,
                                                         retain_output=True)
                    result.write("%s\n" % netperf_output)
                except:
                    logging.error("Test of protocol %s failed", p)
                    list_fail.append(p)

        result.close()
        if list_fail:
            raise error.TestFail("Some netperf tests failed: %s" %
                                 ", ".join(list_fail))

    try:
        logging.info("Setup and run netperf clients on host")
        utils.run(setup_cmd % netperf_dir)

        bg = []
        nic_num = len(params.get("nics").split())
        for i in range(nic_num):
            bg.append(virt_utils.Thread(netperf, (i,)))
            bg[i].start()

        completed = False
        while not completed:
            completed = True
            for b in bg:
                if b.isAlive():
                    completed = False
    finally:
        try:
            for b in bg:
                if b:
                    b.join()
        finally:
            session_serial.cmd_output("killall netserver")
