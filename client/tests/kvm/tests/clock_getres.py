import logging, time, os
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
import kvm_test_utils, kvm_utils


def run_clock_getres(test, params, env):
    """
    Verify if guests using kvm-clock as the time source have a sane clock
    resolution.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    t_name = "test_clock_getres"
    base_dir = "/tmp"

    deps_dir = os.path.join(test.bindir, "deps", t_name)
    os.chdir(deps_dir)
    try:
        utils.system("make clean")
        utils.system("make")
    except:
        raise error.TestError("Failed to compile %s" % t_name)

    test_clock = os.path.join(deps_dir, t_name)
    if not os.path.isfile(test_clock):
        raise error.TestError("Could not find %s" % t_name)

    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)
    vm.copy_files_to(test_clock, base_dir)
    session.cmd(os.path.join(base_dir, t_name))
    logging.info("PASS: Guest reported appropriate clock resolution")
    logging.info("guest's dmesg:")
    session.cmd_output("dmesg")
