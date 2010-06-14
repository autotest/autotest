#!/usr/bin/python
"""
Utility classes and functions to handle Virtual Machine creation using qemu.

@copyright: 2008-2009 Red Hat Inc.
"""

import time, socket, os, logging, fcntl, re, commands
import kvm_utils, kvm_subprocess
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
        self.redirs = {}
        self.vnc_port = 5900
        self.uuid = None

        self.name = name
        self.params = params
        self.root_dir = root_dir
        self.address_cache = address_cache
        self.pci_assignable = None

        # Find available monitor filename
        while True:
            # The monitor filename should be unique
            self.instance = (time.strftime("%Y%m%d-%H%M%S-") +
                             kvm_utils.generate_random_string(4))
            self.monitor_file_name = os.path.join("/tmp",
                                                  "monitor-" + self.instance)
            if not os.path.exists(self.monitor_file_name):
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

        def add_unix_socket_monitor(help, filename):
            return " -monitor unix:%s,server,nowait" % filename

        def add_mem(help, mem):
            return " -m %s" % mem

        def add_smp(help, smp):
            return " -smp %s" % smp

        def add_cdrom(help, filename, index=2):
            if has_option(help, "drive"):
                return " -drive file=%s,index=%d,media=cdrom" % (filename,
                                                                 index)
            else:
                return " -cdrom %s" % filename

        def add_drive(help, filename, format=None, cache=None, werror=None,
                      serial=None, snapshot=False, boot=False):
            cmd = " -drive file=%s" % filename
            if format: cmd += ",if=%s" % format
            if cache: cmd += ",cache=%s" % cache
            if werror: cmd += ",werror=%s" % werror
            if serial: cmd += ",serial=%s" % serial
            if snapshot: cmd += ",snapshot=on"
            if boot: cmd += ",boot=on"
            return cmd

        def add_nic(help, vlan, model=None, mac=None):
            cmd = " -net nic,vlan=%d" % vlan
            if model: cmd += ",model=%s" % model
            if mac: cmd += ",macaddr=%s" % mac
            return cmd

        def add_net(help, vlan, mode, ifname=None, script=None,
                    downscript=None):
            cmd = " -net %s,vlan=%d" % (mode, vlan)
            if mode == "tap":
                if ifname: cmd += ",ifname=%s" % ifname
                if script: cmd += ",script=%s" % script
                cmd += ",downscript=%s" % (downscript or "no")
            return cmd

        def add_floppy(help, filename):
            return " -fda %s" % filename

        def add_tftp(help, filename):
            return " -tftp %s" % filename

        def add_tcp_redir(help, host_port, guest_port):
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
            return " -uuid %s" % uuid

        def add_pcidevice(help, host):
            return " -pcidevice host=%s" % host

        def add_kernel(help, filename):
            return " -kernel %s" % filename

        def add_initrd(help, filename):
            return " -initrd %s" % filename

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
        # Add the monitor socket parameter
        qemu_cmd += add_unix_socket_monitor(help, self.monitor_file_name)

        for image_name in kvm_utils.get_sub_dict_names(params, "images"):
            image_params = kvm_utils.get_sub_dict(params, image_name)
            if image_params.get("boot_drive") == "no":
                continue
            qemu_cmd += add_drive(help,
                                  get_image_filename(image_params, root_dir),
                                  image_params.get("drive_format"),
                                  image_params.get("drive_cache"),
                                  image_params.get("drive_werror"),
                                  image_params.get("drive_serial"),
                                  image_params.get("image_snapshot") == "yes",
                                  image_params.get("image_boot") == "yes")

        vlan = 0
        for nic_name in kvm_utils.get_sub_dict_names(params, "nics"):
            nic_params = kvm_utils.get_sub_dict(params, nic_name)
            # Handle the '-net nic' part
            mac = None
            if "address_index" in nic_params:
                mac = kvm_utils.get_mac_ip_pair_from_dict(nic_params)[0]
            qemu_cmd += add_nic(help, vlan, nic_params.get("nic_model"), mac)
            # Handle the '-net tap' or '-net user' part
            script = nic_params.get("nic_script")
            downscript = nic_params.get("nic_downscript")
            if script:
                script = kvm_utils.get_path(root_dir, script)
            if downscript:
                downscript = kvm_utils.get_path(root_dir, downscript)
            qemu_cmd += add_net(help, vlan, nic_params.get("nic_mode", "user"),
                                nic_params.get("nic_ifname"),
                                script, downscript)
            # Proceed to next NIC
            vlan += 1

        mem = params.get("mem")
        if mem:
            qemu_cmd += add_mem(help, mem)

        smp = params.get("smp")
        if smp:
            qemu_cmd += " -smp %s" % smp

        iso = params.get("cdrom")
        if iso:
            iso = kvm_utils.get_path(root_dir, iso)
            qemu_cmd += add_cdrom(help, iso)

        # Even though this is not a really scalable approach,
        # it doesn't seem like we are going to need more than
        # 2 CDs active on the same VM.
        iso_extra = params.get("cdrom_extra")
        if iso_extra:
            iso_extra = kvm_utils.get_path(root_dir, iso_extra)
            qemu_cmd += add_cdrom(help, iso_extra, 3)

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

        kernel = params.get("kernel")
        if kernel:
            kernel = kvm_utils.get_path(root_dir, kernel)
            qemu_cmd += add_kernel(help, kernel)

        initrd = params.get("initrd")
        if initrd:
            initrd = kvm_utils.get_path(root_dir, initrd)
            qemu_cmd += add_initrd(help, initrd)

        for redir_name in kvm_utils.get_sub_dict_names(params, "redirs"):
            redir_params = kvm_utils.get_sub_dict(params, redir_name)
            guest_port = int(redir_params.get("guest_port"))
            host_port = self.redirs.get(guest_port)
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

        # If the PCI assignment step went OK, add each one of the PCI assigned
        # devices to the qemu command line.
        if self.pci_assignable:
            for pci_id in self.pa_pci_ids:
                qemu_cmd += add_pcidevice(help, pci_id)

        extra_params = params.get("extra_params")
        if extra_params:
            qemu_cmd += " %s" % extra_params

        return qemu_cmd


    def create(self, name=None, params=None, root_dir=None,
               for_migration=False, timeout=5.0):
        """
        Start the VM by running a qemu command.
        All parameters are optional. The following applies to all parameters
        but for_migration: If a parameter is not supplied, the corresponding
        value stored in the class attributes is used, and if it is supplied,
        it is stored for later use.

        @param name: The name of the object
        @param params: A dict containing VM params
        @param root_dir: Base directory for relative filenames
        @param for_migration: If True, start the VM with the -incoming
        option
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

            # Find available VNC port, if needed
            if params.get("display") == "vnc":
                self.vnc_port = kvm_utils.find_free_port(5900, 6100)

            # Find random UUID if specified 'uuid = random' in config file
            if params.get("uuid") == "random":
                f = open("/proc/sys/kernel/random/uuid")
                self.uuid = f.read().strip()
                f.close()

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

            # Is this VM supposed to accept incoming migrations?
            if for_migration:
                # Find available migration port
                self.migration_port = kvm_utils.find_free_port(5200, 6000)
                # Add -incoming option to the qemu command
                qemu_command += " -incoming tcp:0:%d" % self.migration_port

            logging.debug("Running qemu command:\n%s", qemu_command)
            self.process = kvm_subprocess.run_bg(qemu_command, None,
                                                 logging.debug, "(qemu) ")

            if not self.process.is_alive():
                logging.error("VM could not be created; "
                              "qemu command failed:\n%s" % qemu_command)
                logging.error("Status: %s" % self.process.get_status())
                logging.error("Output:" + kvm_utils.format_str_for_message(
                    self.process.get_output()))
                self.destroy()
                return False

            if not kvm_utils.wait_for(self.is_alive, timeout, 0, 1):
                logging.error("VM is not alive for some reason; "
                              "qemu command:\n%s" % qemu_command)
                self.destroy()
                return False

            # Get the output so far, to see if we have any problems with
            # hugepage setup.
            output = self.process.get_output()

            if "alloc_mem_area" in output:
                logging.error("Could not allocate hugepage memory; "
                              "qemu command:\n%s" % qemu_command)
                logging.error("Output:" + kvm_utils.format_str_for_message(
                              self.process.get_output()))
                self.destroy()
                return False

            logging.debug("VM appears to be alive with PID %s", self.get_pid())
            return True

        finally:
            fcntl.lockf(lockfile, fcntl.LOCK_UN)
            lockfile.close()


    def send_monitor_cmd(self, command, block=True, timeout=20.0, verbose=True):
        """
        Send command to the QEMU monitor.

        Connect to the VM's monitor socket and wait for the (qemu) prompt.
        If block is True, read output from the socket until the (qemu) prompt
        is found again, or until timeout expires.

        Return a tuple containing an integer indicating success or failure,
        and the data read so far. The integer is 0 on success and 1 on failure.
        A failure is any of the following cases: connection to the socket
        failed, or the first (qemu) prompt could not be found, or block is
        True and the second prompt could not be found.

        @param command: Command that will be sent to the monitor
        @param block: Whether the output from the socket will be read until
                the timeout expires
        @param timeout: Timeout (seconds) before giving up on reading from
                socket
        """
        def read_up_to_qemu_prompt(s, timeout):
            """
            Read data from socket s until the (qemu) prompt is found.

            If the prompt is found before timeout expires, return a tuple
            containing True and the data read. Otherwise return a tuple
            containing False and the data read so far.

            @param s: Socket object
            @param timeout: Time (seconds) before giving up trying to get the
                    qemu prompt.
            """
            o = ""
            end_time = time.time() + timeout
            while time.time() < end_time:
                try:
                    o += s.recv(1024)
                    if o.splitlines()[-1].split()[-1] == "(qemu)":
                        return (True, o)
                except:
                    time.sleep(0.01)
            return (False, o)

        # In certain conditions printing this debug output might be too much
        # Just print it if verbose is enabled (True by default)
        if verbose:
            logging.debug("Sending monitor command: %s" % command)
        # Connect to monitor
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.setblocking(False)
            s.connect(self.monitor_file_name)
        except:
            logging.debug("Could not connect to monitor socket")
            return (1, "")

        # Send the command and get the resulting output
        try:
            status, data = read_up_to_qemu_prompt(s, timeout)
            if not status:
                logging.debug("Could not find (qemu) prompt; output so far:" +
                              kvm_utils.format_str_for_message(data))
                return (1, "")
            # Send command
            s.sendall(command + "\n")
            # Receive command output
            data = ""
            if block:
                status, data = read_up_to_qemu_prompt(s, timeout)
                data = "\n".join(data.splitlines()[1:])
                if not status:
                    logging.debug("Could not find (qemu) prompt after command; "
                                  "output so far:" +
                                  kvm_utils.format_str_for_message(data))
                    return (1, data)
            return (0, data)

        # Clean up before exiting
        finally:
            s.shutdown(socket.SHUT_RDWR)
            s.close()


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
                            logging.debug("VM is down")
                            return
                    finally:
                        session.close()

            # Try to destroy with a monitor command
            logging.debug("Trying to kill VM with monitor command...")
            status, output = self.send_monitor_cmd("quit", block=False)
            # Was the command sent successfully?
            if status == 0:
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
            if self.pci_assignable:
                self.pci_assignable.release_devs()
            if self.process:
                self.process.close()
            try:
                os.unlink(self.monitor_file_name)
            except OSError:
                pass


    def is_alive(self):
        """
        Return True if the VM's monitor is responsive.
        """
        # Check if the process is running
        if self.is_dead():
            return False
        # Try sending a monitor command
        (status, output) = self.send_monitor_cmd("help")
        if status:
            return False
        return True


    def is_dead(self):
        """
        Return True if the qemu process is dead.
        """
        return not self.process or not self.process.is_alive()


    def kill_tail_thread(self):
        """
        Stop the tailing thread which reports the output of qemu.
        """
        if self.process:
            self.process.kill_tail_thread()


    def get_params(self):
        """
        Return the VM's params dict. Most modified params take effect only
        upon VM.create().
        """
        return self.params


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
            mac, ip = kvm_utils.get_mac_ip_pair_from_dict(nic_params)
            if not mac:
                logging.debug("MAC address unavailable")
                return None
            if not ip or nic_params.get("always_use_tcpdump") == "yes":
                # Get the IP address from the cache
                ip = self.address_cache.get(mac)
                if not ip:
                    logging.debug("Could not find IP address for MAC address: "
                                  "%s" % mac)
                    return None
                # Make sure the IP address is assigned to this guest
                nic_dicts = [kvm_utils.get_sub_dict(self.params, nic)
                             for nic in nics]
                macs = [kvm_utils.get_mac_ip_pair_from_dict(dict)[0]
                        for dict in nic_dicts]
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
        @return: kvm_spawn object on success and None on failure.
        """
        username = self.params.get("username", "")
        password = self.params.get("password", "")
        prompt = self.params.get("shell_prompt", "[\#\$]")
        linesep = eval("'%s'" % self.params.get("shell_linesep", r"\n"))
        client = self.params.get("shell_client")
        address = self.get_address(nic_index)
        port = self.get_port(int(self.params.get("shell_port")))

        if not address or not port:
            logging.debug("IP address or port unavailable")
            return None

        if client == "ssh":
            session = kvm_utils.ssh(address, port, username, password,
                                    prompt, linesep, timeout)
        elif client == "telnet":
            session = kvm_utils.telnet(address, port, username, password,
                                       prompt, linesep, timeout)
        elif client == "nc":
            session = kvm_utils.netcat(address, port, username, password,
                                       prompt, linesep, timeout)

        if session:
            session.set_status_test_command(self.params.get("status_test_"
                                                            "command", ""))
        return session


    def copy_files_to(self, local_path, remote_path, nic_index=0, timeout=600):
        """
        Transfer files to the guest.

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

        if not address or not port:
            logging.debug("IP address or port unavailable")
            return None

        if client == "scp":
            return kvm_utils.scp_to_remote(address, port, username, password,
                                           local_path, remote_path, timeout)


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

        if not address or not port:
            logging.debug("IP address or port unavailable")
            return None

        if client == "scp":
            return kvm_utils.scp_from_remote(address, port, username, password,
                                             remote_path, local_path, timeout)


    def send_key(self, keystr):
        """
        Send a key event to the VM.

        @param: keystr: A key event string (e.g. "ctrl-alt-delete")
        """
        # For compatibility with versions of QEMU that do not recognize all
        # key names: replace keyname with the hex value from the dict, which
        # QEMU will definitely accept
        dict = { "comma": "0x33",
                 "dot": "0x34",
                 "slash": "0x35" }
        for key in dict.keys():
            keystr = keystr.replace(key, dict[key])
        self.send_monitor_cmd("sendkey %s 1" % keystr)
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
            cmd = self.params.get("cpu_chk_cmd")
            s, count = session.get_command_status_output(cmd)
            if s == 0:
                return int(count)
            return None
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
            s, mem_str = session.get_command_status_output(cmd)
            if s != 0:
                return None
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
