import logging, os, socket, time
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

def run_softlockup(test, params, env):
    """
    soft lockup/drift test with stress.

    1) Boot up a VM.
    2) Build stress on host and guest.
    3) run heartbeat with the given options on server and host.
    3) Run for a relatively long time length. ex: 12, 18 or 24 hours.
    4) Output the test result and observe drift.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    stress_setup_cmd = params.get("stress_setup_cmd")
    stress_cmd = params.get("stress_cmd")
    server_setup_cmd = params.get("server_setup_cmd")
    drift_cmd = params.get("drift_cmd")
    kill_stress_cmd = params.get("kill_stress_cmd")
    kill_monitor_cmd = params.get("kill_monitor_cmd")

    threshold = int(params.get("stress_threshold"))
    monitor_log_file_server = params.get("monitor_log_file_server")
    monitor_log_file_client = params.get("monitor_log_file_client")
    test_length = int(3600 * float(params.get("test_length")))
    monitor_port = int(params.get("monitor_port"))

    vm = env.get_vm(params["main_vm"])
    login_timeout = int(params.get("login_timeout", 360))
    stress_dir = os.path.join(os.environ['AUTODIR'], "tests/stress")
    monitor_dir = os.path.join(test.bindir, 'deps')


    def _kill_guest_programs(session, kill_stress_cmd, kill_monitor_cmd):
        logging.info("Kill stress and monitor on guest")
        try:
            session.cmd(kill_stress_cmd)
        except:
            pass
        try:
            session.cmd(kill_monitor_cmd)
        except:
            pass


    def _kill_host_programs(kill_stress_cmd, kill_monitor_cmd):
        logging.info("Kill stress and monitor on host")
        utils.run(kill_stress_cmd, ignore_status=True)
        utils.run(kill_monitor_cmd, ignore_status=True)


    def host():
        logging.info("Setup monitor server on host")
        # Kill previous instances of the host load programs, if any
        _kill_host_programs(kill_stress_cmd, kill_monitor_cmd)
        # Cleanup previous log instances
        if os.path.isfile(monitor_log_file_server):
            os.remove(monitor_log_file_server)
        # Opening firewall ports on host
        utils.run("iptables -F", ignore_status=True)

        # Run heartbeat on host
        utils.run(server_setup_cmd % (monitor_dir, threshold,
                                      monitor_log_file_server, monitor_port))

        logging.info("Build stress on host")
        # Uncompress and build stress on host
        utils.run(stress_setup_cmd % stress_dir)

        logging.info("Run stress on host")
        # stress_threads = 2 * n_cpus
        threads_host = 2 * utils.count_cpus()
        # Run stress test on host
        utils.run(stress_cmd % (stress_dir, threads_host))


    def guest():
        try:
            host_ip = socket.gethostbyname(socket.gethostname())
        except socket.error:
            try:
                # Hackish, but works well on stand alone (laptop) setups
                # with access to the internet. If this fails, well, then
                # not much else can be done...
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("redhat.com", 80))
                host_ip = s.getsockname()[0]
            except socket.error, (value, e):
                raise error.TestError("Could not determine host IP: %d %s" %
                                      (value, e))

        # Now, starting the guest
        vm.verify_alive()
        session = vm.wait_for_login(timeout=login_timeout)

        # Kill previous instances of the load programs, if any
        _kill_guest_programs(session, kill_stress_cmd, kill_monitor_cmd)
        # Clean up previous log instances
        session.cmd("rm -f %s" % monitor_log_file_client)

        # Opening firewall ports on guest
        try:
            session.cmd("iptables -F")
        except:
            pass

        # Get required files and copy them from host to guest
        monitor_path = os.path.join(test.bindir, 'deps', 'heartbeat_slu.py')
        stress_path = os.path.join(os.environ['AUTODIR'], "tests", "stress",
                                   "stress-1.0.4.tar.gz")
        vm.copy_files_to(monitor_path, "/tmp")
        vm.copy_files_to(stress_path, "/tmp")

        logging.info("Setup monitor client on guest")
        # Start heartbeat on guest
        session.cmd(params.get("client_setup_cmd") %
                    ("/tmp", host_ip, monitor_log_file_client, monitor_port))

        logging.info("Build stress on guest")
        # Uncompress and build stress on guest
        session.cmd(stress_setup_cmd % "/tmp", timeout=200)

        logging.info("Run stress on guest")
        # stress_threads = 2 * n_vcpus
        threads_guest = 2 * int(params.get("smp", 1))
        # Run stress test on guest
        session.cmd(stress_cmd % ("/tmp", threads_guest))

        # Wait and report
        logging.debug("Wait for %d s", test_length)
        time.sleep(test_length)

        # Kill instances of the load programs on both guest and host
        _kill_guest_programs(session, kill_stress_cmd, kill_monitor_cmd)
        _kill_host_programs(kill_stress_cmd, kill_monitor_cmd)

        # Collect drift
        drift = utils.system_output(drift_cmd %  monitor_log_file_server)
        logging.info("Drift noticed: %s", drift)


    host()
    guest()
