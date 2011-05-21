import logging
from autotest_lib.client.common_lib import error


def run_stop_continue(test, params, env):
    """
    Suspend a running Virtual Machine and verify its state.

    1) Boot the vm
    2) Suspend the vm through stop command
    3) Verify the state through info status command
    4) Check is the ssh session to guest is still responsive,
       if succeed, fail the test.

    @param test: Kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = float(params.get("login_timeout", 240))
    session = vm.wait_for_login(timeout=timeout)

    try:
        logging.info("Stop the VM")
        vm.monitor.cmd("stop")
        logging.info("Verifying the status of VM is 'paused'")
        vm.verify_status("paused")

        logging.info("Check the session is responsive")
        if session.is_responsive():
            raise error.TestFail("Session is still responsive after stop")

        logging.info("Try to resume the guest")
        vm.monitor.cmd("cont")
        logging.info("Verifying the status of VM is 'running'")
        vm.verify_status("running")

        logging.info("Try to re-log into guest")
        session = vm.wait_for_login(timeout=timeout)

    finally:
        session.close()
