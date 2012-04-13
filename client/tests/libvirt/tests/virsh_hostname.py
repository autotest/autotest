import logging
from autotest.client.common_lib import utils, error
from autotest.client.virt import libvirt_vm

def run_virsh_hostname(test, params, env):
    """
    Test the command virsh hostname

    (1) Call virsh hostname
    (2) Call virsh hostname with an unexpected option
    (3) Call virsh hostname with libvirtd service stop
    """
    def virsh_hostname(option):
        cmd = "virsh hostname  %s" % option
        cmd_result = utils.run(cmd, ignore_status=True)
        logging.debug("Output: %s", cmd_result.stdout.strip())
        logging.debug("Error: %s", cmd_result.stderr.strip())
        logging.debug("Status: %d", cmd_result.exit_status)
        return cmd_result.exit_status, cmd_result.stdout.strip()

    hostname_result = utils.run("hostname", ignore_status=True)
    hostname = hostname_result.stdout.strip()

    # Prepare libvirtd service
    check_libvirtd = params.has_key("libvirtd")
    if check_libvirtd:
        libvirtd = params.get("libvirtd")
        if libvirtd == "off":
            libvirt_vm.libvirtd_stop()

    # Run test case
    option = params.get("options")
    status, hostname_test = virsh_hostname(option)

    # Recover libvirtd service start
    if libvirtd == "off":
        libvirt_vm.libvirtd_start()

    # Check status_error
    status_error = params.get("status_error")
    if status_error == "yes":
        if status == 0:
            raise error.TestFail("Command 'virsh hostname %s' succeeded "
                                 "(incorrect command)" % option)
    elif status_error == "no":
        if cmp(hostname, hostname_test) != 0:
            raise error.TestFail("Virsh cmd gives wrong hostname.")
        if status != 0:
            raise error.TestFail("Command 'virsh hostname %s' failed "
                                 "(correct command)" % option)
