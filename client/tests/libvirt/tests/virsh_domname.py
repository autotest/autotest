import logging, time
from autotest.client.shared import utils, error
from autotest.client.virt import libvirt_vm


def run_virsh_domname(test, params, env):
    """
    Test command: virsh domname <id/uuid>.

    1) Prepare libvirtd status and test environment.
    2) Try to get domname through valid and invalid command.
    3) Recover libvirtd service and test environment.
    4) Check result.
    """
    vm_name = params.get("main_vm", "vm1")
    vm = env.get_vm(params["main_vm"])

    domid = vm.get_id().strip()
    domuuid = vm.get_uuid().strip()

    #Prepare libvirtd status
    libvirtd = params.get("libvirtd", "on")
    if libvirtd == "off":
        libvirt_vm.service_libvirtd_control("stop")

    #run test case
    options_ref = params.get("options_ref", "id")
    addition_status_error = params.get("addition_status_error", "no")
    status_error = params.get("status_error", "no")
    options = params.get("options", "%s")
    options_suffix = params.get("options_suffix", "")
    if options_ref == "id":
        options_ref = domid
        if options_ref == "-":
            options = "%s"
        else:
            options_ref = int(domid)
    elif options_ref == "uuid":
        options_ref = domuuid
        # UUID can get domain name in any state.
        logging.warning("Reset addition_status_error to NO for uuid test!")
        addition_status_error = "no"
    elif options_ref == "name":
        options_ref = vm_name

    if options:
        options = (options % options_ref)
    if options_suffix:
        options = options + " " + options_suffix
    result = libvirt_vm.virsh_domname(options, ignore_status=True, print_info=True)

    #Recover libvirtd service to start
    if libvirtd == "off":
        libvirt_vm.service_libvirtd_control("start")
        addition_status_error = "yes"

    #check status_error
    status_error = (status_error == "no") and (addition_status_error == "no")
    if status_error:
        if result.exit_status != 0 or result.stdout.strip() != vm_name:
            raise error.TestFail("Run failed because unexpected result.")
    else:
        if result.exit_status == 0 and result.stdout.strip() != vm_name:
            raise error.TestFail("Run passed but result is unexpected.")
