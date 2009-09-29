import logging, os
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils, kvm_utils


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
    session = kvm_test_utils.wait_for_login(vm)

    # Modprobe the module if specified in config file
    if params.get("modprobe_module"):
        module = params.get("modprobe_module")
        if session.get_command_status("modprobe %s" % module):
            raise error.TestError("Modprobe module '%s' failed" % module)

    # Get output of command 'info pci' as reference
    s, info_pci_ref = vm.send_monitor_cmd("info pci")

    # Get output of command as reference
    reference = session.get_command_output(params.get("reference_cmd"))

    tested_model = params.get("pci_model")
    test_type = params.get("pci_type")

    if test_type == "nic":
        pci_add_cmd = "pci_add pci_addr=auto nic model=%s" % tested_model
    elif test_type == "block":
        image_name = params.get("image_name_stg")
        image_filename = "%s.%s" % (image_name, params.get("image_format_stg"))
        image_dir = os.path.join(test.bindir, "images")
        storage_name = os.path.join(image_dir, image_filename)
        pci_add_cmd = ("pci_add pci_addr=auto storage file=%s,if=%s" %
                                    (storage_name, tested_model))

    # Implement pci_add
    s, add_output = vm.send_monitor_cmd(pci_add_cmd)
    if not "OK domain" in add_output:
        raise error.TestFail("Add device failed. Hypervisor command is: %s. "
                             "Output: %s" % (pci_add_cmd, add_output))

    # Compare the output of 'info pci'
    s, after_add = vm.send_monitor_cmd("info pci")
    if after_add == info_pci_ref:
        raise error.TestFail("No new PCI device shown after executing "
                             "hypervisor command: 'info pci'")

    # Define a helper function to compare the output
    def new_shown():
        o = session.get_command_output(params.get("reference_cmd"))
        if reference == o:
            return False
        return True

    secs = int(params.get("wait_secs_for_hook_up"))
    if not kvm_utils.wait_for(new_shown, 30, secs, 3):
        raise error.TestFail("No new device shown in output of command "
                             "executed inside the guest: %s" %
                             params.get("reference_cmd"))

    # Define a helper function to catch PCI device string
    def find_pci():
        output = session.get_command_output(params.get("find_pci_cmd"))
        if not params.get("match_string") in output:
            return False
        return True

    if not kvm_utils.wait_for(find_pci, 30, 3, 3):
        raise error.TestFail("PCI model not found: %s. Command is: %s" %
                             (tested_model, params.get("find_pci_cmd")))

    # Test the newly added device
    s, o = session.get_command_status_output(params.get("pci_test_cmd"))
    if s:
        raise error.TestFail("Check for %s device failed after PCI hotplug. "
                             "Output: %s" % (test_type, o))

    # Delete the added pci device
    slot_id = "0" + add_output.split(",")[2].split()[1]
    cmd = "pci_del pci_addr=%s" % slot_id
    s, after_del = vm.send_monitor_cmd(cmd)
    if after_del == after_add:
        raise error.TestFail("Failed to hot remove PCI device: %s. "
                             "Hypervisor command: %s" % (tested_model, cmd))

    session.close()
