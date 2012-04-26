import logging
from autotest.client.shared import error
from autotest.client.virt import virt_utils, virt_test_utils


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
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session_serial = vm.wait_for_serial_login(timeout=timeout)
    # This session will be used to assess whether the IP change worked
    session = vm.wait_for_login(timeout=timeout)
    old_mac = vm.get_mac_address(0)
    while True:
        vm.free_mac_address(0)
        new_mac = virt_utils.generate_mac_address(vm.instance, 0)
        if old_mac != new_mac:
            break
    logging.info("The initial MAC address is %s", old_mac)
    interface = virt_test_utils.get_linux_ifname(session_serial, old_mac)
    # Start change MAC address
    logging.info("Changing MAC address to %s", new_mac)
    change_cmd = ("ifconfig %s down && ifconfig %s hw ether %s && "
                  "ifconfig %s up" % (interface, interface, new_mac, interface))
    session_serial.cmd(change_cmd)

    # Verify whether MAC address was changed to the new one
    logging.info("Verifying the new mac address")
    session_serial.cmd("ifconfig | grep -i %s" % new_mac)

    # Restart `dhclient' to regain IP for new mac address
    logging.info("Restart the network to gain new IP")
    dhclient_cmd = "dhclient -r && dhclient %s" % interface
    session_serial.sendline(dhclient_cmd)

    # Re-log into the guest after changing mac address
    if virt_utils.wait_for(session.is_responsive, 120, 20, 3):
        # Just warning when failed to see the session become dead,
        # because there is a little chance the ip does not change.
        logging.warn("The session is still responsive, settings may fail.")
    session.close()

    # Re-log into guest and check if session is responsive
    logging.info("Re-log into the guest")
    session = vm.wait_for_login(timeout=timeout)
    if not session.is_responsive():
        raise error.TestFail("The new session is not responsive.")

    session.close()
