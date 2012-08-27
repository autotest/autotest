import re, logging
from autotest.client.shared import utils, error
from autotest.client.virt import libvirt_vm, virsh

def run_virsh_freecell(test, params, env):
    """
    Test the command virsh freecell

    (1) Call virsh freecell
    (2) Call virsh freecell --all
    (3) Call virsh freecell with a numeric argument
    (4) Call virsh freecell xyz
    (5) Call virsh freecell with libvirtd service stop
    """

    connect_uri = libvirt_vm.normalize_connect_uri( params.get("connect_uri",
                                                               "default") )
    option = params.get("virsh_freecell_options")

    # Prepare libvirtd service
    check_libvirtd = params.has_key("libvirtd")
    if check_libvirtd:
        libvirtd = params.get("libvirtd")
        if libvirtd == "off":
            libvirt_vm.service_libvirtd_control("stop")

    # Run test case
    cmd_result = virsh.freecell(ignore_status=True, extra=option,
                                uri=connect_uri, debug=True)
    output = cmd_result.stdout.strip()
    status = cmd_result.exit_status

    # Recover libvirtd service start
    if libvirtd == "off":
        libvirt_vm.service_libvirtd_control("start")

    # Check the output
    if virsh.has_help_command('numatune'):
        OLD_LIBVIRT = False
    else:
        OLD_LIBVIRT = True
        if option == '--all':
            raise error.TestNAError("Older libvirt virsh freecell "
                                    "doesn't support --all option")

    def output_check(freecell_output):
        if not re.search("ki?B", freecell_output, re.IGNORECASE):
            raise error.TestFail("virsh freecell output invalid: " + freecell_output)

    # Check status_error
    status_error = params.get("status_error")
    if status_error == "yes":
        if status == 0:
            if libvirtd == "off":
                raise error.TestFail("Command 'virsh freecell' succeeded "
                                     "with libvirtd service stopped, incorrect")
            else:
                # newer libvirt
                if not OLD_LIBVIRT:
                    raise error.TestFail("Command 'virsh freecell %s' succeeded"
                                         "(incorrect command)" % option)
                else: # older libvirt
                    raise error.TestNAError('Older libvirt virsh freecell '
                                            'incorrectly processes extranious'
                                            'command-line options')
    elif status_error == "no":
        output_check(output)
        if status != 0:
            raise error.TestFail("Command 'virsh freecell %s' failed "
                                 "(correct command)" % option)
