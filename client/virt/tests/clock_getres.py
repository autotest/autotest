import logging, os
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils


def run_clock_getres(test, params, env):
    """
    Verify if guests using kvm-clock as the time source have a sane clock
    resolution.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    source_name = "test_clock_getres/test_clock_getres.c"
    source_name = os.path.join(test.bindir, "deps", source_name)
    dest_name = "/tmp/test_clock_getres.c"
    bin_name = "/tmp/test_clock_getres"

    if not os.path.isfile(source_name):
        raise error.TestError("Could not find %s" % source_name)

    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

    vm.copy_files_to(source_name, dest_name)
    session.cmd("gcc -lrt -o %s %s" % (bin_name, dest_name))
    session.cmd(bin_name)
    logging.info("PASS: Guest reported appropriate clock resolution")
    logging.info("Guest's dmesg:\n%s", session.cmd_output("dmesg").strip())
