import logging
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils


def run_pxe(test, params, env):
    """
    PXE test:

    1) Snoop the tftp packet in the tap device.
    2) Wait for some seconds.
    3) Check whether we could capture TFTP packets.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    timeout = int(params.get("pxe_timeout", 60))

    logging.info("Try to boot from PXE")
    status, output = kvm_subprocess.run_fg("tcpdump -nli %s" % vm.get_ifname(),
                                           logging.debug,
                                           "(pxe capture) ",
                                           timeout)

    logging.info("Analyzing the tcpdump result...")
    if not "tftp" in output:
        raise error.TestFail("Couldn't find any TFTP packets after %s seconds" %
                             timeout)
    logging.info("Found TFTP packet")
