import logging, time
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils, kvm_utils

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

        s, o = vm.send_monitor_cmd("stop")
        if s:
            logging.error("stop failed: %r" % o)
        s, o = vm.send_monitor_cmd("savevm 1")
        if s:
            logging.error("savevm failed: %r" % o)
        s, o = vm.send_monitor_cmd("system_reset")
        if s:
            logging.error("system_reset: %r" % o)
        s, o = vm.send_monitor_cmd("loadvm 1")
        if s:
            logging.error("loadvm failed: %r" % o)
        s, o = vm.send_monitor_cmd("cont")
        if s:
            logging.error("cont failed: %r" % o)

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
