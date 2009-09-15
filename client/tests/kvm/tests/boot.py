import logging, time
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils, kvm_utils


def run_boot(test, params, env):
    """
    KVM reboot test:
    1) Log into a guest
    2) Send a reboot command or a system_reset monitor command (optional)
    3) Wait until the guest is up again
    4) Log into the guest to verify it's up again

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm)

    try:
        if params.get("reboot_method") == "shell":
            # Send a reboot command to the guest's shell
            session.sendline(vm.get_params().get("reboot_command"))
            logging.info("Reboot command sent; waiting for guest to go "
                         "down...")
        elif params.get("reboot_method") == "system_reset":
            # Sleep for a while -- give the guest a chance to finish booting
            time.sleep(float(params.get("sleep_before_reset", 10)))
            # Send a system_reset monitor command
            vm.send_monitor_cmd("system_reset")
            logging.info("system_reset monitor command sent; waiting for "
                         "guest to go down...")
        else: return

        # Wait for the session to become unresponsive
        if not kvm_utils.wait_for(lambda: not session.is_responsive(),
                                  120, 0, 1):
            raise error.TestFail("Guest refuses to go down")

    finally:
        session.close()

    logging.info("Guest is down; waiting for it to go up again...")

    session = kvm_utils.wait_for(vm.remote_login, 240, 0, 2)
    if not session:
        raise error.TestFail("Could not log into guest after reboot")
    session.close()

    logging.info("Guest is up again")
