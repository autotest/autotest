import logging
from autotest.client.common_lib import utils, error
from autotest.client.virt import libvirt_vm

def run_virsh_uri(test, params, env):
    """
    Test the command virsh uri

    (1) Call virsh uri
    (2) Call virsh -c remote_uri uri
    (3) Call virsh uri with an unexpected option
    (4) Call virsh uri with libvirtd service stop
    """

    def virsh_uri(cmd):
        cmd_result = utils.run(cmd, ignore_status=True)
        logging.info("Output: %s", cmd_result.stdout.strip())
        logging.error("Error: %s", cmd_result.stderr.strip())
        logging.info("Status: %d", cmd_result.exit_status)
        return cmd_result.exit_status, cmd_result.stdout.strip()

    # Prepare libvirtd service
    check_libvirtd = params.has_key("libvirtd")
    if check_libvirtd:
        libvirtd = params.get("libvirtd")
        if libvirtd == "off":
            libvirt_vm.service_libvirtd_control("stop")

    # Run test case
    option = params.get("options")
    check_target_uri = params.has_key("target_uri")
    if check_target_uri:
        target_uri = params.get("target_uri")
        logging.info("The target_uri: %s", target_uri)
        cmd = "virsh -c %s uri" % target_uri
    else:
        cmd = "virsh uri %s" % option

    logging.info("The command: %s", cmd)
    status, uri_test = virsh_uri(cmd)

    # Recover libvirtd service start
    if libvirtd == "off":
        libvirt_vm.service_libvirtd_control("start")

    # Check status_error
    status_error = params.get("status_error")
    if status_error == "yes":
        if status == 0:
            raise error.TestFail("Command: %s  succeeded "
                                 "(incorrect command)" % cmd)
        else:
            logging.info("command: %s is a expected error", cmd)
    elif status_error == "no":
        if cmp(target_uri, uri_test) != 0:
            raise error.TestFail("Virsh cmd gives wrong uri.")
        if status != 0:
            raise error.TestFail("Command: %s  failed "
                                 "(correct command)" % cmd)
