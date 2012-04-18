import logging, os
from autotest.client.shared import error
from autotest.client.virt import virt_test_utils, virt_utils, aexpect


def run_nic_hotplug(test, params, env):
    """
    Test hotplug of NIC devices

    1) Boot up guest with one nic
    2) Add a host network device through monitor cmd and check if it's added
    3) Add nic device through monitor cmd and check if it's added
    4) Check if new interface gets ip address
    5) Disable primary link of guest
    6) Ping guest new ip from host
    7) Delete nic device and netdev
    8) Re-enable primary link of guest

    BEWARE OF THE NETWORK BRIDGE DEVICE USED FOR THIS TEST ("bridge" param).
    The KVM autotest default bridge virbr0, leveraging libvirt, works fine
    for the purpose of this test. When using other bridges, the timeouts
    which usually happen when the bridge topology changes (that is, devices
    get added and removed) may cause random failures.

    @param test:   KVM test object.
    @param params: Dictionary with the test parameters.
    @param env:    Dictionary with test environment.
    """
    vm = virt_test_utils.get_living_vm(env, params.get("main_vm"))
    login_timeout = int(params.get("login_timeout", 360))
    guest_delay = int(params.get("guest_delay", 20))
    pci_model = params.get("pci_model", "rtl8139")
    run_dhclient = params.get("run_dhclient", "no")
    guest_is_not_windows = "Win" not in params.get("guest_name", "")

    session = virt_test_utils.wait_for_login(vm, timeout=login_timeout)

    udev_rules_path = "/etc/udev/rules.d/70-persistent-net.rules"
    udev_rules_bkp_path = "/tmp/70-persistent-net.rules"

    def guest_path_isfile(path):
        try:
            session.cmd("test -f %s" % path)
        except aexpect.ShellError:
            return False
        return True

    if guest_is_not_windows:
        if guest_path_isfile(udev_rules_path):
            session.cmd("mv -f %s %s" % (udev_rules_path, udev_rules_bkp_path))

        # Modprobe the module if specified in config file
        module = params.get("modprobe_module")
        if module:
            session.get_command_output("modprobe %s" % module)

    # hot-add the nic
    nic_info = vm.add_nic(model=pci_model)

    # Only run dhclient if explicitly set and guest is not running Windows.
    # Most modern Linux guests run NetworkManager, and thus do not need this.
    if run_dhclient == "yes" and guest_is_not_windows:
        session_serial = vm.wait_for_serial_login(timeout=login_timeout)
        ifname = virt_test_utils.get_linux_ifname(session, nic_info['mac'])
        session_serial.cmd("dhclient %s &" % ifname)

    logging.info("Shutting down the primary link")
    vm.monitor.cmd("set_link %s off" % vm.netdev_id[0])

    try:
        logging.info("Waiting for new nic's ip address acquisition...")
        if not virt_utils.wait_for(lambda:
                                   (vm.address_cache.get(nic_info['mac'])
                                    is not None),
                                   10, 1):
            raise error.TestFail("Could not get ip address of new nic")

        ip = vm.address_cache.get(nic_info['mac'])

        if not virt_utils.verify_ip_address_ownership(ip, nic_info['mac']):
            raise error.TestFail("Could not verify the ip address of new nic")
        else:
            logging.info("Got the ip address of new nic: %s", ip)

        logging.info("Ping test the new nic ...")
        s, o = virt_test_utils.ping(ip, 100)
        if s != 0:
            logging.error(o)
            raise error.TestFail("New nic failed ping test")

        logging.info("Detaching the previously attached nic from vm")
        vm.del_nic(nic_info, guest_delay)

    finally:
        vm.free_mac_address(1)
        logging.info("Re-enabling the primary link")
        vm.monitor.cmd("set_link %s on" % vm.netdev_id[0])

    # Attempt to put back udev network naming rules, even if the command to
    # disable the rules failed. We may be undoing what was done in a previous
    # (failed) test that never reached this point.
    if guest_is_not_windows:
        if guest_path_isfile(udev_rules_bkp_path):
            session.cmd("mv -f %s %s" % (udev_rules_bkp_path, udev_rules_path))
