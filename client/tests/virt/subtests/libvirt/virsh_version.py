import logging
from autotest.client.shared import utils, error
from autotest.client.tests.virt import libvirt_vm

def run_virsh_version(test, params, env):
    """
    Test the command virsh version

    (1) Call virsh version
    (2) Call virsh version with an unexpected option
    (3) Call virsh version with libvirtd service stop
    """
    def virsh_version(option):
        cmd = "virsh version  %s" % option
        cmd_result = utils.run(cmd, ignore_status=True)
        logging.debug("Output: %s", cmd_result.stdout.strip())
        logging.debug("Error: %s", cmd_result.stderr.strip())
        logging.debug("Status: %d", cmd_result.exit_status)
        return cmd_result.exit_status

    # Prepare libvirtd service
    check_libvirtd = params.has_key("libvirtd")
    if check_libvirtd:
        libvirtd = params.get("libvirtd")
        if libvirtd == "off":
            libvirt_vm.libvirtd_stop()

    # Run test case
    option = params.get("options")
    status = virsh_version(option)

    # Recover libvirtd service start
    if libvirtd == "off":
        libvirt_vm.libvirtd_start()

    # Check status_error
    status_error = params.get("status_error")
    if status_error == "yes":
        if status == 0:
            raise error.TestFail("Command 'virsh version %s' succeeded "
                                 "(incorrect command)" % option)
    elif status_error == "no":
        if status != 0:
            raise error.TestFail("Command 'virsh version %s' failed "
                                 "(correct command)" % option)
