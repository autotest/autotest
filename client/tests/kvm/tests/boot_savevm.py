import logging, time
from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import kvm_monitor


def run_boot_savevm(test, params, env):
    """
    KVM boot savevm test:

    1) Start guest.
    2) Periodically savevm/loadvm.
    4) Log into the guest to verify it's up, fail after timeout seconds.

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    savevm_delay = float(params.get("savevm_delay"))
    savevm_login_delay = float(params.get("savevm_login_delay"))
    savevm_login_timeout = float(params.get("savevm_timeout"))
    start_time = time.time()

    cycles = 0

    successful_login = False
    while (time.time() - start_time) < savevm_login_timeout:
        logging.info("Save/load cycle %d", cycles + 1)
        time.sleep(savevm_delay)
        try:
            vm.monitor.cmd("stop")
        except kvm_monitor.MonitorError, e:
            logging.error(e)
        try:
            vm.monitor.cmd("savevm 1")
        except kvm_monitor.MonitorError, e:
            logging.error(e)
        try:
            vm.monitor.cmd("system_reset")
        except kvm_monitor.MonitorError, e:
            logging.error(e)
        try:
            vm.monitor.cmd("loadvm 1")
        except kvm_monitor.MonitorError, e:
            logging.error(e)
        try:
            vm.monitor.cmd("cont")
        except kvm_monitor.MonitorError, e:
            logging.error(e)

        vm.verify_kernel_crash()

        try:
            vm.wait_for_login(timeout=savevm_login_delay)
            successful_login = True
            break
        except:
            pass

        cycles += 1

    time_elapsed = int(time.time() - start_time)
    info = "after %s s, %d load/save cycles" % (time_elapsed, cycles + 1)
    if not successful_login:
        raise error.TestFail("Can't log on '%s' %s" % (vm.name, info))
    else:
        logging.info("Test ended %s", info)
