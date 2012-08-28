import os
from virttest import utils_test


def run_autotest(test, params, env):
    """
    Run an autotest test inside a guest.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

    # Collect test parameters
    timeout = int(params.get("test_timeout", 300))
    control_path = os.path.join(test.virtdir, "autotest_control",
                                params.get("test_control_file"))
    outputdir = test.outputdir

    utils_test.run_autotest(vm, session, control_path, timeout, outputdir,
                                 params)
