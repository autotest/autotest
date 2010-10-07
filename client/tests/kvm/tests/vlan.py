import logging, time, re
from autotest_lib.client.common_lib import error
import kvm_test_utils, kvm_utils

def run_vlan(test, params, env):
    """
    Test 802.1Q vlan of NIC, config it by vconfig command.

    1) Create two VMs.
    2) Setup guests in 10 different vlans by vconfig and using hard-coded
       ip address.
    3) Test by ping between same and different vlans of two VMs.
    4) Test by TCP data transfer, floop ping between same vlan of two VMs.
    5) Test maximal plumb/unplumb vlans.
    6) Recover the vlan config.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """

    vm = []
    session = []
    ifname = []
    vm_ip = []
    digest_origin = []
    vlan_ip = ['', '']
    ip_unit = ['1', '2']
    subnet = params.get("subnet")
    vlan_num = int(params.get("vlan_num"))
    maximal = int(params.get("maximal"))
    file_size = params.get("file_size")

    vm.append(kvm_test_utils.get_living_vm(env, params.get("main_vm")))
    vm.append(kvm_test_utils.get_living_vm(env, "vm2"))

    def add_vlan(session, id, iface="eth0"):
        if session.get_command_status("vconfig add %s %s" % (iface, id)) != 0:
            raise error.TestError("Fail to add %s.%s" % (iface, id))

    def set_ip_vlan(session, id, ip, iface="eth0"):
        iface = "%s.%s" % (iface, id)
        if session.get_command_status("ifconfig %s %s" % (iface, ip)) != 0:
            raise error.TestError("Fail to configure ip for %s" % iface)

    def set_arp_ignore(session, iface="eth0"):
        ignore_cmd = "echo 1 > /proc/sys/net/ipv4/conf/all/arp_ignore"
        if session.get_command_status(ignore_cmd) != 0:
            raise error.TestError("Fail to set arp_ignore of %s" % session)

    def rem_vlan(session, id, iface="eth0"):
        rem_vlan_cmd = "if [[ -e /proc/net/vlan/%s ]];then vconfig rem %s;fi"
        iface = "%s.%s" % (iface, id)
        s = session.get_command_status(rem_vlan_cmd % (iface, iface))
        return s

    def nc_transfer(src, dst):
        nc_port = kvm_utils.find_free_port(1025, 5334, vm_ip[dst])
        listen_cmd = params.get("listen_cmd")
        send_cmd = params.get("send_cmd")

        #listen in dst
        listen_cmd = listen_cmd % (nc_port, "receive")
        session[dst].sendline(listen_cmd)
        time.sleep(2)
        #send file from src to dst
        send_cmd = send_cmd % (vlan_ip[dst], str(nc_port), "file")
        if session[src].get_command_status(send_cmd, timeout = 60) != 0:
            raise error.TestFail ("Fail to send file"
                                    " from vm%s to vm%s" % (src+1, dst+1))
        s, o = session[dst].read_up_to_prompt(timeout=60)
        if s != True:
            raise error.TestFail ("Fail to receive file"
                                    " from vm%s to vm%s" % (src+1, dst+1))
        #check MD5 message digest of receive file in dst
        output = session[dst].get_command_output("md5sum receive").strip()
        digest_receive = re.findall(r'(\w+)', output)[0]
        if digest_receive == digest_origin[src]:
            logging.info("file succeed received in vm %s" % vlan_ip[dst])
        else:
            logging.info("digest_origin is  %s" % digest_origin[src])
            logging.info("digest_receive is %s" % digest_receive)
            raise error.TestFail("File transfered differ from origin")
        session[dst].get_command_status("rm -f receive")

    for i in range(2):
        session.append(kvm_test_utils.wait_for_login(vm[i],
                       timeout=int(params.get("login_timeout", 360))))
        if not session[i] :
            raise error.TestError("Could not log into guest(vm%d)" % i)
        logging.info("Logged in")

        ifname.append(kvm_test_utils.get_linux_ifname(session[i],
                      vm[i].get_mac_address()))
        #get guest ip
        vm_ip.append(vm[i].get_address())

        #produce sized file in vm
        dd_cmd = "dd if=/dev/urandom of=file bs=1024k count=%s"
        if session[i].get_command_status(dd_cmd % file_size) != 0:
            raise error.TestFail("File producing failed")
        #record MD5 message digest of file
        s, output =session[i].get_command_status_output("md5sum file",
                                                        timeout=60)
        if s != 0:
            raise error.TestFail("File MD5_checking failed" )
        digest_origin.append(re.findall(r'(\w+)', output)[0])

        #stop firewall in vm
        session[i].get_command_status("/etc/init.d/iptables stop")

        #load 8021q module for vconfig
        load_8021q_cmd = "modprobe 8021q"
        if session[i].get_command_status(load_8021q_cmd) != 0:
            raise error.TestError("Fail to load 8021q module on VM%s" % i)

    try:
        for i in range(2):
            for vlan_i in range(1, vlan_num+1):
                add_vlan(session[i], vlan_i, ifname[i])
                set_ip_vlan(session[i], vlan_i, "%s.%s.%s" %
                            (subnet, vlan_i, ip_unit[i]), ifname[i])
            set_arp_ignore(session[i], ifname[i])

        for vlan in range(1, vlan_num+1):
            logging.info("Test for vlan %s" % vlan)

            logging.info("Ping between vlans")
            interface = ifname[0] + '.' + str(vlan)
            for vlan2 in range(1, vlan_num+1):
                for i in range(2):
                    interface = ifname[i] + '.' + str(vlan)
                    dest = subnet +'.'+ str(vlan2)+ '.' + ip_unit[(i+1)%2]
                    s, o = kvm_test_utils.ping(dest, count=2,
                                              interface=interface,
                                              session=session[i], timeout=30)
                    if ((vlan == vlan2) ^ (s == 0)):
                        raise error.TestFail ("%s ping %s unexpected" %
                                                    (interface, dest))

            vlan_ip[0] = subnet + '.' + str(vlan) + '.' + ip_unit[0]
            vlan_ip[1] = subnet + '.' + str(vlan) + '.' + ip_unit[1]

            logging.info("Flood ping")
            def flood_ping(src, dst):
                # we must use a dedicated session becuase the kvm_subprocess
                # does not have the other method to interrupt the process in
                # the guest rather than close the session.
                session_flood = kvm_test_utils.wait_for_login(vm[src],
                                                              timeout = 60)
                kvm_test_utils.ping(vlan_ip[dst], flood=True,
                                   interface=ifname[src],
                                   session=session_flood, timeout=10)
                session_flood.close()

            flood_ping(0,1)
            flood_ping(1,0)

            logging.info("Transfering data through nc")
            nc_transfer(0, 1)
            nc_transfer(1, 0)

    finally:
        for vlan in range(1, vlan_num+1):
            rem_vlan(session[0], vlan, ifname[0])
            rem_vlan(session[1], vlan, ifname[1])
            logging.info("rem vlan: %s" % vlan)

    # Plumb/unplumb maximal unber of vlan interfaces
    i = 1
    s = 0
    try:
        logging.info("Testing the plumb of vlan interface")
        for i in range (1, maximal+1):
            add_vlan(session[0], i, ifname[0])
    finally:
        for j in range (1, i+1):
            s = s or rem_vlan(session[0], j, ifname[0])
        if s == 0:
            logging.info("maximal interface plumb test done")
        else:
            logging.error("maximal interface plumb test failed")

    session[0].close()
    session[1].close()
