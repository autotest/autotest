import logging, commands, time, os, re
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
import kvm_test_utils


def run_enospc(test, params, env):
    """
    ENOSPC test

    1) Create a virtual disk on lvm
    2) Boot up guest with two disks
    3) Continually write data to second disk
    4) Check images and extend second disk when no space
    5) Continue paused guest
    6) Repeat step 3~5 several times

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    login_timeout = int(params.get("login_timeout", 360))
    session_serial = vm.wait_for_serial_login(timeout=login_timeout)

    drive_format = params.get("drive_format")
    if drive_format == "virtio":
        devname = "/dev/vdb"
    elif drive_format == "ide":
        output = session_serial.cmd_output("dir /dev")
        devname = "/dev/" + re.findall("([sh]db)\s", output)[0]
    elif drive_format == "scsi":
        devname = "/dev/sdb"
    cmd = params.get("background_cmd")
    cmd %= devname
    logging.info("Sending background cmd '%s'", cmd)
    session_serial.sendline(cmd)

    iterations = int(params.get("repeat_time", 40))
    i = 0
    pause_n = 0
    while i < iterations:
        status = vm.monitor.cmd("info status")
        logging.debug(status)
        if "paused" in status:
            pause_n += 1
            logging.info("Checking all images in use by the VM")
            script_path = os.path.join(test.bindir, "scripts/check_image.py")
            try:
                cmd_result = utils.run('python %s' % script_path)
            except error.CmdError, e:
                logging.debug(e.result_obj.stdout)
            logging.info("Guest paused, extending Logical Volume size")
            try:
                cmd_result = utils.run("lvextend -L +200M /dev/vgtest/lvtest")
            except error.CmdError, e:
                logging.debug(e.result_obj.stdout)
            vm.monitor.cmd("cont")
        time.sleep(10)
        i += 1

    if pause_n == 0:
        raise error.TestFail("Guest didn't pause during loop")
    else:
        logging.info("Guest paused %s times from %s iterations",
                     pause_n, iterations)

    logging.info("Final %s" % vm.monitor.cmd("info status"))
