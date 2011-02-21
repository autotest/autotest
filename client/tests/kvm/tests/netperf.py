import logging, os, signal
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
import kvm_subprocess


def run_netperf(test, params, env):
    """
    Network stress test with netperf.

    1) Boot up a VM.
    2) Launch netserver on guest.
    3) Execute netperf client on host with different protocols.
    4) Output the test result.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    login_timeout = int(params.get("login_timeout", 360))
    session_serial = vm.wait_for_serial_login(timeout=login_timeout)

    netperf_dir = os.path.join(os.environ['AUTODIR'], "tests/netperf2")
    setup_cmd = params.get("setup_cmd")
    guest_ip = vm.get_address()
    result_file = os.path.join(test.resultsdir, "output_%s" % test.iteration)

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
    except kvm_subprocess.ShellError:
        logging.warning("Could not flush firewall rules on guest")

    session_serial.cmd(setup_cmd % "/tmp", timeout=200)
    session_serial.cmd(params.get("netserver_cmd") % "/tmp")

    tcpdump = env.get("tcpdump")
    pid = None
    if tcpdump:
        # Stop the background tcpdump process
        try:
            pid = int(utils.system_output("pidof tcpdump"))
            logging.debug("Stopping the background tcpdump")
            os.kill(pid, signal.SIGSTOP)
        except:
            pass

    try:
        logging.info("Setup and run netperf client on host")
        utils.run(setup_cmd % netperf_dir)
        list_fail = []
        result = open(result_file, "w")
        result.write("Netperf test results\n")

        for i in params.get("protocols").split():
            packet_size = params.get("packet_size", "1500")
            for size in packet_size.split():
                cmd = params.get("netperf_cmd") % (netperf_dir, i,
                                                   guest_ip, size)
                logging.info("Netperf: protocol %s", i)
                try:
                    netperf_output = utils.system_output(cmd,
                                                         retain_output=True)
                    result.write("%s\n" % netperf_output)
                except:
                    logging.error("Test of protocol %s failed", i)
                    list_fail.append(i)

        result.close()

        if list_fail:
            raise error.TestFail("Some netperf tests failed: %s" %
                                 ", ".join(list_fail))

    finally:
        session_serial.cmd_output("killall netserver")
        if tcpdump and pid:
            logging.debug("Resuming the background tcpdump")
            logging.info("pid is %s" % pid)
            os.kill(pid, signal.SIGCONT)
