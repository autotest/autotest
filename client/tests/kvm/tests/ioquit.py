import logging, time, random
from autotest_lib.client.common_lib import error
import kvm_test_utils


def run_ioquit(test, params, env):
    """
    Emulate the poweroff under IO workload(dd so far) using kill -9.

    @param test: Kvm test object
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """

    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm,
                  timeout=int(params.get("login_timeout", 360)))
    session2 = kvm_test_utils.wait_for_login(vm,
                  timeout=int(params.get("login_timeout", 360)))
    try:
        bg_cmd = params.get("background_cmd")
        logging.info("Add IO workload for guest OS.")
        session.get_command_output(bg_cmd, timeout=60)
        check_cmd = params.get("check_cmd")
        session2.cmd(check_cmd, timeout=60)

        logging.info("Sleep for a while")
        time.sleep(random.randrange(30,100))
        session2.cmd(check_cmd, timeout=60)
        logging.info("Kill the virtual machine")
        vm.process.close()
    finally:
        session.close()
        session2.close()
