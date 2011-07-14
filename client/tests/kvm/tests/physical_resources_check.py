import re, string, logging
from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import kvm_monitor, virt_vm


def run_physical_resources_check(test, params, env):
    """
    Check physical resources assigned to KVM virtual machines:
    1) Log into the guest
    2) Verify whether cpu counts ,memory size, nics' model,
       count and drives' format & count, drive_serial, UUID
       reported by the guest OS matches what has been assigned
       to the VM (qemu command line)
    3) Verify all MAC addresses for guest NICs

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    # Define a function for checking number of hard drivers & NICs
    def check_num(devices, info_cmd, check_str):
        f_fail = []
        expected_num = params.objects(devices).__len__()
        o = ""
        try:
            o = vm.monitor.info(info_cmd)
        except kvm_monitor.MonitorError, e:
            fail_log =  e + "\n"
            fail_log += "info/query monitor command failed (%s)" % info_cmd
            f_fail.append(fail_log)
            logging.error(fail_log)

        actual_num = string.count(o, check_str)
        if expected_num != actual_num:
            fail_log =  "%s number mismatch:\n" % str(devices)
            fail_log += "    Assigned to VM: %d\n" % expected_num
            fail_log += "    Reported by OS: %d" % actual_num
            f_fail.append(fail_log)
            logging.error(fail_log)
        return expected_num, f_fail

    # Define a function for checking hard drives & NICs' model
    def chk_fmt_model(device, fmt_model, info_cmd, regexp):
        f_fail = []
        devices = params.objects(device)
        for chk_device in devices:
            expected = params.object_params(chk_device).get(fmt_model)
            if not expected:
                expected = "rtl8139"
            o = ""
            try:
                o = vm.monitor.info(info_cmd)
            except kvm_monitor.MonitorError, e:
                fail_log = e + "\n"
                fail_log += "info/query monitor command failed (%s)" % info_cmd
                f_fail.append(fail_log)
                logging.error(fail_log)

            device_found = re.findall(regexp, o)
            logging.debug("Found devices: %s", device_found)
            found = False
            for fm in device_found:
                if expected in fm:
                    found = True

            if not found:
                fail_log =  "%s model mismatch:\n" % str(device)
                fail_log += "    Assigned to VM: %s\n" % expected
                fail_log += "    Reported by OS: %s" % device_found
                f_fail.append(fail_log)
                logging.error(fail_log)
        return f_fail

    # Define a function to verify UUID & Serial number
    def verify_device(expect, name, verify_cmd):
        f_fail = []
        if verify_cmd:
            actual = session.cmd_output(verify_cmd)
            if not string.upper(expect) in actual:
                fail_log =  "%s mismatch:\n" % name
                fail_log += "    Assigned to VM: %s\n" % string.upper(expect)
                fail_log += "    Reported by OS: %s" % actual
                f_fail.append(fail_log)
                logging.error(fail_log)
        return f_fail


    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

    logging.info("Starting physical resources check test")
    logging.info("Values assigned to VM are the values we expect "
                 "to see reported by the Operating System")
    # Define a failure counter, as we want to check all physical
    # resources to know which checks passed and which ones failed
    n_fail = []

    # We will check HDs with the image name
    image_name = virt_vm.get_image_filename(params, test.bindir)

    # Check cpu count
    logging.info("CPU count check")
    expected_cpu_nr = int(params.get("smp"))
    actual_cpu_nr = vm.get_cpu_count()
    if expected_cpu_nr != actual_cpu_nr:
        fail_log =  "CPU count mismatch:\n"
        fail_log += "    Assigned to VM: %s \n" % expected_cpu_nr
        fail_log += "    Reported by OS: %s" % actual_cpu_nr
        n_fail.append(fail_log)
        logging.error(fail_log)

    # Check memory size
    logging.info("Memory size check")
    expected_mem = int(params.get("mem"))
    actual_mem = vm.get_memory_size()
    if actual_mem != expected_mem:
        fail_log =  "Memory size mismatch:\n"
        fail_log += "    Assigned to VM: %s\n" % expected_mem
        fail_log += "    Reported by OS: %s\n" % actual_mem
        n_fail.append(fail_log)
        logging.error(fail_log)


    logging.info("Hard drive count check")
    _, f_fail = check_num("images", "block", image_name)
    n_fail.extend(f_fail)

    logging.info("NIC count check")
    _, f_fail = check_num("nics", "network", "model=")
    n_fail.extend(f_fail)

    logging.info("NICs model check")
    f_fail = chk_fmt_model("nics", "nic_model", "network", "model=(.*),")
    n_fail.extend(f_fail)

    logging.info("Drive format check")
    f_fail = chk_fmt_model("images", "drive_format",
                           "block", "(.*)\: .*%s" % image_name)
    n_fail.extend(f_fail)

    logging.info("Network card MAC check")
    o = ""
    try:
        o = vm.monitor.info("network")
    except kvm_monitor.MonitorError, e:
        fail_log =  e + "\n"
        fail_log += "info/query monitor command failed (network)"
        n_fail.append(fail_log)
        logging.error(fail_log)
    found_mac_addresses = re.findall("macaddr=(\S+)", o)
    logging.debug("Found MAC adresses: %s", found_mac_addresses)

    num_nics = len(params.objects("nics"))
    for nic_index in range(num_nics):
        mac = vm.get_mac_address(nic_index)
        if not string.lower(mac) in found_mac_addresses:
            fail_log =  "MAC address mismatch:\n"
            fail_log += "    Assigned to VM (not found): %s" % mac
            n_fail.append(fail_log)
            logging.error(fail_log)

    logging.info("UUID check")
    if vm.get_uuid():
        f_fail = verify_device(vm.get_uuid(), "UUID",
                               params.get("catch_uuid_cmd"))
        n_fail.extend(f_fail)

    logging.info("Hard Disk serial number check")
    catch_serial_cmd = params.get("catch_serial_cmd")
    f_fail = verify_device(params.get("drive_serial"), "Serial",
                           catch_serial_cmd)
    n_fail.extend(f_fail)

    if n_fail:
        session.close()
        raise error.TestFail("Physical resources check test "
                             "reported %s failures:\n%s" %
                             (len(n_fail), "\n".join(n_fail)))

    session.close()
