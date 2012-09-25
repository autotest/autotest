import os, logging, time
from virttest import utils_misc, aexpect
from autotest.client.shared import openvswitch, error, utils
from autotest.client.utils import ForAll, ForAllP, ForAllPSE
from autotest.client.tests.openvswitch import ovs_utils


def allow_iperf_firewall(machine):
    machine.cmd("iptables -I INPUT -p tcp --dport 5001 --j ACCEPT")
    machine.cmd("iptables -I INPUT -p udp --dport 5001 --j ACCEPT")


class MiniSubtest(object):
    def __new__(cls, *args, **kargs):
        self = super(MiniSubtest, cls).__new__(cls)
        ret = None
        if args is None:
            args = []
        try:
            if hasattr(self, "setup"):
                self.setup(*args, **kargs)

            ret = self.test(*args, **kargs)
        finally:
            if hasattr(self, "clean"):
                self.clean(*args, **kargs)
        return ret


class InfrastructureInit(MiniSubtest):
    def setup(self, test, params, env):
        self.br0_name = "br0-%s" % (utils_misc.generate_random_string(3))
        while self.br0_name in utils_misc.get_net_if():
            self.br0_name = "br0-%s" % (utils_misc.generate_random_string(3))

        self.ovs = None

        error.context("Try to log into guest.")
        self.vms = [env.get_vm(vm) for vm in params.get("vms").split()]
        for vm in self.vms:
            vm.verify_alive()

        error.context("Start OpenVSwitch.")
        self.ovs = openvswitch.OpenVSwitchSystem()
        self.ovs.init_system()
        self.ovs.check()
        error.context("Add new bridge %s." % (self.br0_name))
        self.ovs.add_br(self.br0_name)
        utils_misc.set_net_if_ip(self.br0_name, params.get("bridge_ip"))
        utils_misc.bring_up_ifname(self.br0_name)
        self.dns_pidf = (utils_misc.check_add_dnsmasq_to_br(self.br0_name,
                                                            test.tmpdir))
        error.context("Add new ports from vms %s to bridge %s." %
                        (self.vms, self.br0_name))

        for vm in self.vms:
            utils_misc.change_iface_bridge(vm.virtnet[1],
                                           self.br0_name,
                                           self.ovs)


        logging.debug(self.ovs.status())
        self.host = ovs_utils.Machine(src=test.srcdir)
        self.mvms = [ovs_utils.Machine(vm) for vm in self.vms]
        self.machines = [self.host] + self.mvms

        #ForAllP(self.mvms).cmd("dhclinet")

        time.sleep(5)
        ForAllP(self.machines).fill_addrs()


    def clean(self, test, params, env):
        if self.ovs:
            try:
                utils.signal_program(self.dns_pidf[0:-4],
                                     pid_files_dir=test.tmpdir)
            except:
                pass
            try:
                self.ovs.del_br(self.br0_name)
            except Exception:
                pass
            if self.ovs.cleanup:
                self.ovs.clean()


@error.context_aware
def run_ovs_basic(test, params, env):
    """
    Run basic test of OpenVSwitch driver.
    """
    class test_ping(InfrastructureInit):
        def test(self, test, params, env):
            count = params.get("ping_count", 10)
            for mvm in self.mvms:
                for p_mvm in self.mvms:
                    addr = None
                    if p_mvm.is_virtual():
                        addr = p_mvm.virtnet[1].ip["ipv6"][0]
                    else:
                        addr = p_mvm.addrs[self.br0_name]["ipv6"][0]

                    if p_mvm.is_virtual():
                        mvm.ping_to(addr, 1, count)
                    else:
                        mvm.ping_to(addr, self.br0_name, count)


    class test_iperf(InfrastructureInit):
        def start_servers(self):
            ForAllP(self.machines).cmd_in_src("%s -s &> /dev/null &" %
                                               (self.iperf_b_path))
            ForAllP(self.machines).cmd_in_src("%s -s -u &> /dev/null &" %
                                               (self.iperf_b_path))


        def iperf_client(self, machine, server_ip, add_params):
            out = machine.cmd_in_src("%s -c %s %s" %
                                (self.iperf_b_path,
                                 server_ip,
                                 add_params))
            return " ".join(out.splitlines()[-1].split()[6:8])


        def test_bandwidth(self, add_params=None):
            if add_params is None:
                add_params = ""

            speeds = []
            speeds.append(self.iperf_client(self.mvms[0],
                                    self.host.addrs[self.br0_name]["ipv4"][0],
                                    add_params))


            speeds.append(self.iperf_client(self.host,
                                    self.mvms[0].virtnet[1].ip["ipv4"][0],
                                    add_params))


            speeds.append(self.iperf_client(self.mvms[0],
                                         self.mvms[1].virtnet[1].ip["ipv4"][0],
                                         add_params))

            return speeds


        def test(self, test, params, env):
            iperf_src_path = os.path.join(test.virtdir, "deps")
            self.iperf_b_path = os.path.join("iperf-2.0.4", "src", "iperf")

            error.context("Install iperf to vms machine.")
            ForAllP(self.machines).compile_autotools_app_tar(iperf_src_path,
                                                         "iperf-2.0.4.tar.gz")

            allow_iperf_firewall(self.host)
            ForAllP(self.mvms).cmd("iptables -F")

            self.start_servers()

            #test tcp bandwithd
            error.context("Test iperf bandwidth tcp.")
            speeds = self.test_bandwidth()
            logging.info("TCP Bandwidth from vm->host: %s" % (speeds[0]))
            logging.info("TCP Bandwidth from host->vm: %s" % (speeds[1]))
            logging.info("TCP Bandwidth from vm->vm: %s" % (speeds[2]))

            #test udp bandwithd limited to 1Gb
            error.context("Test iperf bandwidth udp.")
            speeds = self.test_bandwidth("-u -b 1G")
            logging.info("UDP Bandwidth from vm->host: %s" % (speeds[0]))
            logging.info("UDP Bandwidth from host->vm: %s" % (speeds[1]))
            logging.info("UDP Bandwidth from vm->vm: %s" % (speeds[2]))


        def clean(self, test, params, env):
            self.host.cmd("killall -9 iperf")
            super(test_iperf, self).clean(test, params, env)


    class test_vlan_ping(InfrastructureInit):
        def test(self, test, params, env):
            count = params.get("ping_count", 10)
            ret = ForAllPSE(self.mvms).ping_to(self.host.addrs[self.br0_name]
                                               ["ipv6"][0], 1, count)
            for ret, vm in zip(ret, self.mvms):
                if "exception" in ret:
                    raise error.TestError("Vm %s can't ping to hoqst:\n %s" %
                                            (vm.name, ret.exception))


            error.context("Add OpenVSwitch device to vlan.")
            self.ovs.add_port_tag(self.mvms[0].virtnet[1].ifname, "1")
            self.ovs.add_port_tag(self.mvms[1].virtnet[1].ifname, "1")
            self.ovs.add_port_tag(self.mvms[2].virtnet[1].ifname, "2")
            self.ovs.add_port_tag(self.mvms[3].virtnet[1].ifname, "2")

            error.context("Ping all devices in vlan.")
            self.mvms[2].ping_to(self.mvms[3].virtnet[1].ip["ipv6"][0], 1, 2)
            self.mvms[3].ping_to(self.mvms[2].virtnet[1].ip["ipv6"][0], 1, 2)

            self.mvms[0].ping_to(self.mvms[1].virtnet[1].ip["ipv6"][0], 1, 1)
            self.mvms[1].ping_to(self.mvms[0].virtnet[1].ip["ipv6"][0], 1, 1)

            try:
                self.mvms[0].ping_to(self.mvms[2].virtnet[1].ip["ipv6"][0],
                                     1, 2)
                raise error.TestError("Vm %s can't ping to host:\n %s" %
                                                (vm.name, ret.exception))
            except (error.CmdError, aexpect.ShellError):
                pass

            self.mvms[0].add_vlan_iface(self.mvms[0].virtnet[1].g_nic_name, 1)
            self.mvms[0].add_vlan_iface(self.mvms[0].virtnet[1].g_nic_name, 2)

            self.ovs.add_port_tag(self.mvms[0].virtnet[1].ifname, "[]")
            self.ovs.add_port_trunk(self.mvms[0].virtnet[1].ifname, [1, 2])

            time.sleep(1)
            error.context("Ping all devices in vlan.")
            self.mvms[0].ping_to(self.mvms[1].virtnet[1].ip["ipv6"][0], 1,
                                 count, vlan=1)
            self.mvms[0].ping_to(self.mvms[2].virtnet[1].ip["ipv6"][0], 1,
                                 count, vlan=2)
            self.mvms[1].ping_to(self.mvms[0].virtnet[1].ip["ipv6"][0], 1,
                                 count)
            self.mvms[2].ping_to(self.mvms[0].virtnet[1].ip["ipv6"][0], 1,
                                 count)

            try:
                self.mvms[0].ping_to(self.mvms[2].virtnet[1].ip["ipv6"][0],
                                     1, 2)
                raise error.TestError("Vm %s can't ping to host:\n %s" %
                                                (vm.name, ret.exception))
            except (error.CmdError, aexpect.ShellError):
                pass


            for i in range(0, 4095, 10):
                self.ovs.add_port_tag(self.mvms[0].virtnet[1].ifname, "[]")
                self.ovs.add_port_trunk(self.mvms[0].virtnet[1].ifname, [i])

            self.ovs.add_port_trunk(self.mvms[0].virtnet[1].ifname,
                                    range(4095))

            self.ovs.add_port_trunk(self.mvms[0].virtnet[1].ifname, [1])

            self.mvms[0].ping_to(self.mvms[1].virtnet[1].ip["ipv6"][0], 1,
                                count, vlan=1)


    test_type = "test_" + params.get("test_type")
    if (test_type in locals()):
        tests_group = locals()[test_type]
        tests_group(test, params, env)
    else:
        raise error.TestFail("Test type '%s' is not defined in"
                             " OpenVSwitch basic test" % test_type)
