import re, logging
from autotest.client.shared import utils, error
from autotest.client.virt import libvirt_vm
from autotest.client import *

def run_virsh_freecell(test, params, env):
    """
    Test the command virsh freecell

    (1) Call virsh freecell
    (2) Call virsh freecell --all
    (3) Call virsh freecell with a numeric argument
    (4) Call virsh freecell xyz
    (5) Call virsh freecell with libvirtd service stop
    """

    # Prepare libvirtd service
    check_libvirtd = params.has_key("libvirtd")
    if check_libvirtd:
        libvirtd = params.get("libvirtd")
        if libvirtd == "off":
            libvirt_vm.service_libvirtd_control("stop")

    # Run test case
    option = params.get("virsh_freecell_options")
    cmd_result = libvirt_vm.virsh_freecell(ignore_status=True, extra=option)
    logging.info("Output:\n%s", cmd_result.stdout.strip())
    logging.info("Status: %d", cmd_result.exit_status)
    logging.error("Error: %s", cmd_result.stderr.strip())
    output = cmd_result.stdout.strip()
    status = cmd_result.exit_status

    # Recover libvirtd service start
    if libvirtd == "off":
        libvirt_vm.service_libvirtd_control("start")

    # Check the output
    def output_check(freecell_output):
        if not re.search("kB", freecell_output):
            raise error.TestFail("virsh freecell output invalid!")

    # Check status_error
    status_error = params.get("status_error")
    if status_error == "yes":
        if status == 0:
            if libvirtd == "off":
                raise error.TestFail("Command 'virsh freecell' succeeded "
                                     "with libvirtd service stopped, incorrect")
            else:
                raise error.TestFail("Command 'virsh freecell %s' succeeded"
                                     "(incorrect command)" % option)
    elif status_error == "no":
        output_check(output)
        if status != 0:
            raise error.TestFail("Command 'virsh freecell %s' failed "
                                 "(correct command)" % option)
