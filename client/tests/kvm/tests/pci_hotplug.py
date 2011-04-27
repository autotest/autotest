import re
from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import virt_utils, virt_vm, aexpect


def run_pci_hotplug(test, params, env):
    """
    Test hotplug of PCI devices.

    (Elements between [] are configurable test parameters)
    1) PCI add a deivce (NIC / block)
    2) Compare output of monitor command 'info pci'.
    3) Compare output of guest command [reference_cmd].
    4) Verify whether pci_model is shown in [pci_find_cmd].
    5) Check whether the newly added PCI device works fine.
    6) PCI delete the device, verify whether could remove the PCI device.

    @param test:   KVM test object.
    @param params: Dictionary with the test parameters.
    @param env:    Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

    # Modprobe the module if specified in config file
    module = params.get("modprobe_module")
    if module:
        session.cmd("modprobe %s" % module)

    # Get output of command 'info pci' as reference
    info_pci_ref = vm.monitor.info("pci")

    # Get output of command as reference
    reference = session.cmd_output(params.get("reference_cmd"))

    tested_model = params.get("pci_model")
    test_type = params.get("pci_type")
    image_format = params.get("image_format_stg")

    # Probe qemu to verify what is the supported syntax for PCI hotplug
    cmd_output = vm.monitor.cmd("?")
    if len(re.findall("\ndevice_add", cmd_output)) > 0:
        cmd_type = "device_add"
    elif len(re.findall("\npci_add", cmd_output)) > 0:
        cmd_type = "pci_add"
    else:
        raise error.TestError("Unknow version of qemu")

    # Determine syntax of drive hotplug
    # __com.redhat_drive_add == qemu-kvm-0.12 on RHEL 6
    if len(re.findall("\n__com.redhat_drive_add", cmd_output)) > 0:
        drive_cmd_type = "__com.redhat_drive_add"
    # drive_add == qemu-kvm-0.13 onwards
    elif len(re.findall("\ndrive_add", cmd_output)) > 0:
        drive_cmd_type = "drive_add"
    else:
        raise error.TestError("Unknow version of qemu")

    # Probe qemu for a list of supported devices
    devices_support = vm.monitor.cmd("%s ?" % cmd_type)

    if cmd_type == "pci_add":
        if test_type == "nic":
            pci_add_cmd = "pci_add pci_addr=auto nic model=%s" % tested_model
        elif test_type == "block":
            image_params = params.object_params("stg")
            image_filename = virt_vm.get_image_filename(image_params,
                                                       test.bindir)
            pci_add_cmd = ("pci_add pci_addr=auto storage file=%s,if=%s" %
                           (image_filename, tested_model))
        # Execute pci_add (should be replaced by a proper monitor method call)
        add_output = vm.monitor.cmd(pci_add_cmd)
        if not "OK domain" in add_output:
            raise error.TestFail("Add PCI device failed. "
                                 "Monitor command is: %s, Output: %r" %
                                 (pci_add_cmd, add_output))
        after_add = vm.monitor.info("pci")

    elif cmd_type == "device_add":
        driver_id = test_type + "-" + virt_utils.generate_random_id()
        device_id = test_type + "-" + virt_utils.generate_random_id()
        if test_type == "nic":
            if tested_model == "virtio":
                tested_model = "virtio-net-pci"
            pci_add_cmd = "device_add id=%s,driver=%s" % (device_id,
                                                          tested_model)

        elif test_type == "block":
            image_params = params.object_params("stg")
            image_filename = virt_vm.get_image_filename(image_params,
                                                       test.bindir)
            controller_model = None
            if tested_model == "virtio":
                tested_model = "virtio-blk-pci"

            if tested_model == "scsi":
                tested_model = "scsi-disk"
                controller_model = "lsi53c895a"
                if len(re.findall(controller_model, devices_support)) == 0:
                    raise error.TestError("scsi controller device (%s) not "
                                          "supported by qemu" %
                                          controller_model)

            if controller_model is not None:
                controller_id = "controller-" + device_id
                controller_add_cmd = ("device_add %s,id=%s" %
                                      (controller_model, controller_id))
                vm.monitor.cmd(controller_add_cmd)

            if drive_cmd_type == "drive_add":
                driver_add_cmd = ("drive_add auto "
                                  "file=%s,if=none,id=%s,format=%s" %
                                  (image_filename, driver_id, image_format))
            elif drive_cmd_type == "__com.redhat_drive_add":
                driver_add_cmd = ("__com.redhat_drive_add "
                                  "file=%s,format=%s,id=%s" %
                                  (image_filename, image_format, driver_id))

            pci_add_cmd = ("device_add id=%s,driver=%s,drive=%s" %
                           (device_id, tested_model, driver_id))
            vm.monitor.cmd(driver_add_cmd)

        # Check if the device is support in qemu
        if len(re.findall(tested_model, devices_support)) > 0:
            add_output = vm.monitor.cmd(pci_add_cmd)
        else:
            raise error.TestError("%s doesn't support device: %s" %
                                  (cmd_type, tested_model))
        after_add = vm.monitor.info("pci")

        if not device_id in after_add:
            raise error.TestFail("Add device failed. Monitor command is: %s"
                                 ". Output: %r" % (pci_add_cmd, add_output))

    # Define a helper function to delete the device
    def pci_del(ignore_failure=False):
        if cmd_type == "pci_add":
            result_domain, bus, slot, function = add_output.split(',')
            domain = int(result_domain.split()[2])
            bus = int(bus.split()[1])
            slot = int(slot.split()[1])
            pci_addr = "%x:%x:%x" % (domain, bus, slot)
            cmd = "pci_del pci_addr=%s" % pci_addr
        elif cmd_type == "device_add":
            cmd = "device_del %s" % device_id
        # This should be replaced by a proper monitor method call
        vm.monitor.cmd(cmd)

        def device_removed():
            after_del = vm.monitor.info("pci")
            return after_del != after_add

        if (not virt_utils.wait_for(device_removed, 10, 0, 1)
            and not ignore_failure):
            raise error.TestFail("Failed to hot remove PCI device: %s. "
                                 "Monitor command: %s" %
                                 (tested_model, cmd))

    try:
        # Compare the output of 'info pci'
        if after_add == info_pci_ref:
            raise error.TestFail("No new PCI device shown after executing "
                                 "monitor command: 'info pci'")

        # Define a helper function to compare the output
        def new_shown():
            o = session.cmd_output(params.get("reference_cmd"))
            return o != reference

        secs = int(params.get("wait_secs_for_hook_up"))
        if not virt_utils.wait_for(new_shown, 30, secs, 3):
            raise error.TestFail("No new device shown in output of command "
                                 "executed inside the guest: %s" %
                                 params.get("reference_cmd"))

        # Define a helper function to catch PCI device string
        def find_pci():
            o = session.cmd_output(params.get("find_pci_cmd"))
            return params.get("match_string") in o

        if not virt_utils.wait_for(find_pci, 30, 3, 3):
            raise error.TestFail("PCI %s %s device not found in guest. "
                                 "Command was: %s" %
                                 (tested_model, test_type,
                                  params.get("find_pci_cmd")))

        # Test the newly added device
        try:
            session.cmd(params.get("pci_test_cmd"))
        except aexpect.ShellError, e:
            raise error.TestFail("Check for %s device failed after PCI "
                                 "hotplug. Output: %r" % (test_type, e.output))

        session.close()

    except:
        pci_del(ignore_failure=True)
        raise

    else:
        pci_del()
