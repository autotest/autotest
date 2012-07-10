"""
Virt-v2v test utility functions.

@copyright: 2008-2012 Red Hat Inc.
"""

import os, re, logging

from autotest.client.virt import ovirt
from autotest.client.virt import libvirt_vm as lvirt


def build_esx_no_verify(params):
    """
    Build esx no verify relationship.
    """
    netrc = params.get('netrc')
    path = os.path.join(os.getenv("HOME"), '.netrc')

    fp = open(path, 'a+')

    if netrc not in fp.read():
        fp.write(netrc + '\n')

    fp.close()

    # The .netrc file must have a permission mask of 0600
    # to be read correctly by virt-v2v
    if oct(os.stat(path).st_mode & 0777) != '0600':
        os.chmod(path, 0600)


class Uri(object):
    """
    This class is used for generating uri.
    """
    def __init__(self, hypervisor):
        if hypervisor is None:
            # kvm is a default hypervisor
            hypervisor = "kvm"
        self.hyper = hypervisor


    def get_uri(self, hostname):
        """
        Uri dispatcher.

        @param hostname: String with host name.
        """
        uri_func =  getattr(self, "_get_%s_uri" % self.hyper)
        self.host = hostname
        return uri_func()


    def _get_kvm_uri(self):
        """
        Return kvm uri.
        """
        uri = "qemu+ssh://"+ self.host + "/system"
        return uri


    def _get_xen_uri(self):
        """
        Return xen uri.
        """
        uri = "xen+ssh://"+ self.host + "/"
        return uri


    def _get_esx_uri(self):
        """
        Return esx uri.
        """
        uri = "esx://"+ self.host + "/?no_verify=1"
        return uri


    # add new hypervisor in here.


class Target(object):
    """
    This class is used for generating command options.
    """
    def __init__(self, target, uri):
        if target is None:
            # libvirt is a default target
            target = "libvirt"
        self.tgt = target
        self.uri = uri


    def get_cmd_options(self, params):
        """
        Target dispatcher.
        """
        opts_func = getattr(self, "_get_%s_options" % self.tgt)
        self.params = params
        return opts_func()


    def _get_libvirt_options(self):
        """
        Return command options.
        """
        options = " -ic %s -os %s -b %s %s " % (self.uri,
                  self.params.get('storage'), self.params.get('network'),
                  self.params.get('vms'))
        return options


    def _get_ovirt_options(self):
        """
        Return command options.
        """
        options = " -ic %s -o rhev -os %s -n %s %s " % (self.uri,
                  self.params.get('storage'), self.params.get('network'),
                  self.params.get('vms'))

        return options


    # add new target in here.


class LinuxVMCheck(object):
    """
    This class handles all basic linux VM check operations.
    """
    # Timeout definition for session login.
    LOGIN_TIMEOUT = 480


    def __init__(self, test, params, env):
        self.vm = None
        self.test = test
        self.env = env
        self.params = params
        self.name = params.get('vms')
        self.target = params.get('target')

        if self.name is None:
            logging.error("vm name not exist")

        # libvirt is a default target
        if self.target == "libvirt" or self.target is None:
            self.vm = lvirt.VM(self.name, self.params, self.test.bindir,
                              self.env.get("address_cache"))
        elif self.target == "ovirt":
            self.vm = ovirt.VMManager(self.name, self.params, self.test.bindir,
                              self.env.get("address_cache"))
        else:
            raise ValueError("Doesn't support %s target now" % self.target)

        if self.vm.is_alive():
            self.vm.shutdown()
            self.vm.start()
        else:
            self.vm.start()


    def get_vm_kernel(self, session=None, nic_index=0, timeout=LOGIN_TIMEOUT):
        """
        Get vm kernel info.
        """
        cmd = "uname -r"
        if not session:
            session = self.vm.wait_for_login(nic_index, timeout)
            kernel_version = session.cmd(cmd)
            session.close()
        else:
            kernel_version = session.cmd(cmd)
        logging.debug("The kernel of VM '%s' is: %s" %
                      (self.vm.name, kernel_version))
        return kernel_version


    def get_vm_os_info(self, session=None, nic_index=0, timeout=LOGIN_TIMEOUT):
        """
        Get vm os info.
        """
        cmd = "cat /etc/issue"
        if not session:
            session = self.vm.wait_for_login(nic_index, timeout)
            output = session.cmd(cmd).split('\n', 1)[0]
            session.close()
        else:
            output = session.cmd(cmd).split('\n', 1)[0]
        logging.debug("The os info is: %s" % output)
        return output


    def get_vm_os_vendor(self, session=None, nic_index=0,
                         timeout=LOGIN_TIMEOUT):
        """
        Get vm os vendor.
        """
        os_info = self.get_vm_os_info(session, nic_index, timeout)
        if re.search('Red Hat', os_info):
            vendor = 'Red Hat'
        elif re.search('Fedora', os_info):
            vendor = 'Fedora Core'
        elif re.search('SUSE', os_info):
            vendor = 'SUSE'
        elif re.search('Ubuntu', os_info):
            vendor = 'Ubuntu'
        elif re.search('Debian', os_info):
            vendor = 'Debian'
        else:
            vendor = 'Unknown'
        logging.debug("The os vendor of VM '%s' is: %s" %
                      (self.vm.name, vendor))
        return vendor


    def get_vm_parted(self, session=None, nic_index=0, timeout=LOGIN_TIMEOUT):
        """
        Get vm parted info.
        """
        cmd = "parted -l"
        if not session:
            session = self.vm.wait_for_login(nic_index, timeout)
            parted_output = session.cmd(cmd)
            session.close()
        else:
            parted_output = session.cmd(cmd)
        logging.debug("The parted output is:\n %s" % parted_output)
        return parted_output


    def get_vm_modprobe_conf(self, session=None, nic_index=0,
                             timeout=LOGIN_TIMEOUT):
        """
        Get /etc/modprobe.conf info.
        """
        cmd = "cat /etc/modprobe.conf"
        if not session:
            session = self.vm.wait_for_login(nic_index, timeout)
            modprobe_output = session.cmd(cmd, ok_status=[0, 1])
            session.close()
        else:
            modprobe_output = session.cmd(cmd, ok_status=[0, 1])
        logging.debug("modprobe conf is:\n %s" % modprobe_output)
        return modprobe_output


    def get_vm_modules(self, session=None, nic_index=0, timeout=LOGIN_TIMEOUT):
        """
        Get vm modules list.
        """
        cmd = "lsmod"
        if not session:
            session = self.vm.wait_for_login(nic_index, timeout)
            modules = session.cmd(cmd)
            session.close()
        else:
            modules = session.cmd(cmd)
        logging.debug("VM modules list is:\n %s" % modules)
        return modules


    def get_vm_pci_list(self, session=None, nic_index=0, timeout=LOGIN_TIMEOUT):
        """
        Get vm pci list.
        """
        cmd = "lspci"
        if not session:
            session = self.vm.wait_for_login(nic_index, timeout)
            lspci_output = session.cmd(cmd)
            session.close()
        else:
            lspci_output = session.cmd(cmd)
        logging.debug("VM pci devices list is:\n %s" % lspci_output)
        return lspci_output


    def get_vm_rc_local(self, session=None, nic_index=0, timeout=LOGIN_TIMEOUT):
        """
        Get vm /etc/rc.local output.
        """
        cmd = "cat /etc/rc.local"
        if not session:
            session = self.vm.wait_for_login(nic_index, timeout)
            rc_output = session.cmd(cmd, ok_status=[0, 1])
            session.close()
        else:
            rc_output = session.cmd(cmd, ok_status=[0, 1])
        return rc_output


    def has_vmware_tools(self, session=None, nic_index=0,
                         timeout=LOGIN_TIMEOUT):
        """
        Check vmware tools.
        """
        rpm_cmd = "rpm -q VMwareTools"
        ls_cmd = "ls /usr/bin/vmware-uninstall-tools.pl"
        if not session:
            session = self.vm.wait_for_login(nic_index, timeout)
            rpm_cmd_status = session.cmd_status(rpm_cmd)
            ls_cmd_status = session.cmd_status(ls_cmd)
            session.close()
        else:
            rpm_cmd_status = session.cmd_status(rpm_cmd)
            ls_cmd_status = session.cmd_status(ls_cmd)

        if (rpm_cmd_status == 0 or ls_cmd_status == 0):
            return True
        else:
            return False


    def get_vm_tty(self, session=None, nic_index=0, timeout=LOGIN_TIMEOUT):
        """
        Get vm tty config.
        """
        cmd = "cat /etc/securetty /etc/inittab /boot/grub/grub.conf " +\
              "/etc/default/grub"
        if not session:
            session = self.vm.wait_for_login(nic_index, timeout)
            tty = session.cmd_output(cmd)
            session.close()
        else:
            tty = session.cmd_output(cmd)
        return tty


    def get_vm_video(self, session=None, nic_index=0, timeout=LOGIN_TIMEOUT):
        """
        Get vm video config.
        """
        cmd = "cat /etc/X11/xorg.conf /etc/X11/XF86Config"
        if not session:
            session = self.vm.wait_for_login(nic_index, timeout)
            xorg_output = session.cmd(cmd, ok_status=[0, 1])
            session.close()
        else:
            xorg_output = session.cmd(cmd, ok_status=[0, 1])
        return xorg_output


class WindowsVMCheck(object):
    """
    This class handles all basic windows VM check operations.
    """
    pass
