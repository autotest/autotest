import logging, time
from autotest_lib.client.common_lib import error
import kvm_test_utils, kvm_utils


def run_guest_s4(test, params, env):
    """
    Suspend guest to disk,supports both Linux & Windows OSes.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm)

    logging.info("Checking whether guest OS supports suspend to disk (S4)")
    status = session.get_command_status(params.get("check_s4_support_cmd"))
    if status is None:
        logging.error("Failed to check if guest OS supports S4")
    elif status != 0:
        raise error.TestFail("Guest OS does not support S4")

    logging.info("Wait until all guest OS services are fully started")
    time.sleep(params.get("services_up_timeout"))

    # Start up a program (tcpdump for linux & ping for Windows), as a flag.
    # If the program died after suspend, then fails this testcase.
    test_s4_cmd = params.get("test_s4_cmd")
    session.sendline(test_s4_cmd)

    # Get the second session to start S4
    session2 = kvm_test_utils.wait_for_login(vm)

    check_s4_cmd = params.get("check_s4_cmd")
    if session2.get_command_status(check_s4_cmd):
        raise error.TestError("Failed to launch '%s' as a background process" %
                              test_s4_cmd)
    logging.info("Launched background command in guest: %s" % test_s4_cmd)

    # Suspend to disk
    logging.info("Start suspend to disk now...")
    session2.sendline(params.get("set_s4_cmd"))

    if not kvm_utils.wait_for(vm.is_dead, 360, 30, 2):
        raise error.TestFail("VM refuses to go down. Suspend failed")
    logging.info("VM suspended successfully. Wait before booting it again.")
    time.sleep(10)

    # Start vm, and check whether the program is still running
    logging.info("Start suspended VM...")

    if not vm.create():
        raise error.TestError("Failed to start VM after suspend to disk")
    if not vm.is_alive():
        raise error.TestError("VM seems to be dead after it was suspended")

    # Check whether test command still alive
    logging.info("Checking if background command is still alive")
    if session2.get_command_status(check_s4_cmd):
        raise error.TestFail("Command %s failed. S4 failed" % test_s4_cmd)

    logging.info("VM resumed successfuly after suspend to disk")
    session2.sendline(params.get("kill_test_s4_cmd"))
    session.close()
    session2.close()
