import logging, commands, re
from  xml.dom.minidom import parse, parseString
from autotest_lib.client.common_lib import utils, error
from autotest_lib.client.virt import libvirt_vm

def run_virsh_capabilities(test, params, env):
    """
    Test the command virsh capabilities

    (1) Call virsh capabilities
    (2) Call virsh capabilities with an unexpected option
    (3) Call virsh capabilities with libvirtd service stop
    """
    def virsh_capabilities(option):
        cmd = "virsh capabilities  %s" % option
        cmd_result = utils.run(cmd, ignore_status=True)
        logging.info("Output: %s", cmd_result.stdout.strip())
        logging.error("Error: %s", cmd_result.stderr.strip())
        logging.info("Status: %d", cmd_result.exit_status)
        return cmd_result.exit_status, cmd_result.stdout.strip()

    def compare_capabilities_xml(source):
        dom = parseString(source)
        host = dom.getElementsByTagName('host')[0]
        # check that host has a non-empty UUID tag.
        uuid = host.getElementsByTagName('uuid')[0]
        host_uuid_output = uuid.firstChild.data
        logging.info("Host uuid (capabilities_xml):%s", host_uuid_output)
        if host_uuid_output == "":
            raise error.TestFail("The host uuid in capabilities_xml is none!")

        # check the host arch.
        arch = host.getElementsByTagName('arch')[0]
        host_arch_output = arch.firstChild.data
        logging.info("Host arch (capabilities_xml):%s", host_arch_output)
        cmd_result = utils.run("arch", ignore_status=True)
        if cmp(host_arch_output, cmd_result.stdout.strip()) != 0:
            raise error.TestFail("The host arch in capabilities_xml is wrong!")

        # check the host cpus num.
        cpus = dom.getElementsByTagName('cpus')[0]
        host_cpus_output = cpus.getAttribute('num')
        logging.info("Host cpus num (capabilities_xml):%s",
                      host_cpus_output)
        cmd = "less /proc/cpuinfo | grep processor | wc -l"
        cmd_result = utils.run(cmd, ignore_status=True)
        if cmp(host_cpus_output, cmd_result.stdout.strip()) != 0:
            raise error.TestFail("Host cpus num (capabilities_xml) is "
                                 "wrong")

        # check the arch of guest supported.
        cmd = "/usr/libexec/qemu-kvm  --cpu ? | grep qemu"
        cmd_result = utils.run(cmd, ignore_status=True)
        guest_wordsize_array = dom.getElementsByTagName('wordsize')
        length = len(guest_wordsize_array)
        for i in range(length):
            element = guest_wordsize_array[i]
            guest_wordsize = element.firstChild.data
            logging.info("Arch of guest supported (capabilities_xml):%s",
                         guest_wordsize)
            if not re.search(guest_wordsize, cmd_result.stdout.strip()):
                raise error.TestFail("The capabilities_xml gives an extra arch "
                                     "of guest to support!")

        # check the type of hyperviosr.
        guest_domain_type = dom.getElementsByTagName('domain')[0]
        guest_domain_type_output = guest_domain_type.getAttribute('type')
        logging.info("Hypervisor (capabilities_xml):%s",
                     guest_domain_type_output)
        cmd_result = utils.run("virsh uri", ignore_status=True)
        if not re.search(guest_domain_type_output, cmd_result.stdout.strip()):
            raise error.TestFail("The capabilities_xml gives an different "
                                 "hypervisor")

    # Prepare libvirtd service
    check_libvirtd = params.has_key("libvirtd")
    if check_libvirtd:
        libvirtd = params.get("libvirtd")
        if libvirtd == "off":
            libvirt_vm.service_libvirtd_control("stop")

    # Run test case
    option = params.get("virsh_cap_options")
    status, output = virsh_capabilities(option)

    # Recover libvirtd service start
    if libvirtd == "off":
        libvirt_vm.service_libvirtd_control("start")

    # Check status_error
    status_error = params.get("status_error")
    if status_error == "yes":
        if status == 0:
            if libvirtd == "off":
                raise error.TestFail("Command 'virsh capabilities' succeeded "
                                     "with libvirtd service stopped, incorrect")
            else:
                raise error.TestFail("Command 'virsh capabilities %s' succeeded "
                                     "(incorrect command)" % option)
    elif status_error == "no":
        compare_capabilities_xml(output)
        if status != 0:
            raise error.TestFail("Command 'virsh capabilities %s' failed "
                                 "(correct command)" % option)
