"""
Library to perform pre/post test setup for KVM autotest.
"""
import os, logging
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils


class HugePageConfig(object):
    def __init__(self, params):
        """
        Gets environment variable values and calculates the target number
        of huge memory pages.

        @param params: Dict like object containing parameters for the test.
        """
        self.vms = len(params.objects("vms"))
        self.mem = int(params.get("mem"))
        self.max_vms = int(params.get("max_vms", 0))
        self.hugepage_path = '/mnt/kvm_hugepage'
        self.hugepage_size = self.get_hugepage_size()
        self.target_hugepages = self.get_target_hugepages()
        self.kernel_hp_file = '/proc/sys/vm/nr_hugepages'


    def get_hugepage_size(self):
        """
        Get the current system setting for huge memory page size.
        """
        meminfo = open('/proc/meminfo', 'r').readlines()
        huge_line_list = [h for h in meminfo if h.startswith("Hugepagesize")]
        try:
            return int(huge_line_list[0].split()[1])
        except ValueError, e:
            raise ValueError("Could not get huge page size setting from "
                             "/proc/meminfo: %s" % e)


    def get_target_hugepages(self):
        """
        Calculate the target number of hugepages for testing purposes.
        """
        if self.vms < self.max_vms:
            self.vms = self.max_vms
        # memory of all VMs plus qemu overhead of 64MB per guest
        vmsm = (self.vms * self.mem) + (self.vms * 64)
        return int(vmsm * 1024 / self.hugepage_size)


    @error.context_aware
    def set_hugepages(self):
        """
        Sets the hugepage limit to the target hugepage value calculated.
        """
        error.context("setting hugepages limit to %s" % self.target_hugepages)
        hugepage_cfg = open(self.kernel_hp_file, "r+")
        hp = hugepage_cfg.readline()
        while int(hp) < self.target_hugepages:
            loop_hp = hp
            hugepage_cfg.write(str(self.target_hugepages))
            hugepage_cfg.flush()
            hugepage_cfg.seek(0)
            hp = int(hugepage_cfg.readline())
            if loop_hp == hp:
                raise ValueError("Cannot set the kernel hugepage setting "
                                 "to the target value of %d hugepages." %
                                 self.target_hugepages)
        hugepage_cfg.close()
        logging.debug("Successfuly set %s large memory pages on host ",
                      self.target_hugepages)


    @error.context_aware
    def mount_hugepage_fs(self):
        """
        Verify if there's a hugetlbfs mount set. If there's none, will set up
        a hugetlbfs mount using the class attribute that defines the mount
        point.
        """
        error.context("mounting hugepages path")
        if not os.path.ismount(self.hugepage_path):
            if not os.path.isdir(self.hugepage_path):
                os.makedirs(self.hugepage_path)
            cmd = "mount -t hugetlbfs none %s" % self.hugepage_path
            utils.system(cmd)


    def setup(self):
        logging.debug("Number of VMs this test will use: %d", self.vms)
        logging.debug("Amount of memory used by each vm: %s", self.mem)
        logging.debug("System setting for large memory page size: %s",
                      self.hugepage_size)
        logging.debug("Number of large memory pages needed for this test: %s",
                      self.target_hugepages)
        self.set_hugepages()
        self.mount_hugepage_fs()


    @error.context_aware
    def cleanup(self):
        error.context("trying to dealocate hugepage memory")
        try:
            utils.system("umount %s" % self.hugepage_path)
        except error.CmdError:
            return
        utils.system("echo 0 > %s" % self.kernel_hp_file)
        logging.debug("Hugepage memory successfuly dealocated")


class PrivateBridgeError(Exception):
    def __init__(self, brname):
        self.brname = brname

    def __str__(self):
        return "Bridge %s not available after setup" % self.brname


class PrivateBridgeConfig(object):
    __shared_state = {}
    def __init__(self, params=None):
        self.__dict__ = self.__shared_state
        if params is not None:
            self.brname = params.get("priv_brname", 'atbr0')
            self.subnet = params.get("priv_subnet", '192.168.58')
            self.ip_version = params.get("bridge_ip_version", "ipv4")
            self.dhcp_server_pid = None
            self.iptables_rules = [
            "INPUT 1 -i %s -p udp -m udp --dport 53 -j ACCEPT" % self.brname,
            "INPUT 2 -i %s -p tcp -m tcp --dport 53 -j ACCEPT" % self.brname,
            "INPUT 3 -i %s -p udp -m udp --dport 67 -j ACCEPT" % self.brname,
            "INPUT 4 -i %s -p tcp -m tcp --dport 67 -j ACCEPT" % self.brname,
            "INPUT 5 -i %s -p tcp -m tcp --dport 12323 -j ACCEPT" % self.brname,
            "FORWARD 1 -m physdev --physdev-is-bridged -j ACCEPT",
            "FORWARD 2 -d %s.0/24 -o %s -m state --state RELATED,ESTABLISHED "
            "-j ACCEPT" % (self.subnet, self.brname),
            "FORWARD 3 -s %s.0/24 -i %s -j ACCEPT" % (self.subnet, self.brname),
            "FORWARD 4 -i %s -o %s -j ACCEPT" % (self.brname, self.brname),
            ("FORWARD 5 -o %s -j REJECT --reject-with icmp-port-unreachable" %
             self.brname),
            ("FORWARD 6 -i %s -j REJECT --reject-with icmp-port-unreachable" %
             self.brname)]


    def _add_bridge(self):
        utils.system("brctl addbr %s" % self.brname)
        ip_fwd_path = "/proc/sys/net/%s/ip_forward" % self.ip_version
        ip_fwd = open(ip_fwd_path, "w")
        ip_fwd.write("1\n")
        utils.system("brctl stp %s on" % self.brname)
        utils.system("brctl setfd %s 0" % self.brname)


    def _bring_bridge_up(self):
        utils.system("ifconfig %s %s.1 up" % (self.brname, self.subnet))


    def _iptables_add(self, cmd):
        return utils.system("iptables -I %s" % cmd)


    def _iptables_del(self, cmd):
        return utils.system("iptables -D %s" % cmd)


    def _enable_nat(self):
        for rule in self.iptables_rules:
            self._iptables_add(rule)


    def _start_dhcp_server(self):
        utils.system("service dnsmasq stop")
        utils.system("dnsmasq --strict-order --bind-interfaces "
                     "--listen-address %s.1 --dhcp-range %s.2,%s.254 "
                     "--dhcp-lease-max=253 "
                     "--dhcp-no-override "
                     "--pid-file=/tmp/dnsmasq.pid "
                     "--log-facility=/tmp/dnsmasq.log" %
                     (self.subnet, self.subnet, self.subnet))
        self.dhcp_server_pid = None
        try:
            self.dhcp_server_pid = int(open('/tmp/dnsmasq.pid', 'r').read())
        except ValueError:
            raise PrivateBridgeError(self.brname)
        logging.debug("Started internal DHCP server with PID %s",
                      self.dhcp_server_pid)


    def _verify_bridge(self):
        brctl_output = utils.system_output("brctl show")
        if self.brname not in brctl_output:
            raise PrivateBridgeError(self.brname)


    def setup(self):
        brctl_output = utils.system_output("brctl show")
        if self.brname not in brctl_output:
            logging.info("Configuring KVM test private bridge %s", self.brname)
            try:
                self._add_bridge()
            except:
                self._remove_bridge()
                raise
            try:
                self._bring_bridge_up()
            except:
                self._bring_bridge_down()
                self._remove_bridge()
                raise
            try:
                self._enable_nat()
            except:
                self._disable_nat()
                self._bring_bridge_down()
                self._remove_bridge()
                raise
            try:
                self._start_dhcp_server()
            except:
                self._stop_dhcp_server()
                self._disable_nat()
                self._bring_bridge_down()
                self._remove_bridge()
                raise
            self._verify_bridge()


    def _stop_dhcp_server(self):
        if self.dhcp_server_pid is not None:
            try:
                os.kill(self.dhcp_server_pid, 15)
            except OSError:
                pass
        else:
            try:
                dhcp_server_pid = int(open('/tmp/dnsmasq.pid', 'r').read())
            except ValueError:
                return
            try:
                os.kill(dhcp_server_pid, 15)
            except OSError:
                pass


    def _bring_bridge_down(self):
        utils.system("ifconfig %s down" % self.brname, ignore_status=True)


    def _disable_nat(self):
        for rule in self.iptables_rules:
            split_list = rule.split(' ')
            # We need to remove numbering here
            split_list.pop(1)
            rule = " ".join(split_list)
            self._iptables_del(rule)


    def _remove_bridge(self):
        utils.system("brctl delbr %s" % self.brname, ignore_status=True)


    def cleanup(self):
        brctl_output = utils.system_output("brctl show")
        cleanup = False
        for line in brctl_output.split("\n"):
            if line.startswith(self.brname):
                # len == 4 means there is a TAP using the bridge
                # so don't try to clean it up
                if len(line.split()) < 4:
                    cleanup = True
                    break
        if cleanup:
            logging.debug("Cleaning up KVM test private bridge %s", self.brname)
            self._stop_dhcp_server()
            self._disable_nat()
            self._bring_bridge_down()
            self._remove_bridge()
