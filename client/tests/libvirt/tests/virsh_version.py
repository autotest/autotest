import logging
from autotest.client.shared import utils, error
from autotest.client.virt import libvirt_vm, virsh

def run_virsh_version(test, params, env):
    """
    Test the command virsh version

    (1) Call virsh version
    (2) Call virsh version with an unexpected option
    (3) Call virsh version with libvirtd service stop
    """

    connect_uri = libvirt_vm.normalize_connect_uri( params.get("connect_uri",
                                                               "default") )

    # Prepare libvirtd service
    check_libvirtd = params.has_key("libvirtd")
    if check_libvirtd:
        libvirtd = params.get("libvirtd")
        if libvirtd == "off":
            libvirt_vm.libvirtd_stop()

    # Run test case
    option = params.get("virsh_version_options")
    try:
        output = virsh.version(option, uri=connect_uri,
                               ignore_status=False, debug=True)
        status = 0 #good
    except error.CmdError:
        status = 1 #bad

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
