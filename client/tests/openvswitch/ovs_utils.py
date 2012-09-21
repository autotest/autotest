import logging, os, re, shutil
from autotest.client.tests.virt.virttest import utils_misc
from autotest.client.shared import error, utils


class Machine(object):
    def __init__(self, vm=None, src=None):
        self.vm = vm
        self.session = None
        self.runner = utils_misc.local_runner
        self.runner_status = utils_misc.local_runner_status
        self.bg_runner = utils.BgJob
        self.src = src
        self.addrs = None
        if vm:
            self.session = vm.wait_for_login()
            self.runner = self.session.cmd
            self.runner_status = self.session.cmd_status
            self.bg_runner = self.session.sendline
            self.src = os.path.join("/", "tmp", "src")


    def is_virtual(self):
        """
        @return True when Machine is virtual.
        """
        return not self.vm is None


    def cmd(self, cmd, timeout=60):
        """
        Return outpu of command.
        """
        return self.runner(cmd, timeout=timeout)


    def cmd_state(self, cmd, timeout=60):
        """
        Return status of command.
        """
        return self.runner_status(cmd, timeout=timeout)


    def cmd_in_src(self, cmd, timeout=60):
        cmd = os.path.join(self.src, cmd)
        return self.runner(cmd, timeout=timeout)


    def fill_addrs(self):
        self.addrs = utils_misc.get_net_if_and_addrs(self.runner)
        if self.vm:
            self.vm.fill_addrs(self.addrs)


    def get_linkv6_addr(self, ifname):
        """
        Get IPv6 address with link range.

        @param ifname: String or int. Int could be used only for virt Machine.
        @return: IPv6 link address.
        """
        if self.is_virtual() and type(ifname) is int:
            ifname = self.vm.virtnet[ifname].g_nic_name
        return utils_misc.ipv6_from_mac_addr(self.addrs[ifname]['mac'])


    def ping_to(self, dst, iface=None, count=1, vlan=0, ipv=None):
        """
        Ping from vm to destination.
        """
        if ipv is None:
            ipv = "ipv6"

        if ipv == "ipv6":
            if iface is None:
                raise error.TestError("iface cannot be None.")

            if self.vm:
                iface = self.get_if_vlan_name(self.vm.virtnet[iface].g_nic_name,
                                              vlan)
                return ping6(iface, dst, count,
                             self.runner)
            else:
                iface = self.get_if_vlan_name(iface, vlan)
                return ping6(iface, dst, count, self.runner)
        elif ipv == "ipv4":
            return ping4(dst, count, self.runner)


    def add_vlan_iface(self, iface, vlan_id):
        """
        Add vlan link for iface

        @param iface: Interface on which should be added vlan.
        @param vlan_id: Id of vlan.
        """
        self.cmd("ip link add link %s name %s-vl%s type vlan id %s" %
                    (iface, iface, vlan_id, vlan_id))


    def del_vlan_iface(self, iface, vlan_id):
        """
        Del vlan link for iface

        @param iface: Interface from which should be deleted vlan.
        @param vlan_id: Id of vlan.
        """
        self.cmd("ip link del %s" % (iface))


    def bring_iface_up(self, iface):
        """
        Bring iface up
        """
        self.cmd("ip link set %s up" % (iface))


    def bring_iface_down(self, iface):
        """
        Bring iface up
        """
        self.cmd("ip link set %s down" % (iface))


    def get_vlans_ifname(self):
        """
        Return vlans interface name.

        @return: dict of {"ifname": [(vlanid, ifname),(...)],...}
        """
        ret = dict()
        vlans = self.cmd("cat /proc/net/vlan/config")
        v = re.findall("^(\S+)\s*\|\s*(\S+)\s*\|\s*(\S+)\s*$",
                          vlans, re.MULTILINE)
        for vl_ifname, vl_id, ifname in v:
            if ifname in ret:
                ret[ifname][int(vl_id)] = vl_ifname
            else:
                ret[ifname] = {int(vl_id): vl_ifname}

        return ret


    def get_if_vlan_name(self, ifname, vlan_id=0):
        if vlan_id == 0:
            return ifname

        vlans = self.get_vlans_ifname()
        if ifname in vlans:
            if vlan_id in vlans[ifname]:
                return vlans[ifname][vlan_id]
            else:
                raise utils_misc.VlanError(ifname,
                                           "Interface %s has no vlan with"
                                           " id %s" % (ifname, vlan_id))
        else:
            raise utils_misc.VlanError(ifname,
                                       "Interface %s has no vlans" % (ifname))


    def prepare_directory(self, path, cleanup=False):
        """
        Prepare dest directory. Create if directory not exist.

        @param path: Path to directory
        @param cleanup: It true clears the contents of directory.
        """
        if self.cmd_state("[ -x %s ]" % path):
            self.cmd("mkdir -p %s" % path)

        if cleanup:
            self.cmd("rm -rf %s" % (os.path.join(path, "*")))


    def copy_to(self, src, dst):
        if self.vm:
            self.vm.copy_files_to(src, dst)
        else:
            shutil.copy(src, dst)


    def compile_autotools_app_tar(self, path, package_name):
        """
        Compile app on machine in src dir.

        @param path: Path where shoule be program compiled.
        @param dst_dir: Installation path.
        """
        logging.debug("Install %s to %s." % (package_name, self.src))
        self.prepare_directory(self.src)

        pack_dir = None
        if package_name.endswith("tar.gz"):
            pack_dir = package_name[0:-len(".tar.gz")]
            unpack_cmd = ("tar -xvzf %s; cd %s;" % (package_name, pack_dir))
        elif package_name.endswith("tgz"):
            pack_dir = package_name[0:-len(".tgz")]
            unpack_cmd = ("tar -xvzf %s; cd %s;" % (package_name, pack_dir))
        elif package_name.endswith(("tar.bz2")):
            pack_dir = package_name[0:-len(".tar.br2")]
            unpack_cmd = ("tar -xvjf %s; cd %s;" % (package_name, pack_dir))

        self.copy_to(os.path.join(path, package_name), self.src)
        self.cmd("sync")
        self.cmd("cd %s; %s ./configure && make;" % (self.src, unpack_cmd),
                     timeout=240)
        self.cmd("sync")


    def __getattr__(self, name):
        if self.vm:
            try:
                return self.vm.__getattribute__(name)
            except AttributeError:
                return self.session.__getattribute__(name)
        raise AttributeError("Cannot find attribute %s in class" % name)


def ping6(iface, dst_ip, count=1, runner=None):
    """
    Format command for ipv6.
    """
    if runner == None:
        runner = utils.run
    return runner("ping6 -I %s %s -c %s" % (iface, dst_ip, count))


def ping4(iface, dst_ip, count=1, runner=None):
    """
    Format command for ipv6.
    """
    if runner == None:
        runner = utils.run
    return runner("ping  %s -c %s" % (dst_ip, count))
