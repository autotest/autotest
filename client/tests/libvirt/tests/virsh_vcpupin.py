import logging, re, os, commands, string, math
from autotest.client.shared import utils, error
from autotest.client.virt import libvirt_vm
from autotest.client import *

def run_virsh_vcpupin(test, params, env):
    """
    Test the command virsh vcpupin

    (1) Get the host and guest cpu count
    (2) Call virsh vcpupin for each vcpu with pinning of each cpu
    (3) Check whether the virsh vcpupin has pinned the respective vcpu to cpu
    (4) TODO: Right now the testcase covers the pinning one cpu at a time
              this can be improved by a random number of cpus
    """

    # Initialize the variables
    expected_affinity = []
    total_affinity = []
    actual_affinity = []

    def build_actual_info(domname, vcpu):
        """
        This function returns list of the vcpu's affinity from
        virsh vcpuinfo output

        @param: domname: VM Name to operate on
        @param: vcpu: vcpu number for which the affinity is required
        """

        output = libvirt_vm.virsh_vcpuinfo(domname)
        cmd = re.findall('[^Affinity:][-y]+', str(output))
        total_affinity = cmd[vcpu].lstrip()
        actual_affinity = list(total_affinity)
        return actual_affinity


    def build_expected_info(vcpu, cpu):
        """
        This function returns the list of vcpu's expected affinity build

        @param: vcpu: vcpu number for which the affinity is required
        @param: cpu: cpu details for the affinity
        """

        expected_affinity = []

        for i in range(int(host_cpu_count)):
            expected_affinity.append('y')

        for i in range(int(host_cpu_count)):
            if cpu != i:
                expected_affinity[i] = '-'

        expected_affinity_proc = int(math.pow(2, cpu))
        return expected_affinity,expected_affinity_proc


    def virsh_check_vcpupin(domname, vcpu, cpu, pid):
        """
        This function checks the actual and the expected affinity of given vcpu
        and raises error if not matchs

        @param: domname:  VM Name to operate on
        @param: vcpu: vcpu number for which the affinity is required
        @param: cpu: cpu details for the affinity
        """

        expected_output,expected_output_proc = build_expected_info(vcpu, cpu)
        actual_output = build_actual_info(domname, vcpu)

        # Get the vcpus pid
        vcpus_pid = vm.get_vcpus_pid()
        vcpu_pid=vcpus_pid[vcpu]

        # Get the actual cpu affinity value in the proc entry
        output = utils.cpu_affinity_by_task(pid, vcpu_pid)
        actual_output_proc = int(output, 16)

        if expected_output == actual_output:
            logging.info("successfully pinned cpu: %s --> vcpu: %s", cpu, vcpu)
        else:
            raise error.TestFail("Command 'virsh vcpupin %s %s %s'not succeeded"
                                 ", cpu pinning details not updated properly in"
                                 " virsh vcpuinfo command output"
                                                         % (vm_name, vcpu, cpu))

        if expected_output_proc == actual_output_proc:
            logging.info("successfully pinned cpu: %s --> vcpu: %s"
                         " in respective proc entry"
                                                  ,cpu, vcpu)
        else:
            raise error.TestFail("Command 'virsh vcpupin %s %s %s'not succeeded"
                                 " cpu pinning details not updated properly in"
                                 " /proc/%s/task/%s/status"
                                          %(vm_name, vcpu, cpu, pid, vcpu_pid))


    # Get the vm name, pid of vm and check for alive
    vm_name = params.get("main_vm")
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    pid = vm.get_pid()

    # Get the host cpu count
    host_cpu_count = utils.count_cpus()

    # Get the guest vcpu count
    guest_vcpu_count = libvirt_vm.virsh_vcpucount_live(vm_name)

    # Run test case
    for vcpu in range(int(guest_vcpu_count)):
        for cpu in range(int(host_cpu_count)):
            vm.vcpupin(vcpu, cpu)
            virsh_check_vcpupin(vm_name, vcpu, cpu, pid)
