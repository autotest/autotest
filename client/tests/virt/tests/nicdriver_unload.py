import logging, os, time
from autotest.client import utils
from virttest import utils_test


def run_nicdriver_unload(test, params, env):
    """
    Test nic driver.

    1) Boot a VM.
    2) Get the NIC driver name.
    3) Repeatedly unload/load NIC driver.
    4) Multi-session TCP transfer on test interface.
    5) Check whether the test interface should still work.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    timeout = int(params.get("login_timeout", 360))
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    session_serial = vm.wait_for_serial_login(timeout=timeout)

    ethname = utils_test.get_linux_ifname(session_serial,
                                               vm.get_mac_address(0))

    # get ethernet driver from '/sys' directory.
    # ethtool can do the same thing and doesn't care about os type.
    # if we make sure all guests have ethtool, we can make a change here.
    sys_path = params.get("sys_path") % (ethname)

    # readlink in RHEL4.8 doesn't have '-e' param, should use '-f' in RHEL4.8.
    readlink_cmd = params.get("readlink_command", "readlink -e")
    driver = os.path.basename(session_serial.cmd("%s %s" % (readlink_cmd,
                                                 sys_path)).strip())

    logging.info("driver is %s", driver)

    try:
        threads = []
        for _ in range(int(params.get("sessions_num", "10"))):
            thread = utils.InterruptedThread(utils_test.run_file_transfer,
                                             (test, params, env))
            thread.start()
            threads.append(thread)

        time.sleep(10)
        while threads[0].isAlive():
            session_serial.cmd("sleep 10")
            session_serial.cmd("ifconfig %s down" % ethname)
            session_serial.cmd("modprobe -r %s" % driver)
            session_serial.cmd("modprobe %s" % driver)
            session_serial.cmd("ifconfig %s up" % ethname)
    except Exception:
        for thread in threads:
            thread.join(suppress_exception=True)
            raise
    else:
        for thread in threads:
            thread.join()
