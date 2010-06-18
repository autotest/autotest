import logging, os
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils, kvm_utils, kvm_vm


def run_pci_hotplug(test, params, env):
    """
    Test pci devices' hotplug
    1) PCI add a deivce (NIC / block)
    2) Compare output of hypervisor command `info pci`
    3) Compare output of guest command `reference_cmd`
    4) Verify whether pci_model is shown in `pci_find_cmd`
    5) Check whether the newly added pci device works fine
    6) PCI delete the device, verify whether could remove the pci device

    @param test:   kvm test object
    @param params: Dictionary with the test parameters
    @param env:    Dictionary with test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    timeout = int(params.get("login_timeout", 360))
    session = kvm_test_utils.wait_for_login(vm, timeout=timeout)

    # Modprobe the module if specified in config file
    module = params.get("modprobe_module")
    if module:
        if session.get_command_status("modprobe %s" % module):
            raise error.TestError("Modprobe module '%s' failed" % module)

    # Get output of command 'info pci' as reference
    info_pci_ref = vm.monitor.info("pci")

    # Get output of command as reference
    reference = session.get_command_output(params.get("reference_cmd"))

    tested_model = params.get("pci_model")
    test_type = params.get("pci_type")

    if test_type == "nic":
        pci_add_cmd = "pci_add pci_addr=auto nic model=%s" % tested_model
    elif test_type == "block":
        image_params = kvm_utils.get_sub_dict(params, "stg")
        image_filename = kvm_vm.get_image_filename(image_params, test.bindir)
        pci_add_cmd = ("pci_add pci_addr=auto storage file=%s,if=%s" %
                       (image_filename, tested_model))

    # Execute pci_add (should be replaced by a proper monitor method call)
    add_output = vm.monitor.cmd(pci_add_cmd)
    if not "OK domain" in add_output:
        raise error.TestFail("Add device failed. Hypervisor command is: %s. "
                             "Output: %r" % (pci_add_cmd, add_output))
    after_add = vm.monitor.info("pci")

    # Define a helper function to delete the device
    def pci_del(ignore_failure=False):
        slot_id = "0" + add_output.split(",")[2].split()[1]
        cmd = "pci_del pci_addr=%s" % slot_id
        # This should be replaced by a proper monitor method call
        vm.monitor.cmd(cmd)

        def device_removed():
            after_del = vm.monitor.info("pci")
            return after_del != after_add

        if (not kvm_utils.wait_for(device_removed, 10, 0, 1)
            and not ignore_failure):
            raise error.TestFail("Failed to hot remove PCI device: %s. "
                                 "Hypervisor command: %s" % (tested_model,
                                                             cmd))

    try:
        # Compare the output of 'info pci'
        if after_add == info_pci_ref:
            raise error.TestFail("No new PCI device shown after executing "
                                 "hypervisor command: 'info pci'")

        # Define a helper function to compare the output
        def new_shown():
            o = session.get_command_output(params.get("reference_cmd"))
            return o != reference

        secs = int(params.get("wait_secs_for_hook_up"))
        if not kvm_utils.wait_for(new_shown, 30, secs, 3):
            raise error.TestFail("No new device shown in output of command "
                                 "executed inside the guest: %s" %
                                 params.get("reference_cmd"))

        # Define a helper function to catch PCI device string
        def find_pci():
            o = session.get_command_output(params.get("find_pci_cmd"))
            return params.get("match_string") in o

        if not kvm_utils.wait_for(find_pci, 30, 3, 3):
            raise error.TestFail("PCI %s %s device not found in guest. "
                                 "Command was: %s" %
                                 (tested_model, test_type,
                                  params.get("find_pci_cmd")))

        # Test the newly added device
        s, o = session.get_command_status_output(params.get("pci_test_cmd"))
        if s != 0:
            raise error.TestFail("Check for %s device failed after PCI "
                                 "hotplug. Output: %r" % (test_type, o))

        session.close()

    except:
        pci_del(ignore_failure=True)
        raise

    else:
        pci_del()
