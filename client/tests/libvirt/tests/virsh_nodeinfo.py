import re, logging
from autotest.client.shared import utils, error
from autotest.client.virt import libvirt_vm
from autotest.client import *

def run_virsh_nodeinfo(test, params, env):
    """
    Test the command virsh nodeinfo

    (1) Call virsh nodeinfo
    (2) Call virsh nodeinfo with an unexpected option
    (3) Call virsh nodeinfo with libvirtd service stop
    """
    def _check_nodeinfo(nodeinfo_output,verify_str, column):
        cmd = "echo \"%s\" | grep \"%s\" | awk '{print $%s}'" % (nodeinfo_output, verify_str, column)
        cmd_result = utils.run(cmd, ignore_status=True)
        stdout = cmd_result.stdout.strip()
        logging.debug("Info %s on nodeinfo output:%s" %  (verify_str, stdout))
        return stdout


    def output_check(nodeinfo_output):
        # Check CPU model
        cpu_model_nodeinfo = _check_nodeinfo(nodeinfo_output, "CPU model", 3)
        cpu_model_os = utils.get_current_kernel_arch()
        if not re.match(cpu_model_nodeinfo, cpu_model_os):
            raise error.TestFail("Virsh nodeinfo output didn't match CPU model")

        # Check number of CPUs
        cpus_nodeinfo = _check_nodeinfo(nodeinfo_output, "CPU(s)", 2)
        cpus_os = utils.count_cpus()
        if  int(cpus_nodeinfo) != cpus_os:
            raise error.TestFail("Virsh nodeinfo output didn't match number of "
                                 "CPU(s)")

        # Check CPU frequency
        cpu_frequency_nodeinfo = _check_nodeinfo(nodeinfo_output, 'CPU frequency', 3)
        cmd = ("cat /proc/cpuinfo | grep 'cpu MHz' | head -n1 | "
               "awk '{print $4}' | awk -F. '{print $1}'")
        cmd_result = utils.run(cmd, ignore_status=True)
        cpu_frequency_os = cmd_result.stdout.strip()
        print cpu_frequency_os
        if not re.match(cpu_frequency_nodeinfo, cpu_frequency_os):
            raise error.TestFail("Virsh nodeinfo output didn't match CPU "
                                 "frequency")

        # Check CPU socket(s)
        cpu_sockets_nodeinfo = int(_check_nodeinfo(nodeinfo_output, 'CPU socket(s)', 3))
        cmd = "grep 'physical id' /proc/cpuinfo | uniq | sort | uniq |wc -l"
        cmd_result = utils.run(cmd, ignore_status=True)
        cpu_NUMA_nodeinfo = _check_nodeinfo(nodeinfo_output, 'NUMA cell(s)', 3)
        cpu_sockets_os = int(cmd_result.stdout.strip())/int(cpu_NUMA_nodeinfo)
        if cpu_sockets_os != cpu_sockets_nodeinfo:
            raise error.TestFail("Virsh nodeinfo output didn't match CPU "
                                 "socket(s)")

        # Check Core(s) per socket
        cores_per_socket_nodeinfo = _check_nodeinfo(nodeinfo_output, 'Core(s) per socket', 4)
        cmd = "grep 'cpu cores' /proc/cpuinfo | head -n1 | awk '{print $4}'"
        cmd_result = utils.run(cmd, ignore_status=True)
        cores_per_socket_os = cmd_result.stdout.strip()
        if not re.match(cores_per_socket_nodeinfo, cores_per_socket_os):
            raise error.TestFail("Virsh nodeinfo output didn't match Core(s) "
                                 "per socket")

        # Check Memory size
        memory_size_nodeinfo = int(_check_nodeinfo(nodeinfo_output, 'Memory size', 3))
        memory_size_os = utils.memtotal()
        if memory_size_nodeinfo != memory_size_os:
            raise error.TestFail("Virsh nodeinfo output didn't match "
                                 "Memory size")


    # Prepare libvirtd service
    check_libvirtd = params.has_key("libvirtd")
    if check_libvirtd:
        libvirtd = params.get("libvirtd")
        if libvirtd == "off":
            libvirt_vm.service_libvirtd_control("stop")

    # Run test case
    option = params.get("virsh_node_options")
    cmd_result = libvirt_vm.virsh_nodeinfo(ignore_status=True, extra=option)
    logging.info("Output:\n%s", cmd_result.stdout.strip())
    logging.info("Status: %d", cmd_result.exit_status)
    logging.error("Error: %s", cmd_result.stderr.strip())
    output = cmd_result.stdout.strip()
    status = cmd_result.exit_status


    # Recover libvirtd service start
    if libvirtd == "off":
        libvirt_vm.service_libvirtd_control("start")

    # Check status_error
    status_error = params.get("status_error")
    if status_error == "yes":
        if status == 0:
            if libvirtd == "off":
                raise error.TestFail("Command 'virsh nodeinfo' succeeded "
                                     "with libvirtd service stopped, incorrect")
            else:
                raise error.TestFail("Command 'virsh nodeinfo %s' succeeded"
                                     "(incorrect command)" % option)
    elif status_error == "no":
        output_check(output)
        if status != 0:
            raise error.TestFail("Command 'virsh nodeinfo %s' failed "
                                 "(correct command)" % option)
