#!/usr/bin/python
"""
Utility classes and functions to handle Virtual Machine creation using qemu.

@copyright: 2008-2009 Red Hat Inc.
"""

import time, socket, os, logging, fcntl, re, commands, shelve, glob
import kvm_utils, kvm_subprocess, kvm_monitor, rss_file_transfer
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils


def get_image_filename(params, root_dir):
    """
    Generate an image path from params and root_dir.

    @param params: Dictionary containing the test parameters.
    @param root_dir: Base directory for relative filenames.

    @note: params should contain:
           image_name -- the name of the image file, without extension
           image_format -- the format of the image (qcow2, raw etc)
    """
    image_name = params.get("image_name", "image")
    image_format = params.get("image_format", "qcow2")
    if params.get("image_raw_device") == "yes":
        return image_name
    image_filename = "%s.%s" % (image_name, image_format)
    image_filename = kvm_utils.get_path(root_dir, image_filename)
    return image_filename


def create_image(params, root_dir):
    """
    Create an image using qemu_image.

    @param params: Dictionary containing the test parameters.
    @param root_dir: Base directory for relative filenames.

    @note: params should contain:
           image_name -- the name of the image file, without extension
           image_format -- the format of the image (qcow2, raw etc)
           image_size -- the requested size of the image (a string
           qemu-img can understand, such as '10G')
    """
    qemu_img_cmd = kvm_utils.get_path(root_dir, params.get("qemu_img_binary",
                                                           "qemu-img"))
    qemu_img_cmd += " create"

    format = params.get("image_format", "qcow2")
    qemu_img_cmd += " -f %s" % format

    image_filename = get_image_filename(params, root_dir)
    qemu_img_cmd += " %s" % image_filename

    size = params.get("image_size", "10G")
    qemu_img_cmd += " %s" % size

    try:
        utils.system(qemu_img_cmd)
    except error.CmdError, e:
        logging.error("Could not create image; qemu-img command failed:\n%s",
                      str(e))
        return None

    if not os.path.exists(image_filename):
        logging.error("Image could not be created for some reason; "
                      "qemu-img command:\n%s" % qemu_img_cmd)
        return None

    logging.info("Image created in %s" % image_filename)
    return image_filename


def remove_image(params, root_dir):
    """
    Remove an image file.

    @param params: A dict
    @param root_dir: Base directory for relative filenames.

    @note: params should contain:
           image_name -- the name of the image file, without extension
           image_format -- the format of the image (qcow2, raw etc)
    """
    image_filename = get_image_filename(params, root_dir)
    logging.debug("Removing image file %s..." % image_filename)
    if os.path.exists(image_filename):
        os.unlink(image_filename)
    else:
        logging.debug("Image file %s not found")


class VM:
    """
    This class handles all basic VM operations.
    """

    def __init__(self, name, params, root_dir, address_cache):
        """
        Initialize the object and set a few attributes.

        @param name: The name of the object
        @param params: A dict containing VM params
                (see method make_qemu_command for a full description)
        @param root_dir: Base directory for relative filenames
        @param address_cache: A dict that maps MAC addresses to IP addresses
        """
        self.process = None
        self.serial_console = None
        self.redirs = {}
        self.vnc_port = 5900
        self.monitors = []
        self.pci_assignable = None
        self.netdev_id = []
        self.uuid = None

        self.name = name
        self.params = params
        self.root_dir = root_dir
        self.address_cache = address_cache

        # Find a unique identifier for this VM
        while True:
            self.instance = (time.strftime("%Y%m%d-%H%M%S-") +
                             kvm_utils.generate_random_string(4))
            if not glob.glob("/tmp/*%s" % self.instance):
                break


    def clone(self, name=None, params=None, root_dir=None, address_cache=None):
        """
        Return a clone of the VM object with optionally modified parameters.
        The clone is initially not alive and needs to be started using create().
        Any parameters not passed to this function are copied from the source
        VM.

        @param name: Optional new VM name
        @param params: Optional new VM creation parameters
        @param root_dir: Optional new base directory for relative filenames
        @param address_cache: A dict that maps MAC addresses to IP addresses
        """
        if name is None:
            name = self.name
        if params is None:
            params = self.params.copy()
        if root_dir is None:
            root_dir = self.root_dir
        if address_cache is None:
            address_cache = self.address_cache
        return VM(name, params, root_dir, address_cache)


    def make_qemu_command(self, name=None, params=None, root_dir=None):
        """
        Generate a qemu command line. All parameters are optional. If a
        parameter is not supplied, the corresponding value stored in the
        class attributes is used.

        @param name: The name of the object
        @param params: A dict containing VM params
        @param root_dir: Base directory for relative filenames

        @note: The params dict should contain:
               mem -- memory size in MBs
               cdrom -- ISO filename to use with the qemu -cdrom parameter
               extra_params -- a string to append to the qemu command
               shell_port -- port of the remote shell daemon on the guest
               (SSH, Telnet or the home-made Remote Shell Server)
               shell_client -- client program to use for connecting to the
               remote shell daemon on the guest (ssh, telnet or nc)
               x11_display -- if specified, the DISPLAY environment variable
               will be be set to this value for the qemu process (useful for
               SDL rendering)
               images -- a list of image object names, separated by spaces
               nics -- a list of NIC object names, separated by spaces

               For each image in images:
               drive_format -- string to pass as 'if' parameter for this
               image (e.g. ide, scsi)
               image_snapshot -- if yes, pass 'snapshot=on' to qemu for
               this image
               image_boot -- if yes, pass 'boot=on' to qemu for this image
               In addition, all parameters required by get_image_filename.

               For each NIC in nics:
               nic_model -- string to pass as 'model' parameter for this
               NIC (e.g. e1000)
        """
        # Helper function for command line option wrappers
        def has_option(help, option):
            return bool(re.search(r"^-%s(\s|$)" % option, help, re.MULTILINE))

        # Wrappers for all supported qemu command line parameters.
        # This is meant to allow support for multiple qemu versions.
        # Each of these functions receives the output of 'qemu -help' as a
        # parameter, and should add the requested command line option
        # accordingly.

        def add_name(help, name):
            return " -name '%s'" % name

        def add_human_monitor(help, filename):
            return " -monitor unix:'%s',server,nowait" % filename

        def add_qmp_monitor(help, filename):
            return " -qmp unix:'%s',server,nowait" % filename

        def add_serial(help, filename):
            return " -serial unix:'%s',server,nowait" % filename

        def add_mem(help, mem):
            return " -m %s" % mem

        def add_smp(help, smp):
            return " -smp %s" % smp

        def add_cdrom(help, filename, index=None):
            if has_option(help, "drive"):
                cmd = " -drive file='%s',media=cdrom" % filename
                if index is not None: cmd += ",index=%s" % index
                return cmd
            else:
                return " -cdrom '%s'" % filename

        def add_drive(help, filename, index=None, format=None, cache=None,
                      werror=None, serial=None, snapshot=False, boot=False):
            cmd = " -drive file='%s'" % filename
            if index is not None: cmd += ",index=%s" % index
            if format: cmd += ",if=%s" % format
            if cache: cmd += ",cache=%s" % cache
            if werror: cmd += ",werror=%s" % werror
            if serial: cmd += ",serial='%s'" % serial
            if snapshot: cmd += ",snapshot=on"
            if boot: cmd += ",boot=on"
            return cmd

        def add_nic(help, vlan, model=None, mac=None, netdev_id=None,
                    nic_extra_params=None):
            if has_option(help, "netdev"):
                netdev_vlan_str = ",netdev=%s" % netdev_id
            else:
                netdev_vlan_str = ",vlan=%d" % vlan
            if has_option(help, "device"):
                if not model:
                    model = "rtl8139"
                elif model == "virtio":
                    model = "virtio-net-pci"
                cmd = " -device %s" % model + netdev_vlan_str
                if mac:
                    cmd += ",mac='%s'" % mac
                if nic_extra_params:
                    cmd += ",%s" % nic_extra_params
            else:
                cmd = " -net nic" + netdev_vlan_str
                if model:
                    cmd += ",model=%s" % model
                if mac:
                    cmd += ",macaddr='%s'" % mac
            return cmd

        def add_net(help, vlan, mode, ifname=None, script=None,
                    downscript=None, tftp=None, bootfile=None, hostfwd=[],
                    netdev_id=None, netdev_extra_params=None):
            if has_option(help, "netdev"):
                cmd = " -netdev %s,id=%s" % (mode, netdev_id)
                if netdev_extra_params:
                    cmd += ",%s" % netdev_extra_params
            else:
                cmd = " -net %s,vlan=%d" % (mode, vlan)
            if mode == "tap":
                if ifname: cmd += ",ifname='%s'" % ifname
                if script: cmd += ",script='%s'" % script
                cmd += ",downscript='%s'" % (downscript or "no")
            elif mode == "user":
                if tftp and "[,tftp=" in help:
                    cmd += ",tftp='%s'" % tftp
                if bootfile and "[,bootfile=" in help:
                    cmd += ",bootfile='%s'" % bootfile
                if "[,hostfwd=" in help:
                    for host_port, guest_port in hostfwd:
                        cmd += ",hostfwd=tcp::%s-:%s" % (host_port, guest_port)
            return cmd

        def add_floppy(help, filename):
            return " -fda '%s'" % filename

        def add_tftp(help, filename):
            # If the new syntax is supported, don't add -tftp
            if "[,tftp=" in help:
                return ""
            else:
                return " -tftp '%s'" % filename

        def add_bootp(help, filename):
            # If the new syntax is supported, don't add -bootp
            if "[,bootfile=" in help:
                return ""
            else:
                return " -bootp '%s'" % filename

        def add_tcp_redir(help, host_port, guest_port):
            # If the new syntax is supported, don't add -redir
            if "[,hostfwd=" in help:
                return ""
            else:
                return " -redir tcp:%s::%s" % (host_port, guest_port)

        def add_vnc(help, vnc_port):
            return " -vnc :%d" % (vnc_port - 5900)

        def add_sdl(help):
            if has_option(help, "sdl"):
                return " -sdl"
            else:
                return ""

        def add_nographic(help):
            return " -nographic"

        def add_uuid(help, uuid):
            return " -uuid '%s'" % uuid

        def add_pcidevice(help, host):
            return " -pcidevice host='%s'" % host

        def add_kernel(help, filename):
            return " -kernel '%s'" % filename

        def add_initrd(help, filename):
            return " -initrd '%s'" % filename

        def add_kernel_cmdline(help, cmdline):
            return " -append %s" % cmdline

        def add_testdev(help, filename):
            return (" -chardev file,id=testlog,path=%s"
                    " -device testdev,chardev=testlog" % filename)

        def add_no_hpet(help):
            if has_option(help, "no-hpet"):
                return " -no-hpet"
            else:
                return ""

        # End of command line option wrappers

        if name is None: name = self.name
        if params is None: params = self.params
        if root_dir is None: root_dir = self.root_dir

        qemu_binary = kvm_utils.get_path(root_dir, params.get("qemu_binary",
                                                              "qemu"))
        # Get the output of 'qemu -help' (log a message in case this call never
        # returns or causes some other kind of trouble)
        logging.debug("Getting output of 'qemu -help'")
        help = commands.getoutput("%s -help" % qemu_binary)

        # Start constructing the qemu command
        qemu_cmd = ""
        # Set the X11 display parameter if requested
        if params.get("x11_display"):
            qemu_cmd += "DISPLAY=%s " % params.get("x11_display")
        # Add the qemu binary
        qemu_cmd += qemu_binary
        # Add the VM's name
        qemu_cmd += add_name(help, name)
        # Add monitors
        for monitor_name in kvm_utils.get_sub_dict_names(params, "monitors"):
            monitor_params = kvm_utils.get_sub_dict(params, monitor_name)
            monitor_filename = self.get_monitor_filename(monitor_name)
            if monitor_params.get("monitor_type") == "qmp":
                qemu_cmd += add_qmp_monitor(help, monitor_filename)
            else:
                qemu_cmd += add_human_monitor(help, monitor_filename)

        # Add serial console redirection
        qemu_cmd += add_serial(help, self.get_serial_console_filename())

        for image_name in kvm_utils.get_sub_dict_names(params, "images"):
            image_params = kvm_utils.get_sub_dict(params, image_name)
            if image_params.get("boot_drive") == "no":
                continue
            qemu_cmd += add_drive(help,
                                  get_image_filename(image_params, root_dir),
                                  image_params.get("drive_index"),
                                  image_params.get("drive_format"),
                                  image_params.get("drive_cache"),
                                  image_params.get("drive_werror"),
                                  image_params.get("drive_serial"),
                                  image_params.get("image_snapshot") == "yes",
                                  image_params.get("image_boot") == "yes")

        redirs = []
        for redir_name in kvm_utils.get_sub_dict_names(params, "redirs"):
            redir_params = kvm_utils.get_sub_dict(params, redir_name)
            guest_port = int(redir_params.get("guest_port"))
            host_port = self.redirs.get(guest_port)
            redirs += [(host_port, guest_port)]

        vlan = 0
        for nic_name in kvm_utils.get_sub_dict_names(params, "nics"):
            nic_params = kvm_utils.get_sub_dict(params, nic_name)
            # Handle the '-net nic' part
            mac = self.get_mac_address(vlan)
            qemu_cmd += add_nic(help, vlan, nic_params.get("nic_model"), mac,
                                self.netdev_id[vlan],
                                nic_params.get("nic_extra_params"))
            # Handle the '-net tap' or '-net user' part
            script = nic_params.get("nic_script")
            downscript = nic_params.get("nic_downscript")
            tftp = nic_params.get("tftp")
            if script:
                script = kvm_utils.get_path(root_dir, script)
            if downscript:
                downscript = kvm_utils.get_path(root_dir, downscript)
            if tftp:
                tftp = kvm_utils.get_path(root_dir, tftp)
            qemu_cmd += add_net(help, vlan, nic_params.get("nic_mode", "user"),
                                self.get_ifname(vlan),
                                script, downscript, tftp,
                                nic_params.get("bootp"), redirs,
                                self.netdev_id[vlan],
                                nic_params.get("netdev_extra_params"))
            # Proceed to next NIC
            vlan += 1

        mem = params.get("mem")
        if mem:
            qemu_cmd += add_mem(help, mem)

        smp = params.get("smp")
        if smp:
            qemu_cmd += add_smp(help, smp)

        cdroms = kvm_utils.get_sub_dict_names(params, "cdroms")
        for cdrom in cdroms:
            cdrom_params = kvm_utils.get_sub_dict(params, cdrom)
            iso = cdrom_params.get("cdrom")
            if iso:
                qemu_cmd += add_cdrom(help, kvm_utils.get_path(root_dir, iso),
                                      cdrom_params.get("drive_index"))

        # We may want to add {floppy_otps} parameter for -fda
        # {fat:floppy:}/path/. However vvfat is not usually recommended.
        floppy = params.get("floppy")
        if floppy:
            floppy = kvm_utils.get_path(root_dir, floppy)
            qemu_cmd += add_floppy(help, floppy)

        tftp = params.get("tftp")
        if tftp:
            tftp = kvm_utils.get_path(root_dir, tftp)
            qemu_cmd += add_tftp(help, tftp)

        bootp = params.get("bootp")
        if bootp:
            qemu_cmd += add_bootp(help, bootp)

        kernel = params.get("kernel")
        if kernel:
            kernel = kvm_utils.get_path(root_dir, kernel)
            qemu_cmd += add_kernel(help, kernel)

        kernel_cmdline = params.get("kernel_cmdline")
        if kernel_cmdline:
            qemu_cmd += add_kernel_cmdline(help, kernel_cmdline)

        initrd = params.get("initrd")
        if initrd:
            initrd = kvm_utils.get_path(root_dir, initrd)
            qemu_cmd += add_initrd(help, initrd)

        for host_port, guest_port in redirs:
            qemu_cmd += add_tcp_redir(help, host_port, guest_port)

        if params.get("display") == "vnc":
            qemu_cmd += add_vnc(help, self.vnc_port)
        elif params.get("display") == "sdl":
            qemu_cmd += add_sdl(help)
        elif params.get("display") == "nographic":
            qemu_cmd += add_nographic(help)

        if params.get("uuid") == "random":
            qemu_cmd += add_uuid(help, self.uuid)
        elif params.get("uuid"):
            qemu_cmd += add_uuid(help, params.get("uuid"))

        if params.get("testdev") == "yes":
            qemu_cmd += add_testdev(help, self.get_testlog_filename())

        if params.get("disable_hpet") == "yes":
            qemu_cmd += add_no_hpet(help)

        # If the PCI assignment step went OK, add each one of the PCI assigned
        # devices to the qemu command line.
        if self.pci_assignable:
            for pci_id in self.pa_pci_ids:
                qemu_cmd += add_pcidevice(help, pci_id)

        extra_params = params.get("extra_params")
        if extra_params:
            qemu_cmd += " %s" % extra_params

        return qemu_cmd


    def create(self, name=None, params=None, root_dir=None, timeout=5.0,
               migration_mode=None, mac_source=None):
        """
        Start the VM by running a qemu command.
        All parameters are optional. If name, params or root_dir are not
        supplied, the respective values stored as class attributes are used.

        @param name: The name of the object
        @param params: A dict containing VM params
        @param root_dir: Base directory for relative filenames
        @param migration_mode: If supplied, start VM for incoming migration
                using this protocol (either 'tcp', 'unix' or 'exec')
        @param migration_exec_cmd: Command to embed in '-incoming "exec: ..."'
                (e.g. 'gzip -c -d filename') if migration_mode is 'exec'
        @param mac_source: A VM object from which to copy MAC addresses. If not
                specified, new addresses will be generated.
        """
        self.destroy()

        if name is not None:
            self.name = name
        if params is not None:
            self.params = params
        if root_dir is not None:
            self.root_dir = root_dir
        name = self.name
        params = self.params
        root_dir = self.root_dir

        # Verify the md5sum of the ISO image
        iso = params.get("cdrom")
        if iso:
            iso = kvm_utils.get_path(root_dir, iso)
            if not os.path.exists(iso):
                logging.error("ISO file not found: %s" % iso)
                return False
            compare = False
            if params.get("md5sum_1m"):
                logging.debug("Comparing expected MD5 sum with MD5 sum of "
                              "first MB of ISO file...")
                actual_hash = utils.hash_file(iso, 1048576, method="md5")
                expected_hash = params.get("md5sum_1m")
                compare = True
            elif params.get("md5sum"):
                logging.debug("Comparing expected MD5 sum with MD5 sum of ISO "
                              "file...")
                actual_hash = utils.hash_file(iso, method="md5")
                expected_hash = params.get("md5sum")
                compare = True
            elif params.get("sha1sum"):
                logging.debug("Comparing expected SHA1 sum with SHA1 sum of "
                              "ISO file...")
                actual_hash = utils.hash_file(iso, method="sha1")
                expected_hash = params.get("sha1sum")
                compare = True
            if compare:
                if actual_hash == expected_hash:
                    logging.debug("Hashes match")
                else:
                    logging.error("Actual hash differs from expected one")
                    return False

        # Make sure the following code is not executed by more than one thread
        # at the same time
        lockfile = open("/tmp/kvm-autotest-vm-create.lock", "w+")
        fcntl.lockf(lockfile, fcntl.LOCK_EX)

        try:
            # Handle port redirections
            redir_names = kvm_utils.get_sub_dict_names(params, "redirs")
            host_ports = kvm_utils.find_free_ports(5000, 6000, len(redir_names))
            self.redirs = {}
            for i in range(len(redir_names)):
                redir_params = kvm_utils.get_sub_dict(params, redir_names[i])
                guest_port = int(redir_params.get("guest_port"))
                self.redirs[guest_port] = host_ports[i]

            # Generate netdev IDs for all NICs
            self.netdev_id = []
            for nic in kvm_utils.get_sub_dict_names(params, "nics"):
                self.netdev_id.append(kvm_utils.generate_random_id())

            # Find available VNC port, if needed
            if params.get("display") == "vnc":
                self.vnc_port = kvm_utils.find_free_port(5900, 6100)

            # Find random UUID if specified 'uuid = random' in config file
            if params.get("uuid") == "random":
                f = open("/proc/sys/kernel/random/uuid")
                self.uuid = f.read().strip()
                f.close()

            # Generate or copy MAC addresses for all NICs
            num_nics = len(kvm_utils.get_sub_dict_names(params, "nics"))
            for vlan in range(num_nics):
                nic_name = kvm_utils.get_sub_dict_names(params, "nics")[vlan]
                nic_params = kvm_utils.get_sub_dict(params, nic_name)
                if nic_params.get("nic_mac", None):
                    mac = nic_params.get("nic_mac")
                    kvm_utils.set_mac_address(self.instance, vlan, mac)
                else:
                    mac = mac_source and mac_source.get_mac_address(vlan)
                    if mac:
                        kvm_utils.set_mac_address(self.instance, vlan, mac)
                    else:
                        kvm_utils.generate_mac_address(self.instance, vlan)

            # Assign a PCI assignable device
            self.pci_assignable = None
            pa_type = params.get("pci_assignable")
            if pa_type in ["vf", "pf", "mixed"]:
                pa_devices_requested = params.get("devices_requested")

                # Virtual Functions (VF) assignable devices
                if pa_type == "vf":
                    self.pci_assignable = kvm_utils.PciAssignable(
                        type=pa_type,
                        driver=params.get("driver"),
                        driver_option=params.get("driver_option"),
                        devices_requested=pa_devices_requested)
                # Physical NIC (PF) assignable devices
                elif pa_type == "pf":
                    self.pci_assignable = kvm_utils.PciAssignable(
                        type=pa_type,
                        names=params.get("device_names"),
                        devices_requested=pa_devices_requested)
                # Working with both VF and PF
                elif pa_type == "mixed":
                    self.pci_assignable = kvm_utils.PciAssignable(
                        type=pa_type,
                        driver=params.get("driver"),
                        driver_option=params.get("driver_option"),
                        names=params.get("device_names"),
                        devices_requested=pa_devices_requested)

                self.pa_pci_ids = self.pci_assignable.request_devs()

                if self.pa_pci_ids:
                    logging.debug("Successfuly assigned devices: %s",
                                  self.pa_pci_ids)
                else:
                    logging.error("No PCI assignable devices were assigned "
                                  "and 'pci_assignable' is defined to %s "
                                  "on your config file. Aborting VM creation.",
                                  pa_type)
                    return False

            elif pa_type and pa_type != "no":
                logging.warn("Unsupported pci_assignable type: %s", pa_type)

            # Make qemu command
            qemu_command = self.make_qemu_command()

            # Add migration parameters if required
            if migration_mode == "tcp":
                self.migration_port = kvm_utils.find_free_port(5200, 6000)
                qemu_command += " -incoming tcp:0:%d" % self.migration_port
            elif migration_mode == "unix":
                self.migration_file = "/tmp/migration-unix-%s" % self.instance
                qemu_command += " -incoming unix:%s" % self.migration_file
            elif migration_mode == "exec":
                self.migration_port = kvm_utils.find_free_port(5200, 6000)
                qemu_command += (' -incoming "exec:nc -l %s"' %
                                 self.migration_port)

            logging.debug("Running qemu command:\n%s", qemu_command)
            self.process = kvm_subprocess.run_bg(qemu_command, None,
                                                 logging.debug, "(qemu) ")

            # Make sure the process was started successfully
            if not self.process.is_alive():
                logging.error("VM could not be created; "
                              "qemu command failed:\n%s" % qemu_command)
                logging.error("Status: %s" % self.process.get_status())
                logging.error("Output:" + kvm_utils.format_str_for_message(
                    self.process.get_output()))
                self.destroy()
                return False

            # Establish monitor connections
            self.monitors = []
            for monitor_name in kvm_utils.get_sub_dict_names(params,
                                                             "monitors"):
                monitor_params = kvm_utils.get_sub_dict(params, monitor_name)
                # Wait for monitor connection to succeed
                end_time = time.time() + timeout
                while time.time() < end_time:
                    try:
                        if monitor_params.get("monitor_type") == "qmp":
                            # Add a QMP monitor
                            monitor = kvm_monitor.QMPMonitor(
                                monitor_name,
                                self.get_monitor_filename(monitor_name))
                        else:
                            # Add a "human" monitor
                            monitor = kvm_monitor.HumanMonitor(
                                monitor_name,
                                self.get_monitor_filename(monitor_name))
                    except kvm_monitor.MonitorError, e:
                        logging.warn(e)
                    else:
                        if monitor.is_responsive():
                            break
                    time.sleep(1)
                else:
                    logging.error("Could not connect to monitor '%s'" %
                                  monitor_name)
                    self.destroy()
                    return False
                # Add this monitor to the list
                self.monitors += [monitor]

            # Get the output so far, to see if we have any problems with
            # KVM modules or with hugepage setup.
            output = self.process.get_output()

            if re.search("Could not initialize KVM", output, re.IGNORECASE):
                logging.error("Could not initialize KVM; "
                              "qemu command:\n%s" % qemu_command)
                logging.error("Output:" + kvm_utils.format_str_for_message(
                              self.process.get_output()))
                self.destroy()
                return False

            if "alloc_mem_area" in output:
                logging.error("Could not allocate hugepage memory; "
                              "qemu command:\n%s" % qemu_command)
                logging.error("Output:" + kvm_utils.format_str_for_message(
                              self.process.get_output()))
                self.destroy()
                return False

            logging.debug("VM appears to be alive with PID %s", self.get_pid())

            # Establish a session with the serial console -- requires a version
            # of netcat that supports -U
            self.serial_console = kvm_subprocess.ShellSession(
                "nc -U %s" % self.get_serial_console_filename(),
                auto_close=False,
                output_func=kvm_utils.log_line,
                output_params=("serial-%s.log" % name,))

            return True

        finally:
            fcntl.lockf(lockfile, fcntl.LOCK_UN)
            lockfile.close()


    def destroy(self, gracefully=True):
        """
        Destroy the VM.

        If gracefully is True, first attempt to shutdown the VM with a shell
        command.  Then, attempt to destroy the VM via the monitor with a 'quit'
        command.  If that fails, send SIGKILL to the qemu process.

        @param gracefully: Whether an attempt will be made to end the VM
                using a shell command before trying to end the qemu process
                with a 'quit' or a kill signal.
        """
        try:
            # Is it already dead?
            if self.is_dead():
                logging.debug("VM is already down")
                return

            logging.debug("Destroying VM with PID %s...", self.get_pid())

            if gracefully and self.params.get("shutdown_command"):
                # Try to destroy with shell command
                logging.debug("Trying to shutdown VM with shell command...")
                session = self.remote_login()
                if session:
                    try:
                        # Send the shutdown command
                        session.sendline(self.params.get("shutdown_command"))
                        logging.debug("Shutdown command sent; waiting for VM "
                                      "to go down...")
                        if kvm_utils.wait_for(self.is_dead, 60, 1, 1):
                            logging.debug("VM is down, freeing mac address.")
                            return
                    finally:
                        session.close()

            if self.monitor:
                # Try to destroy with a monitor command
                logging.debug("Trying to kill VM with monitor command...")
                try:
                    self.monitor.quit()
                except kvm_monitor.MonitorError, e:
                    logging.warn(e)
                else:
                    # Wait for the VM to be really dead
                    if kvm_utils.wait_for(self.is_dead, 5, 0.5, 0.5):
                        logging.debug("VM is down")
                        return

            # If the VM isn't dead yet...
            logging.debug("Cannot quit normally; sending a kill to close the "
                          "deal...")
            kvm_utils.kill_process_tree(self.process.get_pid(), 9)
            # Wait for the VM to be really dead
            if kvm_utils.wait_for(self.is_dead, 5, 0.5, 0.5):
                logging.debug("VM is down")
                return

            logging.error("Process %s is a zombie!" % self.process.get_pid())

        finally:
            self.monitors = []
            if self.pci_assignable:
                self.pci_assignable.release_devs()
            if self.process:
                self.process.close()
            if self.serial_console:
                self.serial_console.close()
            for f in ([self.get_testlog_filename(),
                       self.get_serial_console_filename()] +
                      self.get_monitor_filenames()):
                try:
                    os.unlink(f)
                except OSError:
                    pass
            if hasattr(self, "migration_file"):
                try:
                    os.unlink(self.migration_file)
                except OSError:
                    pass
            num_nics = len(kvm_utils.get_sub_dict_names(self.params, "nics"))
            for vlan in range(num_nics):
                self.free_mac_address(vlan)


    @property
    def monitor(self):
        """
        Return the main monitor object, selected by the parameter main_monitor.
        If main_monitor isn't defined, return the first monitor.
        If no monitors exist, or if main_monitor refers to a nonexistent
        monitor, return None.
        """
        for m in self.monitors:
            if m.name == self.params.get("main_monitor"):
                return m
        if self.monitors and not self.params.get("main_monitor"):
            return self.monitors[0]


    def is_alive(self):
        """
        Return True if the VM is alive and its monitor is responsive.
        """
        # Check if the process is running
        if self.is_dead():
            return False
        # Try sending a monitor command
        return bool(self.monitor) and self.monitor.is_responsive()


    def is_dead(self):
        """
        Return True if the qemu process is dead.
        """
        return not self.process or not self.process.is_alive()


    def get_params(self):
        """
        Return the VM's params dict. Most modified params take effect only
        upon VM.create().
        """
        return self.params


    def get_monitor_filename(self, monitor_name):
        """
        Return the filename corresponding to a given monitor name.
        """
        return "/tmp/monitor-%s-%s" % (monitor_name, self.instance)


    def get_monitor_filenames(self):
        """
        Return a list of all monitor filenames (as specified in the VM's
        params).
        """
        return [self.get_monitor_filename(m) for m in
                kvm_utils.get_sub_dict_names(self.params, "monitors")]


    def get_serial_console_filename(self):
        """
        Return the serial console filename.
        """
        return "/tmp/serial-%s" % self.instance


    def get_testlog_filename(self):
        """
        Return the testlog filename.
        """
        return "/tmp/testlog-%s" % self.instance


    def get_address(self, index=0):
        """
        Return the address of a NIC of the guest, in host space.

        If port redirection is used, return 'localhost' (the NIC has no IP
        address of its own).  Otherwise return the NIC's IP address.

        @param index: Index of the NIC whose address is requested.
        """
        nics = kvm_utils.get_sub_dict_names(self.params, "nics")
        nic_name = nics[index]
        nic_params = kvm_utils.get_sub_dict(self.params, nic_name)
        if nic_params.get("nic_mode") == "tap":
            mac = self.get_mac_address(index)
            if not mac:
                logging.debug("MAC address unavailable")
                return None
            mac = mac.lower()
            # Get the IP address from the cache
            ip = self.address_cache.get(mac)
            if not ip:
                logging.debug("Could not find IP address for MAC address: %s" %
                              mac)
                return None
            # Make sure the IP address is assigned to this guest
            macs = [self.get_mac_address(i) for i in range(len(nics))]
            if not kvm_utils.verify_ip_address_ownership(ip, macs):
                logging.debug("Could not verify MAC-IP address mapping: "
                              "%s ---> %s" % (mac, ip))
                return None
            return ip
        else:
            return "localhost"


    def get_port(self, port, nic_index=0):
        """
        Return the port in host space corresponding to port in guest space.

        @param port: Port number in host space.
        @param nic_index: Index of the NIC.
        @return: If port redirection is used, return the host port redirected
                to guest port port. Otherwise return port.
        """
        nic_name = kvm_utils.get_sub_dict_names(self.params, "nics")[nic_index]
        nic_params = kvm_utils.get_sub_dict(self.params, nic_name)
        if nic_params.get("nic_mode") == "tap":
            return port
        else:
            if not self.redirs.has_key(port):
                logging.warn("Warning: guest port %s requested but not "
                             "redirected" % port)
            return self.redirs.get(port)


    def get_ifname(self, nic_index=0):
        """
        Return the ifname of a tap device associated with a NIC.

        @param nic_index: Index of the NIC
        """
        nics = kvm_utils.get_sub_dict_names(self.params, "nics")
        nic_name = nics[nic_index]
        nic_params = kvm_utils.get_sub_dict(self.params, nic_name)
        if nic_params.get("nic_ifname"):
            return nic_params.get("nic_ifname")
        else:
            return "t%d-%s" % (nic_index, self.instance[-11:])


    def get_mac_address(self, nic_index=0):
        """
        Return the MAC address of a NIC.

        @param nic_index: Index of the NIC
        """
        return kvm_utils.get_mac_address(self.instance, nic_index)


    def free_mac_address(self, nic_index=0):
        """
        Free a NIC's MAC address.

        @param nic_index: Index of the NIC
        """
        kvm_utils.free_mac_address(self.instance, nic_index)


    def get_pid(self):
        """
        Return the VM's PID.  If the VM is dead return None.

        @note: This works under the assumption that self.process.get_pid()
        returns the PID of the parent shell process.
        """
        try:
            children = commands.getoutput("ps --ppid=%d -o pid=" %
                                          self.process.get_pid()).split()
            return int(children[0])
        except (TypeError, IndexError, ValueError):
            return None


    def get_shell_pid(self):
        """
        Return the PID of the parent shell process.

        @note: This works under the assumption that self.process.get_pid()
        returns the PID of the parent shell process.
        """
        return self.process.get_pid()


    def get_shared_meminfo(self):
        """
        Returns the VM's shared memory information.

        @return: Shared memory used by VM (MB)
        """
        if self.is_dead():
            logging.error("Could not get shared memory info from dead VM.")
            return None

        filename = "/proc/%d/statm" % self.get_pid()
        shm = int(open(filename).read().split()[2])
        # statm stores informations in pages, translate it to MB
        return shm * 4.0 / 1024


    def remote_login(self, nic_index=0, timeout=10):
        """
        Log into the guest via SSH/Telnet/Netcat.
        If timeout expires while waiting for output from the guest (e.g. a
        password prompt or a shell prompt) -- fail.

        @param nic_index: The index of the NIC to connect to.
        @param timeout: Time (seconds) before giving up logging into the
                guest.
        @return: ShellSession object on success and None on failure.
        """
        username = self.params.get("username", "")
        password = self.params.get("password", "")
        prompt = self.params.get("shell_prompt", "[\#\$]")
        linesep = eval("'%s'" % self.params.get("shell_linesep", r"\n"))
        client = self.params.get("shell_client")
        address = self.get_address(nic_index)
        port = self.get_port(int(self.params.get("shell_port")))
        log_filename = ("session-%s-%s.log" %
                        (self.name, kvm_utils.generate_random_string(4)))

        if not address or not port:
            logging.debug("IP address or port unavailable")
            return None

        session = kvm_utils.remote_login(client, address, port, username,
                                         password, prompt, linesep,
                                         log_filename, timeout)

        if session:
            session.set_status_test_command(self.params.get("status_test_"
                                                            "command", ""))
        return session


    def copy_files_to(self, local_path, remote_path, nic_index=0, timeout=600):
        """
        Transfer files to the remote host(guest).

        @param local_path: Host path
        @param remote_path: Guest path
        @param nic_index: The index of the NIC to connect to.
        @param timeout: Time (seconds) before giving up on doing the remote
                copy.
        """
        username = self.params.get("username", "")
        password = self.params.get("password", "")
        client = self.params.get("file_transfer_client")
        address = self.get_address(nic_index)
        port = self.get_port(int(self.params.get("file_transfer_port")))

        log_filename = ("transfer-%s-to-%s-%s.log" %
                        (self.name, address,
                        kvm_utils.generate_random_string(4)))
        return kvm_utils.copy_files_to(address, client, username, password,
                                       port, local_path, remote_path,
                                       log_filename, timeout)


    def copy_files_from(self, remote_path, local_path, nic_index=0, timeout=600):
        """
        Transfer files from the guest.

        @param local_path: Guest path
        @param remote_path: Host path
        @param nic_index: The index of the NIC to connect to.
        @param timeout: Time (seconds) before giving up on doing the remote
                copy.
        """
        username = self.params.get("username", "")
        password = self.params.get("password", "")
        client = self.params.get("file_transfer_client")
        address = self.get_address(nic_index)
        port = self.get_port(int(self.params.get("file_transfer_port")))

        log_filename = ("transfer-%s-from-%s-%s.log" %
                        (self.name, address,
                        kvm_utils.generate_random_string(4)))
        return kvm_utils.copy_files_from(address, client, username, password,
                        port, local_path, remote_path, log_filename, timeout)


    def serial_login(self, timeout=10):
        """
        Log into the guest via the serial console.
        If timeout expires while waiting for output from the guest (e.g. a
        password prompt or a shell prompt) -- fail.

        @param timeout: Time (seconds) before giving up logging into the guest.
        @return: ShellSession object on success and None on failure.
        """
        username = self.params.get("username", "")
        password = self.params.get("password", "")
        prompt = self.params.get("shell_prompt", "[\#\$]")
        linesep = eval("'%s'" % self.params.get("shell_linesep", r"\n"))
        status_test_command = self.params.get("status_test_command", "")

        if self.serial_console:
            self.serial_console.set_linesep(linesep)
            self.serial_console.set_status_test_command(status_test_command)
        else:
            return None

        # Make sure we get a login prompt
        self.serial_console.sendline()

        if kvm_utils._remote_login(self.serial_console, username, password,
                                   prompt, timeout):
            return self.serial_console


    def send_key(self, keystr):
        """
        Send a key event to the VM.

        @param: keystr: A key event string (e.g. "ctrl-alt-delete")
        """
        # For compatibility with versions of QEMU that do not recognize all
        # key names: replace keyname with the hex value from the dict, which
        # QEMU will definitely accept
        dict = {"comma": "0x33",
                "dot":   "0x34",
                "slash": "0x35"}
        for key, value in dict.items():
            keystr = keystr.replace(key, value)
        self.monitor.sendkey(keystr)
        time.sleep(0.2)


    def send_string(self, str):
        """
        Send a string to the VM.

        @param str: String, that must consist of alphanumeric characters only.
                Capital letters are allowed.
        """
        for char in str:
            if char.isupper():
                self.send_key("shift-%s" % char.lower())
            else:
                self.send_key(char)


    def get_uuid(self):
        """
        Catch UUID of the VM.

        @return: None,if not specified in config file
        """
        if self.params.get("uuid") == "random":
            return self.uuid
        else:
            return self.params.get("uuid", None)


    def get_cpu_count(self):
        """
        Get the cpu count of the VM.
        """
        session = self.remote_login()
        if not session:
            return None
        try:
            return int(session.cmd(self.params.get("cpu_chk_cmd")))
        finally:
            session.close()


    def get_memory_size(self, cmd=None):
        """
        Get bootup memory size of the VM.

        @param check_cmd: Command used to check memory. If not provided,
                self.params.get("mem_chk_cmd") will be used.
        """
        session = self.remote_login()
        if not session:
            return None
        try:
            if not cmd:
                cmd = self.params.get("mem_chk_cmd")
            mem_str = session.cmd(cmd)
            mem = re.findall("([0-9]+)", mem_str)
            mem_size = 0
            for m in mem:
                mem_size += int(m)
            if "GB" in mem_str:
                mem_size *= 1024
            elif "MB" in mem_str:
                pass
            else:
                mem_size /= 1024
            return int(mem_size)
        finally:
            session.close()


    def get_current_memory_size(self):
        """
        Get current memory size of the VM, rather than bootup memory.
        """
        cmd = self.params.get("mem_chk_cur_cmd")
        return self.get_memory_size(cmd)


    def save_to_file(self, path):
        """
        Save the state of virtual machine to a file through migrate to
        exec
        """
        # Make sure we only get one iteration
        self.monitor.cmd("migrate_set_speed 1000g")
        self.monitor.cmd("migrate_set_downtime 100000000")
        self.monitor.migrate('"exec:cat>%s"' % path)
