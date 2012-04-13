import logging, os, re, uuid
from autotest.client.shared import error


@error.context_aware
def run_usb(test, params, env):
    """
    Test usb device of guest

    1) Create a image file by qemu-img
    2) Boot up a guest add this image as a usb device
    3) Check usb device information via monitor
    4) Check usb information by executing guest command
    5) Check usb serial option (optional)
    6) Check usb removable option (optional)
    7) Check usb min_io_size/opt_io_size option (optional)

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    @error.context_aware
    def _verify_string(regex_str, string, expect_result, search_opt=0):
        """
        Verify USB storage device in monitor

        @params regex_str: regex for checking command output,
                                search option,
                                and expected string.
        """
        error.context("Finding matched sub-string with regex pattern %s" %
                      regex_str)
        m = re.findall(regex_str, string, search_opt)
        if not m:
            logging.debug(string)
            raise error.TestError("Could not find matched sub-string")

        error.context("Verify matched string is same as expected")
        fail_log = []
        if isinstance(m[0], tuple):
            for i in xrange(len(expect_result)):
                if m[0][i] != expect_result[i]:
                    fail_log.append("Expected: '%s', Actual: '%s'" %
                                    (expect_result[i], m[0][i]))
        else:
            if m[0] != expect_result[0]:
                fail_log.append("Expected: '%s', Actual: '%s'" %
                                (expect_result[0], m[0]))

        if fail_log:
            logging.debug(string)
            raise error.TestFail("Could not find expected string:\n %s" %
                                 ("\n".join(fail_log)))


    @error.context_aware
    def _do_io_test_guest(session):
        output = session.cmd("fdisk -l")
        if params.get("fdisk_string") not in output:
            for line in output.splitlines():
                logging.debug(line)
            raise error.TestFail("Could not detect the usb device on"
                                 "fdisk output")

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
        cmd = "md5sum /mnt/%s" % os.path.basename(c_file)
        md5_usb = session.cmd(cmd).strip()
        md5_root = md5_root.split()[0]
        md5_usb = md5_usb.split()[0]

        if md5_root != md5_usb:
            raise error.TestError("MD5 mismatch between file on root fs and on "
                                  "USB disk")

        error.context("Unmounting USB disk after file comparison")
        session.cmd("umount %s" % devname)

        error.context("Checking if there are I/O error messages in dmesg")
        output = session.get_command_output("dmesg -c")
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


    @error.context_aware
    def _restart_vm(options):
        if vm.is_alive():
            vm.destroy()

        new_params = params.copy()
        for option, value in options.iteritems():
            new_params[option] = value
        error.context("Restarting VM")
        vm.create(params=new_params)
        vm.verify_alive()


    def _login():
        return vm.wait_for_login(timeout=int(params.get("login_timeout", 360)))


    @error.context_aware
    def _check_serial_option(serial, regex_str, expect_str):
        error.context("Set serial option to '%s'" % serial, logging.info)
        _restart_vm({"drive_serial_stg": serial})

        error.context("Check serial option in monitor", logging.info)
        output = str(vm.monitor.info("qtree"))
        _verify_string(regex_str, output, [expect_str], re.S)

        error.context("Check serial option in guest", logging.info)
        session = _login()
        output = session.cmd("lsusb -v")
        if not ("EMPTY_STRING" in serial or "NO_EQUAL_STRING" in serial):
            # Verify in guest when serial is set to empty/null is meaningless.
            _verify_string(serial, output, [serial])
        _do_io_test_guest(session)

        session.close()


    @error.context_aware
    def _check_removable_option(removable, expect_str):
        error.context("Set removable option to '%s'" % removable, logging.info)
        _restart_vm({"removable_stg": removable})

        error.context("Check removable option in monitor", logging.info)
        output = str(vm.monitor.info("qtree"))
        regex_str = 'usb-storage.*?removable = (.*?)\n'
        _verify_string(regex_str, output, [removable], re.S)

        error.context("Check removable option in guest", logging.info)
        session = _login()
        output = session.cmd("ls -l /dev/disk/by-path/* | grep usb").strip()
        devname = re.findall("sd\w", output)
        cmd = "dmesg | grep %s" % devname[0] if devname else "sda"
        output = session.cmd(cmd)
        _verify_string(expect_str, output, [expect_str])
        _do_io_test_guest(session)

        session.close()


    @error.context_aware
    def _check_io_size_option(min_io_size="512", opt_io_size="0"):
        error.context("Set min_io_size to %s, opt_io_size to %s" %
                      (min_io_size, opt_io_size), logging.info)
        opt = {}
        opt["min_io_size_stg"] = min_io_size
        opt["opt_io_size_stg"] = opt_io_size

        _restart_vm(opt)

        error.context("Check min/opt io_size option in monitor", logging.info)
        output = str(vm.monitor.info("qtree"))
        regex_str = "usb-storage.*?min_io_size = (\d+).*?opt_io_size = (\d+)"
        _verify_string(regex_str, output, [min_io_size, opt_io_size], re.S)

        error.context("Check min/opt io_size option in guest", logging.info)
        session = _login()
        output = session.cmd("ls -l /dev/disk/by-path/* | grep usb").strip()
        devname = re.findall("sd\w", output)
        cmd = "cat /sys/block/%s/queue/{minimum,optimal}_io_size" % \
               (devname[0] if devname else "sda")
        output = session.cmd(cmd)
        # Note: If set min_io_size = 0, guest min_io_size would be set to
        # 512 by default.
        expected_min_size = min_io_size if min_io_size != "0" else "512"
        _verify_string("(\d+)\n(\d+)", output, [expected_min_size, opt_io_size])
        _do_io_test_guest(session)

        session.close()


    @error.context_aware
    def _check_freq_option(freq, regex_str, expect_str):
        error.context("Set freq option to '%s'" % freq, logging.info)
        _restart_vm({"freq_usb1": freq})

        error.context("Check freq option in monitor", logging.info)
        output = str(vm.monitor.info("qtree"))
        _verify_string(regex_str, output, [expect_str], re.S)

        error.context("Check freq option in guest", logging.info)
        session = _login()
        _do_io_test_guest(session)
        session.close()


    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()

    error.context("Check usb device information in monitor", logging.info)
    output = str(vm.monitor.info("usb"))
    if "Product QEMU USB MSD" not in output:
        logging.debug(output)
        raise error.TestFail("Could not find mass storage device")

    error.context("Check usb device information in guest", logging.info)
    session = _login()
    output = session.cmd("lsusb -v")
    # No bus specified, default using "usb.0" for "usb-storage"
    for i in ["ID 0000:0000", "Mass Storage", "SCSI", "QEMU USB HARDDRIVE"]:
        _verify_string(i, output, [i])
    _do_io_test_guest(session)
    session.close()

    if params.get("check_serial_option") == "yes":
        error.context("Check usb serial option", logging.info)
        serial = str(uuid.uuid4())
        regex_str = 'usb-storage.*?serial = "(.*?)"\n'
        _check_serial_option(serial, regex_str, serial)

        logging.info("Check this option with some illegal string")
        logging.info("Set usb serial to a empty string")
        # An empty string, ""
        serial = "EMPTY_STRING"
        regex_str = 'usb-storage.*?serial = (.*?)\n'
        _check_serial_option(serial, regex_str, '""')

        logging.info("Leave usb serial option blank")
        serial = "NO_EQUAL_STRING"
        regex_str = 'usb-storage.*?serial = (.*?)\n'
        _check_serial_option(serial, regex_str, '"on"')

    if params.get("check_removable_option") == "yes":
        error.context("Check usb removable option", logging.info)
        removable = "on"
        expect_str = "Attached SCSI removable disk"
        _check_removable_option(removable, expect_str)

        removable = "off"
        expect_str = "Attached SCSI disk"
        _check_removable_option(removable, expect_str)

    if params.get("check_io_size_option") == "yes":
        error.context("Check usb min/opt io_size option", logging.info)
        _check_io_size_option("0", "0")
        # Guest can't recognize correct value which we set now,
        # So comment these test temporary.
        #_check_io_size_option("1024", "1024")
        #_check_io_size_option("4096", "4096")

    if params.get("check_freq_option") == "yes":
        error.context("Check USB EHCI freq option", logging.info)
        freq = "1000"
        regex_str = 'usb-ehci.*?freq = (.*?)\n'
        _check_freq_option(freq, regex_str, freq)

        freq = "250"
        _check_freq_option(freq, regex_str, freq)

        freq = "2000"
        _check_freq_option(freq, regex_str, freq)
