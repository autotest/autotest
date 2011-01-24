import logging, time
from autotest_lib.client.common_lib import error


def run_linux_s3(test, params, env):
    """
    Suspend a guest Linux OS to memory.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

    logging.info("Checking that VM supports S3")
    session.cmd("grep -q mem /sys/power/state")

    logging.info("Waiting for a while for X to start")
    time.sleep(10)

    src_tty = session.cmd_output("fgconsole").strip()
    logging.info("Current virtual terminal is %s", src_tty)
    if src_tty not in map(str, range(1, 10)):
        raise error.TestFail("Got a strange current vt (%s)" % src_tty)

    dst_tty = "1"
    if src_tty == "1":
        dst_tty = "2"

    logging.info("Putting VM into S3")
    command = "chvt %s && echo mem > /sys/power/state && chvt %s" % (dst_tty,
                                                                     src_tty)
    suspend_timeout = 120 + int(params.get("smp")) * 60
    session.cmd(command, timeout=suspend_timeout)

    logging.info("VM resumed after S3")

    session.close()
