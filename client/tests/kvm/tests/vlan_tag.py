import logging, time
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils, kvm_utils


def run_vlan_tag(test, params, env):
    """
    Test 802.1Q vlan of NIC, config it by vconfig command.

    1) Create two VMs.
    2) Setup guests in different VLANs by vconfig and test communication by
       ping using hard-coded ip addresses.
    3) Setup guests in same vlan and test communication by ping.
    4) Recover the vlan config.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    subnet = params.get("subnet")
    vlans = params.get("vlans").split()

    vm1 = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    vm2 = kvm_test_utils.get_living_vm(env, "vm2")

    timeout = int(params.get("login_timeout", 360))
    session1 = kvm_test_utils.wait_for_login(vm1, timeout=timeout)
    session2 = kvm_test_utils.wait_for_login(vm2, timeout=timeout)

    try:
        ip_cfg_base = "vconfig add eth0 %s && ifconfig eth0.%s %s.%s"
        ip_cfg_cmd1 = ip_cfg_base % (vlans[0], vlans[0], subnet, "11")
        ip_cfg_cmd2 = ip_cfg_base % (vlans[1], vlans[1], subnet, "12")

        # Configure VM1 and VM2 in different VLANs
        ip_cfg_vm1 = session1.get_command_status(ip_cfg_cmd1)
        if ip_cfg_vm1 != 0:
            raise error.TestError("Failed to config VM 1 IP address")
        ip_cfg_vm2 = session2.get_command_status(ip_cfg_cmd2)
        if ip_cfg_vm2 != 0:
            raise error.TestError("Failed to config VM 2 IP address")

        # Trying to ping VM 2 from VM 1, this shouldn't work
        ping_cmd = "ping -c 2 -I eth0.%s %s.%s" % (vlans[0], subnet, "12")
        ping_diff_vlan = session1.get_command_status(ping_cmd)
        if ping_diff_vlan == 0:
            raise error.TestFail("VM 2 can be reached even though it was "
                                 "configured on a different VLAN")

        # Now let's put VM 2 in the same VLAN as VM 1
        ip_cfg_reconfig= ("vconfig rem eth0.%s && vconfig add eth0 %s && "
                          "ifconfig eth0.%s %s.%s" % (vlans[1], vlans[0],
                                                      vlans[0], subnet, "12"))
        ip_cfg_vm2 = session2.get_command_status(ip_cfg_reconfig)
        if ip_cfg_vm2 != 0:
            raise error.TestError("Failed to re-config IP address of VM 2")

        # Try to ping VM 2 from VM 1, this should work
        ping_same_vlan = session1.get_command_status(ping_cmd)
        if ping_same_vlan != 0:
            raise error.TestFail("Failed to ping VM 2 even though it was "
                                 "configured on the same VLAN")

    finally:
        session1.get_command_status("vconfig rem eth0.%s" % vlans[0])
        session1.close()
        session2.get_command_status("vconfig rem eth0.%s" % vlans[0])
        session2.close()
