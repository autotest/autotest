#!/usr/bin/python
"""
Utility classes and functions to handle Virtual Machine creation using qemu.

@copyright: 2008-2009 Red Hat Inc.
"""

import time, socket, os, logging, fcntl, re, commands
import kvm_utils, kvm_subprocess


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

    logging.debug("Running qemu-img command:\n%s" % qemu_img_cmd)
    (status, output) = kvm_subprocess.run_fg(qemu_img_cmd, logging.debug,
                                             "(qemu-img) ", timeout=30)

    if status is None:
        logging.error("Timeout elapsed while waiting for qemu-img command "
                      "to complete:\n%s" % qemu_img_cmd)
        return None
    elif status != 0:
        logging.error("Could not create image; "
                      "qemu-img command failed:\n%s" % qemu_img_cmd)
        logging.error("Status: %s" % status)
        logging.error("Output:" + kvm_utils.format_str_for_message(output))
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
        if name == None:
            name = self.name
        if params == None:
            params = self.params.copy()
        if root_dir == None:
            root_dir = self.root_dir
        if address_cache == None:
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
        if name == None:
            name = self.name
        if params == None:
            params = self.params
        if root_dir == None:
            root_dir = self.root_dir

        # Start constructing the qemu command
        qemu_cmd = ""
        # Set the X11 display parameter if requested
        if params.get("x11_display"):
            qemu_cmd += "DISPLAY=%s " % params.get("x11_display")
        # Add the qemu binary
        qemu_cmd += kvm_utils.get_path(root_dir, params.get("qemu_binary",
                                                            "qemu"))
        # Add the VM's name
        qemu_cmd += " -name '%s'" % name
        # Add the monitor socket parameter
        qemu_cmd += " -monitor unix:%s,server,nowait" % self.monitor_file_name

        for image_name in kvm_utils.get_sub_dict_names(params, "images"):
            image_params = kvm_utils.get_sub_dict(params, image_name)
            if image_params.get("boot_drive") == "no":
                continue
            qemu_cmd += " -drive file=%s" % get_image_filename(image_params,
                                                               root_dir)
            if image_params.get("drive_format"):
                qemu_cmd += ",if=%s" % image_params.get("drive_format")
            if image_params.get("drive_cache"):
                qemu_cmd += ",cache=%s" % image_params.get("drive_cache")
            if image_params.get("drive_serial"):
                qemu_cmd += ",serial=%s" % image_params.get("drive_serial")
            if image_params.get("image_snapshot") == "yes":
                qemu_cmd += ",snapshot=on"
            if image_params.get("image_boot") == "yes":
                qemu_cmd += ",boot=on"

        vlan = 0
        for nic_name in kvm_utils.get_sub_dict_names(params, "nics"):
            nic_params = kvm_utils.get_sub_dict(params, nic_name)
            # Handle the '-net nic' part
            qemu_cmd += " -net nic,vlan=%d" % vlan
            if nic_params.get("nic_model"):
                qemu_cmd += ",model=%s" % nic_params.get("nic_model")
            if nic_params.has_key("address_index"):
                mac, ip = kvm_utils.get_mac_ip_pair_from_dict(nic_params)
                if mac:
                    qemu_cmd += ",macaddr=%s" % mac
            # Handle the '-net tap' or '-net user' part
            mode = nic_params.get("nic_mode", "user")
            qemu_cmd += " -net %s,vlan=%d" % (mode, vlan)
            if mode == "tap":
                if nic_params.get("nic_ifname"):
                    qemu_cmd += ",ifname=%s" % nic_params.get("nic_ifname")
                script_path = nic_params.get("nic_script")
                if script_path:
                    script_path = kvm_utils.get_path(root_dir, script_path)
                    qemu_cmd += ",script=%s" % script_path
                script_path = nic_params.get("nic_downscript")
                if script_path:
                    script_path = kvm_utils.get_path(root_dir, script_path)
                    qemu_cmd += ",downscript=%s" % script_path
            # Proceed to next NIC
            vlan += 1

        mem = params.get("mem")
        if mem:
            qemu_cmd += " -m %s" % mem

        iso = params.get("cdrom")
        if iso:
            iso = kvm_utils.get_path(root_dir, iso)
            qemu_cmd += " -cdrom %s" % iso

        extra_params = params.get("extra_params")
        if extra_params:
            qemu_cmd += " %s" % extra_params

        for redir_name in kvm_utils.get_sub_dict_names(params, "redirs"):
            redir_params = kvm_utils.get_sub_dict(params, redir_name)
            guest_port = int(redir_params.get("guest_port"))
            host_port = self.redirs.get(guest_port)
            qemu_cmd += " -redir tcp:%s::%s" % (host_port, guest_port)

        if params.get("display") == "vnc":
            qemu_cmd += " -vnc :%d" % (self.vnc_port - 5900)
        elif params.get("display") == "sdl":
            qemu_cmd += " -sdl"
        elif params.get("display") == "nographic":
            qemu_cmd += " -nographic"

        if params.get("uuid") == "random":
            qemu_cmd += " -uuid %s" % self.uuid
        elif params.get("uuid"):
            qemu_cmd += " -uuid %s" % params.get("uuid")

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

        if name != None:
            self.name = name
        if params != None:
            self.params = params
        if root_dir != None:
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
                actual_md5sum = kvm_utils.md5sum_file(iso, 1048576)
                expected_md5sum = params.get("md5sum_1m")
                compare = True
            elif params.get("md5sum"):
                logging.debug("Comparing expected MD5 sum with MD5 sum of ISO "
                              "file...")
                actual_md5sum = kvm_utils.md5sum_file(iso)
                expected_md5sum = params.get("md5sum")
                compare = True
            if compare:
                if actual_md5sum == expected_md5sum:
                    logging.debug("MD5 sums match")
                else:
                    logging.error("Actual MD5 sum differs from expected one")
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
                self.vnc_port = kvm_utils.find_free_port(5900, 6000)

            # Find random UUID if specified 'uuid = random' in config file
            if params.get("uuid") == "random":
                f = open("/proc/sys/kernel/random/uuid")
                self.uuid = f.read().strip()
                f.close()

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
                return False

            logging.debug("VM appears to be alive with PID %d",
                          self.process.get_pid())
            return True

        finally:
            fcntl.lockf(lockfile, fcntl.LOCK_UN)
            lockfile.close()


    def send_monitor_cmd(self, command, block=True, timeout=20.0):
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
                    o += s.recv(16384)
                    if o.splitlines()[-1].split()[-1] == "(qemu)":
                        return (True, o)
                except:
                    time.sleep(0.01)
            return (False, o)

        # Connect to monitor
        logging.debug("Sending monitor command: %s" % command)
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.setblocking(False)
            s.connect(self.monitor_file_name)
        except:
            logging.debug("Could not connect to monitor socket")
            return (1, "")
        status, data = read_up_to_qemu_prompt(s, timeout)
        if not status:
            s.close()
            logging.debug("Could not find (qemu) prompt; output so far:" \
                    + kvm_utils.format_str_for_message(data))
            return (1, "")
        # Send command
        s.sendall(command + "\n")
        # Receive command output
        data = ""
        if block:
            status, data = read_up_to_qemu_prompt(s, timeout)
            data = "\n".join(data.splitlines()[1:])
            if not status:
                s.close()
                logging.debug("Could not find (qemu) prompt after command;"
                              " output so far: %s",
                               kvm_utils.format_str_for_message(data))
                return (1, data)
        s.close()
        return (0, data)


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

            logging.debug("Destroying VM with PID %d..." %
                          self.process.get_pid())

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
            if self.process:
                self.process.close()


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
        Return the VM's PID.
        """
        return self.process.get_pid()


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
        client = self.params.get("shell_client")
        address = self.get_address(nic_index)
        port = self.get_port(int(self.params.get("shell_port")))

        if not address or not port:
            logging.debug("IP address or port unavailable")
            return None

        if client == "ssh":
            session = kvm_utils.ssh(address, port, username, password,
                                    prompt, timeout)
        elif client == "telnet":
            session = kvm_utils.telnet(address, port, username, password,
                                       prompt, timeout)
        elif client == "nc":
            session = kvm_utils.netcat(address, port, username, password,
                                       prompt, timeout)

        if session:
            session.set_status_test_command(self.params.get("status_test_"
                                                            "command", ""))
        return session


    def copy_files_to(self, local_path, remote_path, nic_index=0, timeout=300):
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


    def copy_files_from(self, remote_path, local_path, nic_index=0, timeout=300):
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
