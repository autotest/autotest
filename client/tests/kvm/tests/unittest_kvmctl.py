import os
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


def run_unittest_kvmctl(test, params, env):
    """
    This is kvm userspace unit test, use kvm test harness kvmctl load binary
    test case file to test various functions of the kvm kernel module.
    The output of all unit tests can be found in the test result dir.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    case = params.get("case")
    srcdir = params.get("srcdir", test.srcdir)
    unit_dir = os.path.join(srcdir, "kvm_userspace", "kvm", "user")
    os.chdir(unit_dir)

    cmd = "./kvmctl test/x86/bootstrap test/x86/%s.flat" % case
    try:
        results = utils.system_output(cmd)
    except error.CmdError:
        raise error.TestFail("Unit test %s failed" % case)

    result_file = os.path.join(test.resultsdir, case)
    utils.open_write_close(result_file, results)
