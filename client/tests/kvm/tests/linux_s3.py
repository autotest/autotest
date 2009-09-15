import logging, time
from autotest_lib.client.common_lib import error
import kvm_test_utils


def run_linux_s3(test, params, env):
    """
    Suspend a guest Linux OS to memory.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm)

    logging.info("Checking that VM supports S3")
    status = session.get_command_status("grep -q mem /sys/power/state")
    if status == None:
        logging.error("Failed to check if S3 exists")
    elif status != 0:
        raise error.TestFail("Guest does not support S3")

    logging.info("Waiting for a while for X to start")
    time.sleep(10)

    src_tty = session.get_command_output("fgconsole").strip()
    logging.info("Current virtual terminal is %s" % src_tty)
    if src_tty not in map(str, range(1,10)):
        raise error.TestFail("Got a strange current vt (%s)" % src_tty)

    dst_tty = "1"
    if src_tty == "1":
        dst_tty = "2"

    logging.info("Putting VM into S3")
    command = "chvt %s && echo mem > /sys/power/state && chvt %s" % (dst_tty,
                                                                     src_tty)
    status = session.get_command_status(command, timeout=120)
    if status != 0:
        raise error.TestFail("Suspend to mem failed")

    logging.info("VM resumed after S3")

    session.close()
