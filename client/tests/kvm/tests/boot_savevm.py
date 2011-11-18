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
    end_time = time.time() + float(params.get("savevm_timeout"))

    while time.time() < end_time:
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

        try:
            vm.wait_for_login(timeout=savevm_login_delay)
            break
        except Exception, detail:
            logging.debug(detail)

    if (time.time() > end_time):
        raise error.TestFail("Not possible to log onto the vm after %s s" %
                             params.get("savevm_timeout"))
