import logging, time, shutil
from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import virt_utils


def run_watchdog(test, params, env):
    """
    Configure watchdog, crash the guest and check if watchdog_action occurs.
    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)
    relogin_timeout = int(params.get("relogin_timeout", 240))
    watchdog_enable_cmd = "chkconfig watchdog on && service watchdog start"

    def watchdog_action_reset():
        """
        Trigger a crash dump through sysrq-trigger
        Ensure watchdog_action(reset) occur.
        """
        session = vm.wait_for_login(timeout=timeout)

        logging.info("Triggering crash on vm")
        crash_cmd = "echo c > /proc/sysrq-trigger"
        session.sendline(crash_cmd)

        if not virt_utils.wait_for(lambda: not session.is_responsive(),
                                   240, 0, 1):
            raise error.TestFail("Could not trigger crash")

        logging.info("Waiting for kernel watchdog_action to take place")
        session = vm.wait_for_login(timeout=relogin_timeout)

    logging.info("Enabling watchdog service...")
    session.cmd(watchdog_enable_cmd, timeout=320)
    watchdog_action_reset()

    # Close stablished session
    session.close()
