import logging, commands, random
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
from autotest_lib.client.virt import virt_utils, virt_test_utils


def run_jumbo(test, params, env):
    """
    Test the RX jumbo frame function of vnics:

    1) Boot the VM.
    2) Change the MTU of guest nics and host taps depending on the NIC model.
    3) Add the static ARP entry for guest NIC.
    4) Wait for the MTU ok.
    5) Verify the path MTU using ping.
    6) Ping the guest with large frames.
    7) Increment size ping.
    8) Flood ping the guest with large frames.
    9) Verify the path MTU.
    10) Recover the MTU.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    session = vm.wait_for_login(timeout=int(params.get("login_timeout", 360)))
    mtu = params.get("mtu", "1500")
    flood_time = params.get("flood_time", "300")
    max_icmp_pkt_size = int(mtu) - 28

    ifname = vm.get_ifname(0)
    ip = vm.get_address(0)
    if ip is None:
        raise error.TestError("Could not get the IP address")

    try:
        # Environment preparation
        ethname = virt_test_utils.get_linux_ifname(session, vm.get_mac_address(0))

        logging.info("Changing the MTU of guest ...")
        guest_mtu_cmd = "ifconfig %s mtu %s" % (ethname , mtu)
        session.cmd(guest_mtu_cmd)

        logging.info("Chaning the MTU of host tap ...")
        host_mtu_cmd = "ifconfig %s mtu %s" % (ifname, mtu)
        utils.run(host_mtu_cmd)

        logging.info("Add a temporary static ARP entry ...")
        arp_add_cmd = "arp -s %s %s -i %s" % (ip, vm.get_mac_address(0), ifname)
        utils.run(arp_add_cmd)

        def is_mtu_ok():
            s, o = virt_test_utils.ping(ip, 1, interface=ifname,
                                       packetsize=max_icmp_pkt_size,
                                       hint="do", timeout=2)
            return s == 0

        def verify_mtu():
            logging.info("Verify the path MTU")
            s, o = virt_test_utils.ping(ip, 10, interface=ifname,
                                       packetsize=max_icmp_pkt_size,
                                       hint="do", timeout=15)
            if s != 0 :
                logging.error(o)
                raise error.TestFail("Path MTU is not as expected")
            if virt_test_utils.get_loss_ratio(o) != 0:
                logging.error(o)
                raise error.TestFail("Packet loss ratio during MTU "
                                     "verification is not zero")

        def flood_ping():
            logging.info("Flood with large frames")
            virt_test_utils.ping(ip, interface=ifname,
                                packetsize=max_icmp_pkt_size,
                                flood=True, timeout=float(flood_time))

        def large_frame_ping(count=100):
            logging.info("Large frame ping")
            s, o = virt_test_utils.ping(ip, count, interface=ifname,
                                       packetsize=max_icmp_pkt_size,
                                       timeout=float(count) * 2)
            ratio = virt_test_utils.get_loss_ratio(o)
            if ratio != 0:
                raise error.TestFail("Loss ratio of large frame ping is %s" %
                                     ratio)

        def size_increase_ping(step=random.randrange(90, 110)):
            logging.info("Size increase ping")
            for size in range(0, max_icmp_pkt_size + 1, step):
                logging.info("Ping %s with size %s", ip, size)
                s, o = virt_test_utils.ping(ip, 1, interface=ifname,
                                           packetsize=size,
                                           hint="do", timeout=1)
                if s != 0:
                    s, o = virt_test_utils.ping(ip, 10, interface=ifname,
                                               packetsize=size,
                                               adaptive=True, hint="do",
                                               timeout=20)

                    if virt_test_utils.get_loss_ratio(o) > int(params.get(
                                                      "fail_ratio", 50)):
                        raise error.TestFail("Ping loss ratio is greater "
                                             "than 50% for size %s" % size)

        logging.info("Waiting for the MTU to be OK")
        wait_mtu_ok = 10
        if not virt_utils.wait_for(is_mtu_ok, wait_mtu_ok, 0, 1):
            logging.debug(commands.getoutput("ifconfig -a"))
            raise error.TestError("MTU is not as expected even after %s "
                                  "seconds" % wait_mtu_ok)

        # Functional Test
        verify_mtu()
        large_frame_ping()
        size_increase_ping()

        # Stress test
        flood_ping()
        verify_mtu()

    finally:
        # Environment clean
        session.close()
        logging.info("Removing the temporary ARP entry")
        utils.run("arp -d %s -i %s" % (ip, ifname))
