import logging, time
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils, kvm_utils


def run_shutdown(test, params, env):
    """
    KVM shutdown test:
    1) Log into a guest
    2) Send a shutdown command to the guest, or issue a system_powerdown
       monitor command (depending on the value of shutdown_method)
    3) Wait until the guest is down

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm)

    try:
        if params.get("shutdown_method") == "shell":
            # Send a shutdown command to the guest's shell
            session.sendline(vm.get_params().get("shutdown_command"))
            logging.info("Shutdown command sent; waiting for guest to go "
                         "down...")
        elif params.get("shutdown_method") == "system_powerdown":
            # Sleep for a while -- give the guest a chance to finish booting
            time.sleep(float(params.get("sleep_before_powerdown", 10)))
            # Send a system_powerdown monitor command
            vm.send_monitor_cmd("system_powerdown")
            logging.info("system_powerdown monitor command sent; waiting for "
                         "guest to go down...")

        if not kvm_utils.wait_for(vm.is_dead, 240, 0, 1):
            raise error.TestFail("Guest refuses to go down")

        logging.info("Guest is down")

    finally:
        session.close()
