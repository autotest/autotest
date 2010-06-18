import logging, time
from autotest_lib.client.common_lib import error
import kvm_test_utils, kvm_utils


def run_guest_s4(test, params, env):
    """
    Suspend guest to disk, supports both Linux & Windows OSes.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    timeout = int(params.get("login_timeout", 360))
    session = kvm_test_utils.wait_for_login(vm, timeout=timeout)

    logging.info("Checking whether guest OS supports suspend to disk (S4)...")
    s, o = session.get_command_status_output(params.get("check_s4_support_cmd"))
    if "not enough space" in o:
        raise error.TestError("Check S4 support failed: %s" % o)
    elif s != 0:
        raise error.TestNAError("Guest OS does not support S4")

    logging.info("Waiting until all guest OS services are fully started...")
    time.sleep(float(params.get("services_up_timeout", 30)))

    # Start up a program (tcpdump for linux & ping for Windows), as a flag.
    # If the program died after suspend, then fails this testcase.
    test_s4_cmd = params.get("test_s4_cmd")
    session.sendline(test_s4_cmd)
    time.sleep(5)

    # Get the second session to start S4
    session2 = kvm_test_utils.wait_for_login(vm, timeout=timeout)

    # Make sure the background program is running as expected
    check_s4_cmd = params.get("check_s4_cmd")
    if session2.get_command_status(check_s4_cmd) != 0:
        raise error.TestError("Failed to launch '%s' as a background process" %
                              test_s4_cmd)
    logging.info("Launched background command in guest: %s" % test_s4_cmd)

    # Suspend to disk
    logging.info("Starting suspend to disk now...")
    session2.sendline(params.get("set_s4_cmd"))

    # Make sure the VM goes down
    suspend_timeout = 240 + int(params.get("smp")) * 60
    if not kvm_utils.wait_for(vm.is_dead, suspend_timeout, 2, 2):
        raise error.TestFail("VM refuses to go down. Suspend failed.")
    logging.info("VM suspended successfully. Sleeping for a while before "
                 "resuming it.")
    time.sleep(10)

    # Start vm, and check whether the program is still running
    logging.info("Resuming suspended VM...")
    if not vm.create():
        raise error.TestError("Failed to start VM after suspend to disk")

    # Log into the resumed VM
    relogin_timeout = int(params.get("relogin_timeout", 240))
    logging.info("Logging into resumed VM, timeout %s", relogin_timeout)
    session2 = kvm_utils.wait_for(vm.remote_login, relogin_timeout, 0, 2)
    if not session2:
        raise error.TestFail("Could not log into VM after resuming from "
                             "suspend to disk")

    # Check whether the test command is still alive
    logging.info("Checking if background command is still alive...")
    if session2.get_command_status(check_s4_cmd) != 0:
        raise error.TestFail("Background command '%s' stopped running. S4 "
                             "failed." % test_s4_cmd)

    logging.info("VM resumed successfuly after suspend to disk")
    session2.get_command_output(params.get("kill_test_s4_cmd"))
    session.close()
    session2.close()
