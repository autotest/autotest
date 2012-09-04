"""
Interfaces to the virt agent.

@copyright: 2008-2012 Red Hat Inc.
"""

import socket, time, logging, random
from autotest.client.shared import error
from kvm_monitor import Monitor, MonitorError

try:
    import json
except ImportError:
    logging.warning("Could not import json module. "
                    "virt agent functionality disabled.")


class VAgentError(MonitorError):
    def __init__(self):
        MonitorError.__init__(self)


class VAgentConnectError(VAgentError):
    pass


class VAgentSocketError(VAgentError):
    def __init__(self, msg, e):
        VAgentError.__init__(self, msg, e)
        self.msg = msg
        self.e = e

    def __str__(self):
        return "%s    (%s)" % (self.msg, self.e)


class VAgentLockError(VAgentError):
    pass


class VAgentProtocolError(VAgentError):
    pass


class VAgentNotSupportedError(VAgentError):
    pass


class VAgentNotSupportedSerialError(VAgentNotSupportedError):
    pass


class VAgentCmdError(VAgentError):
    def __init__(self, cmd, args, data):
        VAgentError.__init__(self, cmd, args, data)
        self.cmd = cmd
        self.args = args
        self.data = data

    def __str__(self):
        return ("Virt Agent command %r failed    (arguments: %r,    "
                "error message: %r)" % (self.cmd, self.args, self.data))


class VAgentSyncError(VAgentError):
    def __init__(self, vm_name):
        VAgentError.__init__(self)
        self.vm = vm_name

    def __str__(self):
        return "Could not sync with guest agent in vm '%s'" % self.vm


class VAgentSuspendError(VAgentError):
    pass


class VAgentSuspendUnknownModeError(VAgentSuspendError):
    def __init__(self, mode):
        VAgentSuspendError.__init__(self)
        self.mode = mode

    def __str__(self):
        return "Not supported suspend mode '%s'" % self.mode


class VAgentFreezeStatusError(VAgentError):
    def __init__(self, vm, status, expected):
        VAgentError.__init__(self)
        self.vm = vm
        self.status = status
        self.expected = expected


    def __str__(self):
        return ("Unexpected guest FS status '%s' (expected '%s') in vm "
                "'%s'" % (self.status, self.expected, self.vm))


class QemuAgent(Monitor):
    """
    Wraps qemu guest agent commands.
    """

    READ_OBJECTS_TIMEOUT = 5
    CMD_TIMEOUT = 20
    RESPONSE_TIMEOUT = 20
    PROMPT_TIMEOUT = 20

    SHUTDOWN_MODE_POWERDOWN = "powerdown"
    SHUTDOWN_MODE_REBOOT = "reboot"
    SHUTDOWN_MODE_HALT = "halt"

    SUSPEND_MODE_DISK = "disk"
    SUSPEND_MODE_RAM = "ram"
    SUSPEND_MODE_HYBRID = "hybrid"

    FSFREEZE_STATUS_FROZEN = "frozen"
    FSFREEZE_STATUS_THAWED = "thawed"


    def __init__(self, vm, name, serial_type, get_supported_cmds=False,
                 suppress_exceptions=False):
        """
        Connect to the guest agent socket, Also make sure the json
        module is available.

        @param vm: The VM object who has this GuestAgent.
        @param name: Guest agent identifier.
        @param serial_type: Specific which serial type (firtio or isa) guest
                agent will use.
        @param get_supported_cmds: Try to get supported cmd list when initiation.
        @param suppress_exceptions: If True, ignore VAgentError exception.

        @raise VAgentConnectError: Raised if the connection fails and
                suppress_exceptions is False
        @raise VAgentNotSupportedSerialError: Raised if the serial type is
                neither 'virtio' nor 'isa' and suppress_exceptions is False
        @raise VAgentNotSupportedError: Raised if json isn't available and
                suppress_exceptions is False
        """
        try:
            if serial_type == "virtio":
                filename = vm.get_virtio_port_filename(name)
            elif serial_type == "isa":
                filename = vm.get_serial_console_filename(name)
            else:
                raise VAgentNotSupportedSerialError("Not supported serial type"
                                                    "'%s'" % serial_type)

            Monitor.__init__(self, name, filename)
            # Make sure json is available
            try:
                json
            except NameError:
                raise VAgentNotSupportedError("guest agent requires the json"
                                              " module (Python 2.6 and up)")

            # Set a reference to the VM object that has this GuestAgent.
            self.vm = vm

            if get_supported_cmds:
                self._get_supported_cmds()

        except VAgentError, e:
            self._close_sock()
            if suppress_exceptions:
                logging.warn(e)
            else:
                raise


    # Methods only used inside this class

    def _build_cmd(self, cmd, args=None):
        obj = {"execute": cmd}
        if args is not None:
            obj["arguments"] = args
        return obj


    def _read_objects(self, timeout=READ_OBJECTS_TIMEOUT):
        """
        Read lines from the guest agent socket and try to decode them.
        Stop when all available lines have been successfully decoded, or when
        timeout expires. Return all decoded objects.

        @param timeout: Time to wait for all lines to decode successfully
        @return: A list of objects
        """
        if not self._data_available():
            return []
        s = ""
        end_time = time.time() + timeout
        while self._data_available(end_time - time.time()):
            s += self._recvall()
            # Make sure all lines are decodable
            for line in s.splitlines():
                if line:
                    try:
                        json.loads(line)
                    except Exception:
                        # Found an incomplete or broken line -- keep reading
                        break
            else:
                # All lines are OK -- stop reading
                break
        # Decode all decodable lines
        objs = []
        for line in s.splitlines():
            try:
                objs += [json.loads(line)]
                self._log_lines(line)
            except Exception:
                pass
        return objs


    def _send(self, data):
        """
        Send raw data without waiting for response.

        @param data: Data to send
        @raise VAgentSocketError: Raised if a socket error occurs
        """
        try:
            self._socket.sendall(data)
            self._log_lines(str(data))
        except socket.error, e:
            raise VAgentSocketError("Could not send data: %r" % data, e)


    def _get_response(self, timeout=RESPONSE_TIMEOUT):
        """
        Read a response from the guest agent socket.

        @param id: If not None, look for a response with this id
        @param timeout: Time duration to wait for response
        @return: The response dict
        """
        end_time = time.time() + timeout
        while self._data_available(end_time - time.time()):
            for obj in self._read_objects():
                if isinstance(obj, dict):
                    if "return" in obj or "error" in obj:
                        return obj
        # Return empty dict when timeout.
        return {}


    def _get_supported_cmds(self):
        """
        Get supported qmp cmds list.
        """
        cmds = self.cmd("guest-info", debug=False)
        if cmds and cmds.has_key("supported_commands"):
            cmd_list = cmds["supported_commands"]
            self._supported_cmds = [n["name"] for n in cmd_list if
                                    isinstance(n, dict) and n.has_key("name")]

        if not self._supported_cmds:
            # If initiation fails, set supported list to a None-only list.
            self._supported_cmds = [None]
            logging.warn("Could not get supported guest agent cmds list")


    def _has_command(self, cmd):
        """
        Check wheter guest agent support 'cmd'.

        @param cmd: command string which will be checked.

        @return: True if cmd is supported, False if not supported.
        """
        # Initiate supported cmds list if it's empty.
        if not self._supported_cmds:
            self.get_supported_cmds()

        # If the first element in supported cmd list is 'None', it means
        # autotest fails to get the cmd list, so bypass cmd checking.
        if self._supported_cmds[0] is None:
            return True

        if cmd and cmd in self._supported_cmds:
            return True
        return False


    def _log_command(self, cmd, debug=True, extra_str=""):
        """
        Print log message beening sent.

        @param cmd: Command string.
        @param debug: Whether to print the commands.
        @param extra_str: Extra string would be printed in log.
        """
        if self.debug_log or debug:
            logging.debug("(vagent %s) Sending command '%s' %s",
                          self.name, cmd, extra_str)


    def _log_response(self, cmd, resp, debug=True):
        """
        Print log message for guest agent cmd's response.

        @param cmd: Command string.
        @param resp: Response from guest agent command.
        @param debug: Whether to print the commands.
        """
        def _log_output(o, indent=0):
            logging.debug("(vagent %s)    %s%s",
                          self.name, " " * indent, o)

        def _dump_list(li, indent=0):
            for l in li:
                if isinstance(l, dict):
                    _dump_dict(l, indent + 2)
                else:
                    _log_output(str(l), indent)

        def _dump_dict(di, indent=0):
            for k, v in di.iteritems():
                o = "%s%s: " % (" " * indent, k)
                if isinstance(v, dict):
                    _log_output(o, indent)
                    _dump_dict(v, indent + 2)
                elif isinstance(v, list):
                    _log_output(o, indent)
                    _dump_list(v, indent + 2)
                else:
                    o += str(v)
                    _log_output(o, indent)

        if self.debug_log or debug:
            logging.debug("(vagent %s) Response to '%s' "
                          "(re-formated)", self.name, cmd)
            if isinstance(resp, dict):
                _dump_dict(resp)
            elif isinstance(resp, list):
                _dump_list(resp)
            else:
                for l in str(resp).splitlines():
                    _log_output(l)


    # Public methods

    def cmd(self, cmd, args=None, timeout=CMD_TIMEOUT, debug=True,
            success_resp=True):
        """
        Send a guest agent command and return the response if success_resp is
        True.

        @param cmd: Command to send
        @param args: A dict containing command arguments, or None
        @param timeout: Time duration to wait for response
        @param debug: Whether to print the commands being sent and responses
        @param fd: file object or file descriptor to pass

        @return: The response received

        @raise VAgentLockError: Raised if the lock cannot be acquired
        @raise VAgentSocketError: Raised if a socket error occurs
        @raise VAgentProtocolError: Raised if no response is received
        @raise VAgentCmdError: Raised if the response is an error message
                               (the exception's args are (cmd, args, data)
                                where data is the error data)
        """
        self._log_command(cmd, debug)
        # Send command
        cmdobj = self._build_cmd(cmd, args)
        data = json.dumps(cmdobj) + "\n"
        r = self.cmd_raw(data, timeout, success_resp)

        if not success_resp:
            return ""

        if "return" in r:
            ret = r["return"]
            if ret:
                self._log_response(cmd, ret, debug)
            return ret
        if "error" in r:
            raise VAgentCmdError(cmd, args, r["error"])



    def cmd_raw(self, data, timeout=CMD_TIMEOUT, success_resp=True):
        """
        Send a raw string to the guest agent and return the response.
        Unlike cmd(), return the raw response dict without performing
        any checks on it.

        @param data: The data to send
        @param timeout: Time duration to wait for response
        @return: The response received
        @raise VAgentLockError: Raised if the lock cannot be acquired
        @raise VAgentSocketError: Raised if a socket error occurs
        @raise VAgentProtocolError: Raised if no response is received
        """
        if not self._acquire_lock():
            raise VAgentLockError("Could not acquire exclusive lock to send "
                                  "data: %r" % data)

        try:
            self._read_objects()
            self._send(data)
            # Return directly for some cmd without any response.
            if not success_resp:
                return {}

            # Read response
            r = self._get_response(timeout)

        finally:
            self._lock.release()

        if r is None:
            raise VAgentProtocolError("Received no response to data: %r" % data)
        return r


    def cmd_obj(self, obj, timeout=CMD_TIMEOUT):
        """
        Transform a Python object to JSON, send the resulting string to
        the guest agent, and return the response.
        Unlike cmd(), return the raw response dict without performing any
        checks on it.

        @param obj: The object to send
        @param timeout: Time duration to wait for response
        @return: The response received
        @raise VAgentLockError: Raised if the lock cannot be acquired
        @raise VAgentSocketError: Raised if a socket error occurs
        @raise VAgentProtocolError: Raised if no response is received
        """
        return self.cmd_raw(json.dumps(obj) + "\n", timeout)


    def verify_responsive(self):
        """
        Make sure the guest agent is responsive by sending a command.
        """
        cmd = "guest-ping"
        if self._has_command(cmd):
            self.cmd(cmd=cmd, debug=False)


    @error.context_aware
    def shutdown(self, mode=SHUTDOWN_MODE_POWERDOWN):
        """
        Send "guest-shutdown", this cmd would not return any response.

        @param mode: Speicfy shutdown mode, now qemu guest agent supports
                     'powerdown', 'reboot', 'halt' 3 modes.
        @return: True if shutdown cmd is sent successfully, False if
                 'shutdown' is unsupported.
        """
        cmd = "guest-shutdown"
        if not self._has_command(cmd):
            return False

        args = None
        if mode in [self.SHUTDOWN_MODE_POWERDOWN, self.SHUTDOWN_MODE_REBOOT,
                    self.SHUTDOWN_MODE_HALT]:
            args = {"mode": mode}
        self.cmd(cmd=cmd, args=args, success_resp=False)
        return True


    @error.context_aware
    def sync(self):
        """
        Sync guest agent with cmd 'guest-sync'.
        """
        cmd = "guest-sync"
        if not self._has_command(cmd):
            return

        rnd_num = random.randint(1000, 9999)
        args = {"id": rnd_num}
        ret = self.cmd(cmd, args=args)
        if ret != rnd_num:
            raise VAgentSyncError(self.vm.name)


    @error.context_aware
    def suspend(self, mode=SUSPEND_MODE_RAM):
        """
        This function tries to execute the scripts provided by the pm-utils
        package via guest agent interface. If it's not available, the suspend
        operation will be performed by manually writing to a sysfs file.

        NOTE: 1) For the best results it's strongly recommended to have the
                 pm-utils package installed in the guest.
              2) The 'ram' and 'hybrid' mode require QEMU to support the
                 'system_wakeup' command.  Thus, it's *required* to query QEMU
                 for the presence of the 'system_wakeup' command before issuing
                 guest agent command.

        @param mode: Specify suspend mode, could be one of 'disk', 'ram',
                     'hybrid'.
        @return: True if shutdown cmd is sent successfully, False if
                 'suspend' is unsupported.
        @raise VAgentSuspendUnknownModeError: Raise if mode is not supported.
        """
        if not mode in [self.SUSPEND_MODE_DISK, self.SUSPEND_MODE_RAM,
                        self.SUSPEND_MODE_HYBRID]:
            raise VAgentSuspendUnknownModeError("Not supported suspend mode '%s'" %
                                          mode)

        error.context("Suspend guest '%s' to '%s'" % (self.vm.name, mode))
        cmd = "guest-suspend-%s" % mode
        if not self._has_command(cmd):
            return False

        # verify QEMU monitor has 'system_wakeup' command.
        self.vm.monitor.verify_supported_cmd("system_wakeup")

        # First, sync with guest.
        self.sync()

        # Then send suspend cmd.
        self.cmd(cmd=cmd, success_resp=False)

        return True


    def get_fsfreeze_status(self):
        """
        Get guest 'fsfreeze' status. The status could be 'frozen' or 'thawed'.
        """
        cmd = "guest-fsfreeze-status"
        if self._has_command(cmd):
            return self.cmd(cmd=cmd)


    def verify_fsfreeze_status(self, expected):
        """
        Verify the guest agent fsfreeze status is same as expected, if not,
        raise a VAgentFreezeStatusError.

        @param expected: The expected status.
        @raise VAgentFreezeStatusError: Raise if the guest fsfreeze status is
                unexpected.
        """
        status = self.get_fsfreeze_status()
        if status != expected:
            raise VAgentFreezeStatusError(self.vm, status, expected)


    @error.context_aware
    def fsfreeze(self, check_status=True):
        """
        Freeze File system on guest.

        @param check_status: Force this function to check the fsreeze status
                             before/after sending cmd.
        @return: Frozen FS number if cmd succeed, -1 if guest agent doesn't
                 support fsfreeze cmd.
        """
        error.context("Freeze all FS in guest '%s'" % self.vm.name)
        if check_status:
            self.verify_fsfreeze_status(self.FSFREEZE_STATUS_THAWED)

        cmd = "guest-fsfreeze-freeze"
        if self._has_command(cmd):
            ret = self.cmd(cmd=cmd)
            if check_status:
                try:
                    self.verify_fsfreeze_status(self.FSFREEZE_STATUS_FROZEN)
                except VAgentFreezeStatusError:
                    # When the status is incorrect, reset fsfreeze status to
                    # 'thawed'.
                    self.cmd(cmd="guest-fsreeze-thaw")
                    raise
            return ret
        return -1


    @error.context_aware
    def fsthaw(self, check_status=True):
        """
        Thaw File system on guest.

        @param check_status: Force this function to check the fsreeze status
                             before/after sending cmd.
        @return: Thaw FS number if cmd succeed, -1 if guest agent doesn't
                 support fsfreeze cmd.
        """
        error.context("thaw all FS in guest '%s'" % self.vm.name)
        if check_status:
            self.verify_fsfreeze_status(self.FSFREEZE_STATUS_FROZEN)

        cmd = "guest-fsfreeze-thaw"
        if self._has_command(cmd):
            ret = self.cmd(cmd=cmd)
            if check_status:
                try:
                    self.verify_fsfreeze_status(self.FSFREEZE_STATUS_THAWED)
                except VAgentFreezeStatusError:
                    # When the status is incorrect, reset fsfreeze status to
                    # 'thawed'.
                    self.cmd(cmd=cmd)
                    raise
            return ret
        return -1
