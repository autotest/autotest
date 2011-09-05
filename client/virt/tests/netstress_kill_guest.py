import logging, os, signal, re, time
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
from autotest_lib.client.virt import aexpect, virt_utils


def run_netstress_kill_guest(test, params, env):
    """
    Try stop network interface in VM when other VM try to communicate.

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    def get_corespond_ip(ip):
        """
        Get local ip address which is used for contact ip.

        @param ip: Remote ip
        @return: Local corespond IP.
        """
        result = utils.run("ip route get %s" % (ip)).stdout
        ip = re.search("src (.+)", result)
        if ip is not None:
            ip = ip.groups()[0]
        return ip


    def get_ethernet_driver(session):
        """
        Get driver of network cards.

        @param session: session to machine
        """
        modules = []
        out = session.cmd("ls -l --color=never "
                          "/sys/class/net/*/device/driver/module")
        for module in out.split("\n"):
            modules.append(module.split("/")[-1])
        modules.remove("")
        return set(modules)


    def kill_and_check(vm):
        vm_pid = vm.get_pid()
        vm.destroy(gracefully=False)
        time.sleep(2)
        try:
            os.kill(vm_pid, 0)
            logging.error("VM is not dead")
            raise error.TestFail("VM is not dead after sending signal 0 to it")
        except OSError:
            logging.info("VM is dead")


    def netload_kill_problem(session_serial):
        netperf_dir = os.path.join(os.environ['AUTODIR'], "tests/netperf2")
        setup_cmd = params.get("setup_cmd")
        clean_cmd = params.get("clean_cmd")
        firewall_flush = "iptables -F"

        try:
            utils.run(firewall_flush)
        except:
            logging.warning("Could not flush firewall rules on guest")

        try:
            session_serial.cmd(firewall_flush)
        except aexpect.ShellError:
            logging.warning("Could not flush firewall rules on guest")

        for i in params.get("netperf_files").split():
            vm.copy_files_to(os.path.join(netperf_dir, i), "/tmp")

        guest_ip = vm.get_address(0)
        server_ip = get_corespond_ip(guest_ip)

        logging.info("Setup and run netperf on host and guest")
        session_serial.cmd(setup_cmd % "/tmp", timeout=200)
        utils.run(setup_cmd % netperf_dir)

        try:
            session_serial.cmd(clean_cmd)
        except:
            pass
        session_serial.cmd(params.get("netserver_cmd") % "/tmp")

        utils.run(clean_cmd, ignore_status=True)
        utils.run(params.get("netserver_cmd") % netperf_dir)

        server_netperf_cmd = params.get("netperf_cmd") % (netperf_dir, "TCP_STREAM",
                                        guest_ip, params.get("packet_size", "1500"))
        quest_netperf_cmd = params.get("netperf_cmd") % ("/tmp", "TCP_STREAM",
                                       server_ip, params.get("packet_size", "1500"))

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
            logging.info("Start heavy network load host <=> guest.")
            session_serial.sendline(quest_netperf_cmd)
            utils.BgJob(server_netperf_cmd)

            #Wait for create big network usage.
            time.sleep(10)
            kill_and_check(vm)

        finally:
            utils.run(clean_cmd, ignore_status=True)
            if tcpdump and pid:
                logging.debug("Resuming the background tcpdump")
                logging.info("pid is %s" % pid)
                os.kill(pid, signal.SIGCONT)


    def netdriver_kill_problem(session_serial):
        modules = get_ethernet_driver(session_serial)
        logging.debug(modules)
        for _ in range(50):
            for module in modules:
                session_serial.cmd("rmmod %s" % (module))
                time.sleep(0.2)
            for module in modules:
                session_serial.cmd("modprobe %s" % (module))
                time.sleep(0.2)
        kill_and_check(vm)


    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    login_timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=login_timeout)
    session.close()
    session_serial = vm.wait_for_serial_login(timeout=login_timeout)

    mode = params.get("mode")
    if mode == "driver":
        netdriver_kill_problem(session_serial)
    elif mode == "load":
        netload_kill_problem(session_serial)
