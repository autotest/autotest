import logging, time
from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import virt_utils


@error.context_aware
def run_guest_s4(test, params, env):
    """
    Suspend guest to disk, supports both Linux & Windows OSes.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    error.base_context("before S4")
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

    error.context("checking whether guest OS supports S4", logging.info)
    session.cmd(params.get("check_s4_support_cmd"))
    error.context()

    logging.info("Waiting until all guest OS services are fully started...")
    time.sleep(float(params.get("services_up_timeout", 30)))

    # Start up a program (tcpdump for linux & ping for Windows), as a flag.
    # If the program died after suspend, then fails this testcase.
    test_s4_cmd = params.get("test_s4_cmd")
    session.sendline(test_s4_cmd)
    time.sleep(5)

    # Get the second session to start S4
    session2 = vm.wait_for_login(timeout=timeout)

    # Make sure the background program is running as expected
    error.context("making sure background program is running")
    check_s4_cmd = params.get("check_s4_cmd")
    session2.cmd(check_s4_cmd)
    logging.info("Launched background command in guest: %s", test_s4_cmd)
    error.context()
    error.base_context()

    # Suspend to disk
    logging.info("Starting suspend to disk now...")
    session2.sendline(params.get("set_s4_cmd"))

    # Make sure the VM goes down
    error.base_context("after S4")
    suspend_timeout = 240 + int(params.get("smp")) * 60
    if not virt_utils.wait_for(vm.is_dead, suspend_timeout, 2, 2):
        raise error.TestFail("VM refuses to go down. Suspend failed.")
    logging.info("VM suspended successfully. Sleeping for a while before "
                 "resuming it.")
    time.sleep(10)

    # Start vm, and check whether the program is still running
    logging.info("Resuming suspended VM...")
    vm.create()

    # Log into the resumed VM
    relogin_timeout = int(params.get("relogin_timeout", 240))
    logging.info("Logging into resumed VM, timeout %s", relogin_timeout)
    session2 = vm.wait_for_login(timeout=relogin_timeout)

    # Check whether the test command is still alive
    error.context("making sure background program is still running",
                  logging.info)
    session2.cmd(check_s4_cmd)
    error.context()

    logging.info("VM resumed successfuly after suspend to disk")
    session2.cmd_output(params.get("kill_test_s4_cmd"))
    session.close()
    session2.close()
