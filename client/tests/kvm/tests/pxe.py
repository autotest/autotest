import logging
from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import aexpect

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
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("pxe_timeout", 60))

    logging.info("Try to boot from PXE")
    output = aexpect.run_fg("tcpdump -nli %s" % vm.get_ifname(),
                                   logging.debug, "(pxe capture) ", timeout)[1]

    logging.info("Analyzing the tcpdump result...")
    if not "tftp" in output:
        raise error.TestFail("Couldn't find any TFTP packets after %s seconds" %
                             timeout)
    logging.info("Found TFTP packet")
