"""
Library to perform pre/post test setup for KVM autotest.
"""
import os, logging, time, re, random, commands
from autotest.client.shared import error
from autotest.client import utils
from autotest.client import kvm_control
from autotest.client.virt import virt_utils


class THPError(Exception):
    """
    Base exception for Transparent Hugepage setup.
    """
    pass


class THPNotSupportedError(THPError):
    """
    Thrown when host does not support tansparent hugepages.
    """
    pass


class THPWriteConfigError(THPError):
    """
    Thrown when host does not support tansparent hugepages.
    """
    pass


class THPKhugepagedError(THPError):
    """
    Thrown when khugepaged is not behaving as expected.
    """
    pass


class TransparentHugePageConfig(object):
    def __init__(self, test, params):
        """
        Find paths for transparent hugepages and kugepaged configuration. Also,
        back up original host configuration so it can be restored during
        cleanup.
        """
        self.params = params

        RH_THP_PATH = "/sys/kernel/mm/redhat_transparent_hugepage"
        UPSTREAM_THP_PATH = "/sys/kernel/mm/transparent_hugepage"
        if os.path.isdir(RH_THP_PATH):
            self.thp_path = RH_THP_PATH
        elif os.path.isdir(UPSTREAM_THP_PATH):
            self.thp_path = UPSTREAM_THP_PATH
        else:
            raise THPNotSupportedError("System doesn't support transparent "
                                       "hugepages")

        tmp_list = []
        test_cfg = {}
        test_config = self.params.get("test_config", None)
        if test_config is not None:
            tmp_list = re.split(';', test_config)
        while len(tmp_list) > 0:
            tmp_cfg = tmp_list.pop()
            test_cfg[re.split(":", tmp_cfg)[0]] = re.split(":", tmp_cfg)[1]
        # Save host current config, so we can restore it during cleanup
        # We will only save the writeable part of the config files
        original_config = {}
        # List of files that contain string config values
        self.file_list_str = []
        # List of files that contain integer config values
        self.file_list_num = []
        logging.info("Scanning THP base path and recording base values")
        for f in os.walk(self.thp_path):
            base_dir = f[0]
            if f[2]:
                for name in f[2]:
                    f_dir = os.path.join(base_dir, name)
                    parameter = file(f_dir, 'r').read()
                    logging.debug("Reading path %s: %s", f_dir,
                                  parameter.strip())
                    try:
                        # Verify if the path in question is writable
                        f = open(f_dir, 'w')
                        f.close()
                        if re.findall("\[(.*)\]", parameter):
                            original_config[f_dir] = re.findall("\[(.*)\]",
                                                           parameter)[0]
                            self.file_list_str.append(f_dir)
                        else:
                            original_config[f_dir] = int(parameter)
                            self.file_list_num.append(f_dir)
                    except IOError:
                        pass

        self.test_config = test_cfg
        self.original_config = original_config


    def set_env(self):
        """
        Applies test configuration on the host.
        """
        if self.test_config:
            logging.info("Applying custom THP test configuration")
            for path in self.test_config.keys():
                logging.info("Writing path %s: %s", path,
                             self.test_config[path])
                file(path, 'w').write(self.test_config[path])


    def value_listed(self, value):
        """
        Get a parameters list from a string
        """
        value_list = []
        for i in re.split("\[|\]|\n+|\s+", value):
            if i:
                value_list.append(i)
        return value_list


    def khugepaged_test(self):
        """
        Start, stop and frequency change test for khugepaged.
        """
        def check_status_with_value(action_list, file_name):
            """
            Check the status of khugepaged when set value to specify file.
            """
            for (a, r) in action_list:
                logging.info("Writing path %s: %s, expected khugepage rc: %s ",
                             file_name, a, r)
                try:
                    file_object = open(file_name, "w")
                    file_object.write(a)
                    file_object.close()
                except IOError, error_detail:
                    logging.info("IO Operation on path %s failed: %s",
                                 file_name, error_detail)
                time.sleep(5)
                try:
                    utils.run('pgrep khugepaged', verbose=False)
                    if r != 0:
                        raise THPKhugepagedError("Khugepaged still alive when"
                                                 "transparent huge page is "
                                                 "disabled")
                except error.CmdError:
                    if r == 0:
                        raise THPKhugepagedError("Khugepaged could not be set to"
                                                 "status %s" % a)

        logging.info("Testing khugepaged")
        for file_path in self.file_list_str:
            action_list = []
            if re.findall("enabled", file_path):
                # Start and stop test for khugepaged
                value_list = self.value_listed(open(file_path,"r").read())
                for i in value_list:
                    if re.match("n", i, re.I):
                        action_stop = (i, 256)
                for i in value_list:
                    if re.match("[^n]", i, re.I):
                        action = (i, 0)
                        action_list += [action_stop, action, action_stop]
                action_list += [action]

                check_status_with_value(action_list, file_path)
            else:
                value_list = self.value_listed(open(file_path,"r").read())
                for i in value_list:
                    action = (i, 0)
                    action_list.append(action)
                check_status_with_value(action_list, file_path)

        for file_path in self.file_list_num:
            action_list = []
            file_object = open(file_path, "r")
            value = file_object.read()
            value = int(value)
            file_object.close()
            if value != 0 and value != 1:
                new_value = random.random()
                action_list.append((str(int(value * new_value)),0))
                action_list.append((str(int(value * ( new_value + 1))),0))
            else:
                action_list.append(("0", 0))
                action_list.append(("1", 0))

            check_status_with_value(action_list, file_path)


    def setup(self):
        """
        Configure host for testing. Also, check that khugepaged is working as
        expected.
        """
        self.set_env()
        self.khugepaged_test()


    def cleanup(self):
        """:
        Restore the host's original configuration after test
        """
        logging.info("Restoring host's original THP configuration")
        for path in self.original_config:
            logging.info("Writing path %s: %s", path,
                         self.original_config[path])
            try:
                p_file = open(path, 'w')
                p_file.write(str(self.original_config[path]))
                p_file.close()
            except IOError, error_detail:
                logging.info("IO operation failed on file %s: %s", path,
                             error_detail)


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


class PciAssignable(object):
    """
    Request PCI assignable devices on host. It will check whether to request
    PF (physical Functions) or VF (Virtual Functions).
    """
    def __init__(self, type="vf", driver=None, driver_option=None,
                 names=None, devices_requested=None,
                 host_set_flag=None, kvm_params=None):
        """
        Initialize parameter 'type' which could be:
        vf: Virtual Functions
        pf: Physical Function (actual hardware)
        mixed:  Both includes VFs and PFs

        If pass through Physical NIC cards, we need to specify which devices
        to be assigned, e.g. 'eth1 eth2'.

        If pass through Virtual Functions, we need to specify how many vfs
        are going to be assigned, e.g. passthrough_count = 8 and max_vfs in
        config file.

        @param type: PCI device type.
        @param driver: Kernel module for the PCI assignable device.
        @param driver_option: Module option to specify the maximum number of
                VFs (eg 'max_vfs=7')
        @param names: Physical NIC cards correspondent network interfaces,
                e.g.'eth1 eth2 ...'
        @param devices_requested: Number of devices being requested.
        @param host_set_flag: Flag for if the test should setup host env:
               0: do nothing
               1: do setup env
               2: do cleanup env
               3: setup and cleanup env
        @param kvm_params: a dict for kvm module parameters default value
        """
        self.type = type
        self.driver = driver
        self.driver_option = driver_option
        if names:
            self.name_list = names.split()
        if devices_requested:
            self.devices_requested = int(devices_requested)
        else:
            self.devices_requested = None
        if host_set_flag is not None:
            self.setup = host_set_flag & 1 == 1
            self.cleanup = host_set_flag & 2 == 2
        else:
            self.setup = False
            self.cleanup = False
        self.kvm_params = kvm_params
        self.auai_path = None
        if self.kvm_params is not None:
            for i in self.kvm_params:
                if "allow_unsafe_assigned_interrupts" in i:
                    self.auai_path = i

    def _get_pf_pci_id(self, name, search_str):
        """
        Get the PF PCI ID according to name.

        @param name: Name of the PCI device.
        @param search_str: Search string to be used on lspci.
        """
        cmd = "ethtool -i %s | awk '/bus-info/ {print $2}'" % name
        s, pci_id = commands.getstatusoutput(cmd)
        if not (s or "Cannot get driver information" in pci_id):
            return pci_id[5:]
        cmd = "lspci | awk '/%s/ {print $1}'" % search_str
        pci_ids = [id for id in commands.getoutput(cmd).splitlines()]
        nic_id = int(re.search('[0-9]+', name).group(0))
        if (len(pci_ids) - 1) < nic_id:
            return None
        return pci_ids[nic_id]


    def _release_dev(self, pci_id):
        """
        Release a single PCI device.

        @param pci_id: PCI ID of a given PCI device.
        """
        base_dir = "/sys/bus/pci"
        full_id = virt_utils.get_full_pci_id(pci_id)
        vendor_id = virt_utils.get_vendor_from_pci_id(pci_id)
        drv_path = os.path.join(base_dir, "devices/%s/driver" % full_id)
        if 'pci-stub' in os.readlink(drv_path):
            cmd = "echo '%s' > %s/new_id" % (vendor_id, drv_path)
            if os.system(cmd):
                return False

            stub_path = os.path.join(base_dir, "drivers/pci-stub")
            cmd = "echo '%s' > %s/unbind" % (full_id, stub_path)
            if os.system(cmd):
                return False

            driver = self.dev_drivers[pci_id]
            cmd = "echo '%s' > %s/bind" % (full_id, driver)
            if os.system(cmd):
                return False

        return True


    def get_vf_devs(self):
        """
        Catch all VFs PCI IDs.

        @return: List with all PCI IDs for the Virtual Functions avaliable
        """
        if self.setup:
            if not self.sr_iov_setup():
                return []
        cmd = "lspci | awk '/Virtual Function/ {print $1}'"
        return commands.getoutput(cmd).split()


    def get_pf_devs(self):
        """
        Catch all PFs PCI IDs.

        @return: List with all PCI IDs for the physical hardware requested
        """
        pf_ids = []
        for name in self.name_list:
            pf_id = self._get_pf_pci_id(name, "Ethernet")
            if not pf_id:
                continue
            pf_ids.append(pf_id)
        return pf_ids


    def get_devs(self, count):
        """
        Check out all devices' PCI IDs according to their name.

        @param count: count number of PCI devices needed for pass through
        @return: a list of all devices' PCI IDs
        """
        if self.type == "vf":
            vf_ids = self.get_vf_devs()
        elif self.type == "pf":
            vf_ids = self.get_pf_devs()
        elif self.type == "mixed":
            vf_ids = self.get_vf_devs()
            vf_ids.extend(self.get_pf_devs())
        return vf_ids[0:count]


    def get_vfs_count(self):
        """
        Get VFs count number according to lspci.
        """
        # FIXME: Need to think out a method of identify which
        # 'virtual function' belongs to which physical card considering
        # that if the host has more than one 82576 card. PCI_ID?
        cmd = "lspci | grep 'Virtual Function' | wc -l"
        return int(commands.getoutput(cmd))


    def check_vfs_count(self):
        """
        Check VFs count number according to the parameter driver_options.
        """
        # Network card 82576 has two network interfaces and each can be
        # virtualized up to 7 virtual functions, therefore we multiply
        # two for the value of driver_option 'max_vfs'.
        expected_count = int((re.findall("(\d)", self.driver_option)[0])) * 2
        return (self.get_vfs_count == expected_count)


    def is_binded_to_stub(self, full_id):
        """
        Verify whether the device with full_id is already binded to pci-stub.

        @param full_id: Full ID for the given PCI device
        """
        base_dir = "/sys/bus/pci"
        stub_path = os.path.join(base_dir, "drivers/pci-stub")
        if os.path.exists(os.path.join(stub_path, full_id)):
            return True
        return False


    def sr_iov_setup(self):
        """
        Ensure the PCI device is working in sr_iov mode.

        Check if the PCI hardware device drive is loaded with the appropriate,
        parameters (number of VFs), and if it's not, perform setup.

        @return: True, if the setup was completed successfuly, False otherwise.
        """
        # Check if the host support interrupt remapping
        kvm_re_probe = False
        o = utils.system_output("cat /var/log/dmesg")
        ecap = re.findall("ecap\s+(.\w+)", o)
        if ecap and int(ecap[0], 16) & 8 == 0:
            if self.kvm_params is not None:
                if self.auai_path and self.kvm_params[self.auai_path] == "N":
                    kvm_re_probe = True
            else:
                kvm_re_probe = True
        # Try to re probe kvm module with interrupt remapping support
        if kvm_re_probe:
            kvm_arch = kvm_control.get_kvm_arch()
            utils.system("modprobe -r %s" % kvm_arch)
            utils.system("modprobe -r kvm")
            cmd = "modprobe kvm allow_unsafe_assigned_interrupts=1"
            if self.kvm_params is not None:
                for i in self.kvm_params:
                    if "allow_unsafe_assigned_interrupts" not in i:
                        if self.kvm_params[i] == "Y":
                            params_name = os.path.split(i)[1]
                            cmd += " %s=1" % params_name
            logging.info("Loading kvm with: %s" % cmd)

            try:
                utils.system(cmd)
            except Exception:
                logging.debug("Can not enable the interrupt remapping support")
            utils.system("modprobe %s" % kvm_arch)

        re_probe = False
        s, o = commands.getstatusoutput('lsmod | grep %s' % self.driver)
        if s:
            re_probe = True
        elif not self.check_vfs_count():
            os.system("modprobe -r %s" % self.driver)
            re_probe = True
        else:
            return True

        # Re-probe driver with proper number of VFs
        if re_probe:
            cmd = "modprobe %s %s" % (self.driver, self.driver_option)
            logging.info("Loading the driver '%s' with option '%s'",
                         self.driver, self.driver_option)
            s, o = commands.getstatusoutput(cmd)
            utils.system("/etc/init.d/network restart", ignore_status=True)
            if s:
                return False
            return True

    def sr_iov_cleanup(self):
        """
        Clean up the sriov setup

        Check if the PCI hardware device drive is loaded with the appropriate,
        parameters (none of VFs), and if it's not, perform cleanup.

        @return: True, if the setup was completed successfuly, False otherwise.
        """
        # Check if the host support interrupt remapping
        kvm_re_probe = False
        if self.kvm_params is not None:
            if (self.auai_path and
               open(self.auai_path, "r").read().strip() == "Y"):
                if self.kvm_params and self.kvm_params[self.auai_path] == "N":
                    kvm_re_probe = True
        else:
            kvm_re_probe = True
        # Try to re probe kvm module with interrupt remapping support
        if kvm_re_probe:
            kvm_arch = kvm_control.get_kvm_arch()
            utils.system("modprobe -r %s" % kvm_arch)
            utils.system("modprobe -r kvm")
            cmd = "modprobe kvm"
            if self.kvm_params:
                for i in self.kvm_params:
                    if self.kvm_params[i] == "Y":
                        params_name = os.path.split(i)[1]
                        cmd += " %s=1" % params_name
            logging.info("Loading kvm with: %s" % cmd)

            try:
                utils.system(cmd)
            except Exception:
                logging.debug("Failed to reload kvm")
            utils.system("modprobe %s" % kvm_arch)

        re_probe = False
        s, o = commands.getstatusoutput('lsmod | grep %s' % self.driver)
        if s:
            os.system("modprobe -r %s" % self.driver)
            re_probe = True
        else:
            return True

        # Re-probe driver with proper number of VFs
        if re_probe:
            cmd = "modprobe %s" % self.driver
            logging.info("Loading the driver '%s' without option", self.driver)
            s, o = commands.getstatusoutput(cmd)
            utils.system("/etc/init.d/network restart", ignore_status=True)
            if s:
                return False
            return True
    def request_devs(self):
        """
        Implement setup process: unbind the PCI device and then bind it
        to the pci-stub driver.

        @return: a list of successfully requested devices' PCI IDs.
        """
        base_dir = "/sys/bus/pci"
        stub_path = os.path.join(base_dir, "drivers/pci-stub")

        self.pci_ids = self.get_devs(self.devices_requested)
        logging.debug("The following pci_ids were found: %s", self.pci_ids)
        requested_pci_ids = []
        self.dev_drivers = {}

        # Setup all devices specified for assignment to guest
        for pci_id in self.pci_ids:
            full_id = virt_utils.get_full_pci_id(pci_id)
            if not full_id:
                continue
            drv_path = os.path.join(base_dir, "devices/%s/driver" % full_id)
            dev_prev_driver = os.path.realpath(os.path.join(drv_path,
                                               os.readlink(drv_path)))
            self.dev_drivers[pci_id] = dev_prev_driver

            # Judge whether the device driver has been binded to stub
            if not self.is_binded_to_stub(full_id):
                logging.debug("Binding device %s to stub", full_id)
                vendor_id = virt_utils.get_vendor_from_pci_id(pci_id)
                stub_new_id = os.path.join(stub_path, 'new_id')
                unbind_dev = os.path.join(drv_path, 'unbind')
                stub_bind = os.path.join(stub_path, 'bind')

                info_write_to_files = [(vendor_id, stub_new_id),
                                       (full_id, unbind_dev),
                                       (full_id, stub_bind)]

                for content, file in info_write_to_files:
                    try:
                        utils.open_write_close(file, content)
                    except IOError:
                        logging.debug("Failed to write %s to file %s", content,
                                      file)
                        continue

                if not self.is_binded_to_stub(full_id):
                    logging.error("Binding device %s to stub failed", pci_id)
                    continue
            else:
                logging.debug("Device %s already binded to stub", pci_id)
            requested_pci_ids.append(pci_id)
        self.pci_ids = requested_pci_ids
        return self.pci_ids


    def release_devs(self):
        """
        Release all PCI devices currently assigned to VMs back to the
        virtualization host.
        """
        try:
            for pci_id in self.dev_drivers:
                if not self._release_dev(pci_id):
                    logging.error("Failed to release device %s to host", pci_id)
                else:
                    logging.info("Released device %s successfully", pci_id)
            if self.cleanup:
                logging.info("Clean up host env for PCI assign test")
                self.sr_iov_cleanup()
        except Exception:
            return
