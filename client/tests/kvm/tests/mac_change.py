import logging
from autotest_lib.client.common_lib import error
import kvm_utils, kvm_test_utils


def run_mac_change(test, params, env):
    """
    Change MAC address of guest.

    1) Get a new mac from pool, and the old mac addr of guest.
    2) Set new mac in guest and regain new IP.
    3) Re-log into guest with new MAC.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    timeout = int(params.get("login_timeout", 360))
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    logging.info("Trying to log into guest '%s' by serial", vm.name)
    session = kvm_utils.wait_for(lambda: vm.serial_login(),
                                  timeout, 0, step=2)
    if not session:
        raise error.TestFail("Could not log into guest '%s'" % vm.name)

    old_mac = vm.get_mac_address(0)
    while True:
        vm.free_mac_address(0)
        new_mac = kvm_utils.generate_mac_address(vm.instance, 0)
        if old_mac != new_mac:
            break
    logging.info("The initial MAC address is %s", old_mac)
    interface = kvm_test_utils.get_linux_ifname(session, old_mac)
    # Start change MAC address
    logging.info("Changing MAC address to %s", new_mac)
    change_cmd = ("ifconfig %s down && ifconfig %s hw ether %s && "
                  "ifconfig %s up" % (interface, interface, new_mac, interface))
    if session.get_command_status(change_cmd) != 0:
        raise error.TestFail("Fail to send mac_change command")

    # Verify whether MAC address was changed to the new one
    logging.info("Verifying the new mac address")
    if session.get_command_status("ifconfig | grep -i %s" % new_mac) != 0:
        raise error.TestFail("Fail to change MAC address")

    # Restart `dhclient' to regain IP for new mac address
    logging.info("Restart the network to gain new IP")
    dhclient_cmd = "dhclient -r && dhclient %s" % interface
    session.sendline(dhclient_cmd)

    # Re-log into the guest after changing mac address
    if kvm_utils.wait_for(session.is_responsive, 120, 20, 3):
        # Just warning when failed to see the session become dead,
        # because there is a little chance the ip does not change.
        logging.warn("The session is still responsive, settings may fail.")
    session.close()

    # Re-log into guest and check if session is responsive
    logging.info("Re-log into the guest")
    session = kvm_test_utils.wait_for_login(vm,
              timeout=int(params.get("login_timeout", 360)))
    if not session.is_responsive():
        raise error.TestFail("The new session is not responsive.")

    session.close()
