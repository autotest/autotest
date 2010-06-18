import logging, time
from autotest_lib.client.common_lib import error
import kvm_test_utils, kvm_utils, kvm_monitor

def run_boot_savevm(test, params, env):
    """
    KVM boot savevm test:
    1) Start guest
    2) Periodically savevm/loadvm
    4) Log into the guest to verify it's up, fail after timeout seconds

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    savevm_delay = float(params.get("savevm_delay"))
    savevm_login_delay = float(params.get("savevm_login_delay"))
    logging.info("savevm_delay = %f" % savevm_delay)
    login_expire = time.time() + savevm_login_delay
    end_time = time.time() + float(params.get("savevm_timeout"))

    while time.time() < end_time:
        time.sleep(savevm_delay)

        try:
            vm.monitor.cmd("stop")
        except kvm_monitor.MonitorError, e:
            logging.error(e)
        try:
            # This should be replaced by a proper monitor method call
            vm.monitor.cmd("savevm 1")
        except kvm_monitor.MonitorError, e:
            logging.error(e)
        try:
            vm.monitor.cmd("system_reset")
        except kvm_monitor.MonitorError, e:
            logging.error(e)
        try:
            # This should be replaced by a proper monitor method call
            vm.monitor.cmd("loadvm 1")
        except kvm_monitor.MonitorError, e:
            logging.error(e)
        try:
            vm.monitor.cmd("cont")
        except kvm_monitor.MonitorError, e:
            logging.error(e)

        # Log in
        if (time.time() > login_expire):
            login_expire = time.time() + savevm_login_delay
            logging.info("Logging in after loadvm...")
            session = kvm_utils.wait_for(vm.remote_login, 1, 0, 1)
            if not session:
                logging.info("Failed to login")
            else:
                logging.info("Logged in to guest!")
                break

    if (time.time() > end_time):
        raise error.TestFail("fail: timeout")
