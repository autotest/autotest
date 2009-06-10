#!/usr/bin/python
import time, socket, os, logging
import kvm_utils

"""
Utility classes and functions to handle Virtual Machine creation using qemu.

@copyright: 2008-2009 Red Hat Inc.
"""


def get_image_filename(params, image_dir):
    """
    Generate an image path from params and image_dir.

    @param params: Dictionary containing the test parameters.
    @param image_dir: The directory where the image is to be located

    @note: params should contain:
           image_name -- the name of the image file, without extension
           image_format -- the format of the image (qcow2, raw etc)
    """
    image_name = params.get("image_name", "image")
    image_format = params.get("image_format", "qcow2")
    image_filename = "%s.%s" % (image_name, image_format)
    image_filename = os.path.join(image_dir, image_filename)
    return image_filename


def create_image(params, qemu_img_path, image_dir):
    """
    Create an image using qemu_image.

    @param params: Dictionary containing the test parameters.
    @param qemu_img_path: The path of the qemu-img binary
    @param image_dir: The directory where the image is to be located

    @note: params should contain:
           image_name -- the name of the image file, without extension
           image_format -- the format of the image (qcow2, raw etc)
           image_size -- the requested size of the image (a string
           qemu-img can understand, such as '10G')
    """
    qemu_img_cmd = qemu_img_path
    qemu_img_cmd += " create"

    format = params.get("image_format", "qcow2")
    qemu_img_cmd += " -f %s" % format

    image_filename = get_image_filename(params, image_dir)
    qemu_img_cmd += " %s" % image_filename

    size = params.get("image_size", "10G")
    qemu_img_cmd += " %s" % size

    logging.debug("Running qemu-img command:\n%s" % qemu_img_cmd)
    (status, pid, output) = kvm_utils.run_bg(qemu_img_cmd, None,
                                             logging.debug, "(qemu-img) ",
                                             timeout=30)

    if status:
        logging.debug("qemu-img exited with status %d" % status)
        logging.error("Could not create image %s" % image_filename)
        return None
    if not os.path.exists(image_filename):
        logging.debug("Image file does not exist for some reason")
        logging.error("Could not create image %s" % image_filename)
        return None

    logging.info("Image created in %s" % image_filename)
    return image_filename


def remove_image(params, image_dir):
    """
    Remove an image file.

    @param params: A dict
    @param image_dir: The directory where the image is to be located

    @note: params should contain:
           image_name -- the name of the image file, without extension
           image_format -- the format of the image (qcow2, raw etc)
    """
    image_filename = get_image_filename(params, image_dir)
    logging.debug("Removing image file %s..." % image_filename)
    if os.path.exists(image_filename):
        os.unlink(image_filename)
    else:
        logging.debug("Image file %s not found")


class VM:
    """
    This class handles all basic VM operations.
    """

    def __init__(self, name, params, qemu_path, image_dir, iso_dir):
        """
        Initialize the object and set a few attributes.

        @param name: The name of the object
        @param params: A dict containing VM params
                (see method make_qemu_command for a full description)
        @param qemu_path: The path of the qemu binary
        @param image_dir: The directory where images reside
        @param iso_dir: The directory where ISOs reside
        """
        self.pid = None

        self.name = name
        self.params = params
        self.qemu_path = qemu_path
        self.image_dir = image_dir
        self.iso_dir = iso_dir


        # Find available monitor filename
        while True:
            # The monitor filename should be unique
            self.instance = time.strftime("%Y%m%d-%H%M%S-") + \
            kvm_utils.generate_random_string(4)
            self.monitor_file_name = os.path.join("/tmp",
                                                  "monitor-" + self.instance)
            if not os.path.exists(self.monitor_file_name):
                break


    def clone(self, name=None, params=None, qemu_path=None, image_dir=None,
              iso_dir=None):
        """
        Return a clone of the VM object with optionally modified parameters.
        The clone is initially not alive and needs to be started using create().
        Any parameters not passed to this function are copied from the source
        VM.

        @param name: Optional new VM name
        @param params: Optional new VM creation parameters
        @param qemu_path: Optional new path to qemu
        @param image_dir: Optional new image dir
        @param iso_dir: Optional new iso directory
        """
        if name == None:
            name = self.name
        if params == None:
            params = self.params.copy()
        if qemu_path == None:
            qemu_path = self.qemu_path
        if image_dir == None:
            image_dir = self.image_dir
        if iso_dir == None:
            iso_dir = self.iso_dir
        return VM(name, params, qemu_path, image_dir, iso_dir)


    def verify_process_identity(self):
        """
        Make sure .pid really points to the original qemu process. If .pid
        points to the same process that was created with the create method,
        or to a dead process, return True. Otherwise return False.
        """
        if self.is_dead():
            return True
        filename = "/proc/%d/cmdline" % self.pid
        if not os.path.exists(filename):
            logging.debug("Filename %s does not exist" % filename)
            return False
        file = open(filename)
        cmdline = file.read()
        file.close()
        if not self.qemu_path in cmdline:
            return False
        if not self.monitor_file_name in cmdline:
            return False
        return True


    def make_qemu_command(self, name=None, params=None, qemu_path=None,
                          image_dir=None, iso_dir=None):
        """
        Generate a qemu command line. All parameters are optional. If a
        parameter is not supplied, the corresponding value stored in the
        class attributes is used.


        @param name: The name of the object
        @param params: A dict containing VM params
        @param qemu_path: The path of the qemu binary
        @param image_dir: The directory where images reside
        @param iso_dir: The directory where ISOs reside


        @note: The params dict should contain:
               mem -- memory size in MBs
               cdrom -- ISO filename to use with the qemu -cdrom parameter
               (iso_dir is pre-pended to the ISO filename)
               extra_params -- a string to append to the qemu command
               ssh_port -- should be 22 for SSH, 23 for Telnet
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
        if qemu_path == None:
            qemu_path = self.qemu_path
        if image_dir == None:
            image_dir = self.image_dir
        if iso_dir == None:
            iso_dir = self.iso_dir

        # Start constructing the qemu command
        qemu_cmd = ""
        # Set the X11 display parameter if requested
        if params.get("x11_display"):
            qemu_cmd += "DISPLAY=%s " % params.get("x11_display")
        # Add the qemu binary
        qemu_cmd += qemu_path
        # Add the VM's name
        qemu_cmd += " -name '%s'" % name
        # Add the monitor socket parameter
        qemu_cmd += " -monitor unix:%s,server,nowait" % self.monitor_file_name

        for image_name in kvm_utils.get_sub_dict_names(params, "images"):
            image_params = kvm_utils.get_sub_dict(params, image_name)
            qemu_cmd += " -drive file=%s" % get_image_filename(image_params,
                                                               image_dir)
            if image_params.get("drive_format"):
                qemu_cmd += ",if=%s" % image_params.get("drive_format")
            if image_params.get("image_snapshot") == "yes":
                qemu_cmd += ",snapshot=on"
            if image_params.get("image_boot") == "yes":
                qemu_cmd += ",boot=on"

        vlan = 0
        for nic_name in kvm_utils.get_sub_dict_names(params, "nics"):
            nic_params = kvm_utils.get_sub_dict(params, nic_name)
            qemu_cmd += " -net nic,vlan=%d" % vlan
            if nic_params.get("nic_model"):
                qemu_cmd += ",model=%s" % nic_params.get("nic_model")
            qemu_cmd += " -net user,vlan=%d" % vlan
            vlan += 1

        mem = params.get("mem")
        if mem:
            qemu_cmd += " -m %s" % mem

        iso = params.get("cdrom")
        if iso:
            iso = os.path.join(iso_dir, iso)
            qemu_cmd += " -cdrom %s" % iso

        extra_params = params.get("extra_params")
        if extra_params:
            qemu_cmd += " %s" % extra_params

        for redir_name in kvm_utils.get_sub_dict_names(params, "redirs"):
            redir_params = kvm_utils.get_sub_dict(params, redir_name)
            guest_port = int(redir_params.get("guest_port"))
            host_port = self.get_port(guest_port)
            qemu_cmd += " -redir tcp:%s::%s" % (host_port, guest_port)

        if params.get("display") == "vnc":
            qemu_cmd += " -vnc :%d" % (self.vnc_port - 5900)
        elif params.get("display") == "sdl":
            qemu_cmd += " -sdl"
        elif params.get("display") == "nographic":
            qemu_cmd += " -nographic"

        return qemu_cmd


    def create(self, name=None, params=None, qemu_path=None, image_dir=None,
               iso_dir=None, for_migration=False, timeout=5.0):
        """
        Start the VM by running a qemu command.
        All parameters are optional. The following applies to all parameters
        but for_migration: If a parameter is not supplied, the corresponding
        value stored in the class attributes is used, and if it is supplied,
        it is stored for later use.

        @param name: The name of the object
        @param params: A dict containing VM params
        @param qemu_path: The path of the qemu binary
        @param image_dir: The directory where images reside
        @param iso_dir: The directory where ISOs reside
        @param for_migration: If True, start the VM with the -incoming
        option
        """
        if name != None:
            self.name = name
        if params != None:
            self.params = params
        if qemu_path != None:
            self.qemu_path = qemu_path
        if image_dir != None:
            self.image_dir = image_dir
        if iso_dir != None:
            self.iso_dir = iso_dir
        name = self.name
        params = self.params
        qemu_path = self.qemu_path
        image_dir = self.image_dir
        iso_dir = self.iso_dir

        # Verify the md5sum of the ISO image
        iso = params.get("cdrom")
        if iso:
            iso = os.path.join(iso_dir, iso)
            if not os.path.exists(iso):
                logging.error("ISO file not found: %s" % iso)
                return False
            compare = False
            if params.get("md5sum_1m"):
                logging.debug("Comparing expected MD5 sum with MD5 sum of first"
                              "MB of ISO file...")
                actual_md5sum = kvm_utils.md5sum_file(iso, 1048576)
                expected_md5sum = params.get("md5sum_1m")
                compare = True
            elif params.get("md5sum"):
                logging.debug("Comparing expected MD5 sum with MD5 sum of ISO"
                              " file...")
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

            # Make qemu command
            qemu_command = self.make_qemu_command()

            # Is this VM supposed to accept incoming migrations?
            if for_migration:
                # Find available migration port
                self.migration_port = kvm_utils.find_free_port(5200, 6000)
                # Add -incoming option to the qemu command
                qemu_command += " -incoming tcp:0:%d" % self.migration_port

            logging.debug("Running qemu command:\n%s", qemu_command)
            (status, pid, output) = kvm_utils.run_bg(qemu_command, None,
                                                     logging.debug, "(qemu) ")

            if status:
                logging.debug("qemu exited with status %d", status)
                logging.error("VM could not be created -- qemu command"
                              " failed:\n%s", qemu_command)
                return False

            self.pid = pid

            if not kvm_utils.wait_for(self.is_alive, timeout, 0, 1):
                logging.debug("VM is not alive for some reason")
                logging.error("VM could not be created with"
                              " command:\n%s", qemu_command)
                self.destroy()
                return False

            logging.debug("VM appears to be alive with PID %d", self.pid)
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

        If gracefully is True, first attempt to kill the VM via SSH/Telnet
        with a shutdown command. Then, attempt to destroy the VM via the
        monitor with a 'quit' command. If that fails, send SIGKILL to the
        qemu process.

        @param gracefully: Whether an attempt will be made to end the VM
                using monitor command before trying to kill the qemu process
                or not.
        """
        # Is it already dead?
        if self.is_dead():
            logging.debug("VM is already down")
            return

        logging.debug("Destroying VM with PID %d..." % self.pid)

        if gracefully and self.params.get("cmd_shutdown"):
            # Try to destroy with SSH command
            logging.debug("Trying to shutdown VM with SSH command...")
            (status, output) = self.ssh(self.params.get("cmd_shutdown"))
            # Was the command sent successfully?
            if status == 0:
            #if self.ssh(self.params.get("cmd_shutdown")):
                logging.debug("Shutdown command sent; Waiting for VM to go"
                              "down...")
                if kvm_utils.wait_for(self.is_dead, 60, 1, 1):
                    logging.debug("VM is down")
                    self.pid = None
                    return

        # Try to destroy with a monitor command
        logging.debug("Trying to kill VM with monitor command...")
        (status, output) = self.send_monitor_cmd("quit", block=False)
        # Was the command sent successfully?
        if status == 0:
            # Wait for the VM to be really dead
            if kvm_utils.wait_for(self.is_dead, 5, 0.5, 0.5):
                logging.debug("VM is down")
                self.pid = None
                return

        # If the VM isn't dead yet...
        logging.debug("Cannot quit normally; Sending a kill to close the"
                      " deal...")
        kvm_utils.safe_kill(self.pid, 9)
        # Wait for the VM to be really dead
        if kvm_utils.wait_for(self.is_dead, 5, 0.5, 0.5):
            logging.debug("VM is down")
            self.pid = None
            return

        logging.error("We have a zombie! PID %d is a zombie!" % self.pid)


    def is_alive(self):
        """
        Return True if the VM's monitor is responsive.
        """
        # Check if the process exists
        if not kvm_utils.pid_exists(self.pid):
            return False
        # Try sending a monitor command
        (status, output) = self.send_monitor_cmd("help")
        if status:
            return False
        return True


    def is_dead(self):
        """
        Return True iff the VM's PID does not exist.
        """
        return not kvm_utils.pid_exists(self.pid)


    def get_params(self):
        """
        Return the VM's params dict. Most modified params take effect only
        upon VM.create().
        """
        return self.params


    def get_address(self):
        """
        Return the guest's address in host space.

        If port redirection is used, return 'localhost' (the guest has no IP
        address of its own).  Otherwise return the guest's IP address.
        """
        # Currently redirection is always used, so return 'localhost'
        return "localhost"


    def get_port(self, port):
        """
        Return the port in host space corresponding to port in guest space.

        @param port: Port number in host space.
        @return: If port redirection is used, return the host port redirected
                to guest port port. Otherwise return port.
        """
        # Currently redirection is always used, so use the redirs dict
        if self.redirs.has_key(port):
            return self.redirs[port]
        else:
            logging.debug("Warning: guest port %s requested but not"
                          " redirected" % port)
            return None


    def is_sshd_running(self, timeout=10):
        """
        Return True iff the guest's SSH port is responsive.

        @param timeout: Time (seconds) before giving up checking the SSH daemon
                responsiveness.
        """
        address = self.get_address()
        port = self.get_port(int(self.params.get("ssh_port")))
        if not port:
            return False
        return kvm_utils.is_sshd_running(address, port, timeout=timeout)


    def ssh_login(self, timeout=10):
        """
        Log into the guest via SSH/Telnet.
        If timeout expires while waiting for output from the guest (e.g. a
        password prompt or a shell prompt) -- fail.

        @param timeout: Time (seconds) before giving up logging into the
                guest.
        @return: kvm_spawn object on success and None on failure.
        """
        username = self.params.get("username", "")
        password = self.params.get("password", "")
        prompt = self.params.get("ssh_prompt", "[\#\$]")
        use_telnet = self.params.get("use_telnet") == "yes"
        address = self.get_address()
        port = self.get_port(int(self.params.get("ssh_port")))
        if not port:
            return None

        if use_telnet:
            session = kvm_utils.telnet(address, port, username, password,
                                       prompt, timeout)
        else:
            session = kvm_utils.ssh(address, port, username, password,
                                    prompt, timeout)
        if session:
            session.set_status_test_command(self.params.get("ssh_status_test_"
                                                            "command", ""))
        return session


    def scp_to_remote(self, local_path, remote_path, timeout=300):
        """
        Transfer files to the guest via SCP.

        @param local_path: Host path
        @param remote_path: Guest path
        @param timeout: Time (seconds) before giving up on doing the remote
                copy.
        """
        username = self.params.get("username", "")
        password = self.params.get("password", "")
        address = self.get_address()
        port = self.get_port(int(self.params.get("ssh_port")))
        if not port:
            return None
        return kvm_utils.scp_to_remote(address, port, username, password,
                                       local_path, remote_path, timeout)


    def scp_from_remote(self, remote_path, local_path, timeout=300):
        """
        Transfer files from the guest via SCP.

        @param local_path: Guest path
        @param remote_path: Host path
        @param timeout: Time (seconds) before giving up on doing the remote
                copy.
        """
        username = self.params.get("username", "")
        password = self.params.get("password", "")
        address = self.get_address()
        port = self.get_port(int(self.params.get("ssh_port")))
        if not port:
            return None
        return kvm_utils.scp_from_remote(address, port, username, password,
                                         remote_path, local_path, timeout)


    def ssh(self, command, timeout=10):
        """
        Login via SSH/Telnet and send a command.

        @command: Command that will be sent.
        @timeout: Time before giving up waiting on a status return.
        @return: A tuple (status, output). status is 0 on success and 1 on
                failure.
        """
        session = self.ssh_login(timeout)
        if not session:
            return (1, "")

        logging.debug("Sending command: %s" % command)
        session.sendline(command)
        output = session.read_nonblocking(1.0)
        session.close()

        return (0, output)


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
