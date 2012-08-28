import logging
from autotest.client.shared import utils, error
from virttest import libvirt_vm, virsh


def run_virsh_hostname(test, params, env):
    """
    Test the command virsh hostname

    (1) Call virsh hostname
    (2) Call virsh hostname with an unexpected option
    (3) Call virsh hostname with libvirtd service stop
    """

    hostname_result = utils.run("hostname", ignore_status=True)
    hostname = hostname_result.stdout.strip()

    # Prepare libvirtd service
    check_libvirtd = params.has_key("libvirtd")
    if check_libvirtd:
        libvirtd = params.get("libvirtd")
        if libvirtd == "off":
            libvirt_vm.libvirtd_stop()

    # Run test case
    option = params.get("virsh_hostname_options")
    try:
        hostname_test = virsh.hostname(option,
                                       ignore_status=False,
                                       debug=True)
        status = 0 # good
    except error.CmdError:
        status = 1 # bad
        hostname_test = None

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
            raise error.TestFail("Virsh cmd gives hostname %s != %s." % (hostname_test, hostname))
        if status != 0:
            raise error.TestFail("Command 'virsh hostname %s' failed "
                                 "(correct command)" % option)
