import logging
from autotest.client.shared import utils, error
from autotest.client.virt import libvirt_vm, virsh

def run_virsh_uri(test, params, env):
    """
    Test the command virsh uri

    (1) Call virsh uri
    (2) Call virsh -c remote_uri uri
    (3) Call virsh uri with an unexpected option
    (4) Call virsh uri with libvirtd service stop
    """

    connect_uri = libvirt_vm.normalize_connect_uri( params.get("connect_uri",
                                                               "default") )

    option = params.get("options")
    target_uri = params.get("target_uri")
    if target_uri:
        if target_uri.count('EXAMPLE.COM'):
            raise error.TestError('target_uri configuration set to sample value')
        logging.info("The target_uri: %s", target_uri)
        cmd = "virsh -c %s uri" % target_uri
    else:
        cmd = "virsh uri %s" % option

    # Prepare libvirtd service
    check_libvirtd = params.has_key("libvirtd")
    if check_libvirtd:
        libvirtd = params.get("libvirtd")
        if libvirtd == "off":
            libvirt_vm.service_libvirtd_control("stop")

    # Run test case
    logging.info("The command: %s", cmd)
    try:
        uri_test = virsh.canonical_uri(option, uri=connect_uri,
                             ignore_status=False,
                             debug=True)
        status = 0 # good
    except error.CmdError:
        status = 1 # bad
        uri_test = ''

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
            raise error.TestFail("Virsh cmd uri %s != %s." % (uri_test,target_uri))
        if status != 0:
            raise error.TestFail("Command: %s  failed "
                                 "(correct command)" % cmd)
