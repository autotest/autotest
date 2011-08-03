import logging, os
from autotest_lib.client.common_lib import error


@error.context_aware
def run_usb(test, params, env):
    """
    Test usb device of guest

    1) create a image file by qemu-img
    2) boot up a guest add this file as a usb device
    3) check usb device information by execute monitor/guest command

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.create()

    session = vm.wait_for_login(timeout=int(params.get("login_timeout", 360)))

    output = vm.monitor.cmd("info usb")
    if "Product QEMU USB MSD" not in output:
        logging.debug(output)
        raise error.TestFail("Could not find mass storage device")

    output = session.cmd("lsusb -v")
    # No bus specified, default using "usb.0" for "usb-storage"
    for i in ["ID 0000:0000", "Mass Storage", "SCSI", "QEMU USB HARDDRIVE"]:
        if i not in output:
            logging.debug(output)
            raise error.TestFail("No '%s' in the output of 'lsusb -v'" % i)

    output = session.cmd("fdisk -l")
    if params.get("fdisk_string") not in output:
        for line in output.splitlines():
            logging.debug(line)
        raise error.TestFail("Could not detect the usb device on fdisk output")

    error.context("Formatting USB disk")
    devname = session.cmd("ls /dev/disk/by-path/* | grep usb").strip()
    session.cmd("yes | mkfs %s" % devname,
                timeout=int(params.get("format_timeout")))

    error.context("Mounting USB disk")
    session.cmd("mount %s /mnt" % devname)

    error.context("Creating comparison file")
    c_file = '/tmp/usbfile'
    session.cmd("dd if=/dev/random of=%s bs=1M count=1" % c_file)

    error.context("Copying %s to USB disk" % c_file)
    session.cmd("cp %s /mnt" % c_file)

    error.context("Unmounting USB disk before file comparison")
    session.cmd("umount %s" % devname)

    error.context("Mounting USB disk for file comparison")
    session.cmd("mount %s /mnt" % devname)

    error.context("Determining md5sum for file on root fs and in USB disk")
    md5_root = session.cmd("md5sum %s" % c_file).strip()
    md5_usb = session.cmd("md5sum /mnt/%s" % os.path.basename(c_file)).strip()
    md5_root = md5_root.split()[0]
    md5_usb = md5_usb.split()[0]

    error.context("")
    if md5_root != md5_usb:
        raise error.TestError("MD5 mismatch between file on root fs and on "
                              "USB disk")

    error.context("Unmounting USB disk after file comparison")
    session.cmd("umount %s" % devname)

    error.context("Checking if there are I/O error messages in dmesg")
    output = session.get_command_output("dmesg")
    io_error_msg = []
    for line in output.splitlines():
        if "Buffer I/O error" in line:
            io_error_msg.append(line)

    if io_error_msg:
        e_msg = "IO error found on guest's dmesg when formatting USB device"
        logging.error(e_msg)
        for line in io_error_msg:
            logging.error(line)
        raise error.TestFail(e_msg)

    session.close()
