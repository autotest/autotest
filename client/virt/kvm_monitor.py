"""
Interfaces to the QEMU monitor.

@copyright: 2008-2010 Red Hat Inc.
"""

import socket, time, threading, logging, select, re, os
import virt_utils, virt_passfd_setup
from autotest.client.shared import utils
try:
    import json
except ImportError:
    logging.warning("Could not import json module. "
                    "QMP monitor functionality disabled.")


class MonitorError(Exception):
    pass


class MonitorConnectError(MonitorError):
    pass


class MonitorSocketError(MonitorError):
    def __init__(self, msg, e):
        Exception.__init__(self, msg, e)
        self.msg = msg
        self.e = e

    def __str__(self):
        return "%s    (%s)" % (self.msg, self.e)


class MonitorLockError(MonitorError):
    pass


class MonitorProtocolError(MonitorError):
    pass


class MonitorNotSupportedError(MonitorError):
    pass


class QMPCmdError(MonitorError):
    def __init__(self, cmd, qmp_args, data):
        MonitorError.__init__(self, cmd, qmp_args, data)
        self.cmd = cmd
        self.qmp_args = qmp_args
        self.data = data

    def __str__(self):
        return ("QMP command %r failed    (arguments: %r,    "
                "error message: %r)" % (self.cmd, self.qmp_args, self.data))


class Monitor:
    """
    Common code for monitor classes.
    """

    ACQUIRE_LOCK_TIMEOUT = 20
    DATA_AVAILABLE_TIMEOUT = 0

    def __init__(self, name, filename):
        """
        Initialize the instance.

        @param name: Monitor identifier (a string)
        @param filename: Monitor socket filename
        @raise MonitorConnectError: Raised if the connection fails
        """
        self.name = name
        self.filename = filename
        self._lock = threading.RLock()
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._passfd = None
        self._supported_cmds = []
        self.debug_log = False
        self.log_file = os.path.basename(self.filename + ".log")

        try:
            self._socket.connect(filename)
        except socket.error:
            raise MonitorConnectError("Could not connect to monitor socket")


    def __del__(self):
        # Automatically close the connection when the instance is garbage
        # collected
        self._close_sock()


    # The following two functions are defined to make sure the state is set
    # exclusively by the constructor call as specified in __getinitargs__().

    def __getstate__(self):
        pass


    def __setstate__(self, state):
        pass


    def __getinitargs__(self):
        # Save some information when pickling -- will be passed to the
        # constructor upon unpickling
        return self.name, self.filename, True


    def _close_sock(self):
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except socket.error:
            pass
        self._socket.close()


    def _acquire_lock(self, timeout=ACQUIRE_LOCK_TIMEOUT):
        end_time = time.time() + timeout
        while time.time() < end_time:
            if self._lock.acquire(False):
                return True
            time.sleep(0.05)
        return False


    def _data_available(self, timeout=DATA_AVAILABLE_TIMEOUT):
        timeout = max(0, timeout)
        try:
            return bool(select.select([self._socket], [], [], timeout)[0])
        except socket.error, e:
            raise MonitorSocketError("Verifying data on monitor socket", e)


    def _recvall(self):
        s = ""
        while self._data_available():
            try:
                data = self._socket.recv(1024)
            except socket.error, e:
                raise MonitorSocketError("Could not receive data from monitor",
                                         e)
            if not data:
                break
            s += data
        return s


    def _has_command(self, cmd):
        """
        Check wheter kvm monitor support 'cmd'.

        @param cmd: command string which will be checked.

        @return: True if cmd is supported, False if not supported.
        """
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
            logging.debug("(monitor %s) Sending command '%s' %s",
                          self.name, cmd, extra_str)


    def _log_lines(self, log_str):
        """
        Record monitor cmd/output in log file.
        """
        try:
            for l in log_str.splitlines():
                virt_utils.log_line(self.log_file, l)
        except Exception:
            pass


    def is_responsive(self):
        """
        Return True iff the monitor is responsive.
        """
        try:
            self.verify_responsive()
            return True
        except MonitorError:
            return False


class HumanMonitor(Monitor):
    """
    Wraps "human monitor" commands.
    """

    PROMPT_TIMEOUT = 20
    CMD_TIMEOUT = 20

    def __init__(self, name, filename, suppress_exceptions=False):
        """
        Connect to the monitor socket and find the (qemu) prompt.

        @param name: Monitor identifier (a string)
        @param filename: Monitor socket filename
        @raise MonitorConnectError: Raised if the connection fails and
                suppress_exceptions is False
        @raise MonitorProtocolError: Raised if the initial (qemu) prompt isn't
                found and suppress_exceptions is False
        @note: Other exceptions may be raised.  See cmd()'s
                docstring.
        """
        try:
            Monitor.__init__(self, name, filename)

            self.protocol = "human"

            # Find the initial (qemu) prompt
            s, o = self._read_up_to_qemu_prompt()
            if not s:
                raise MonitorProtocolError("Could not find (qemu) prompt "
                                           "after connecting to monitor. "
                                           "Output so far: %r" % o)

            self._get_supported_cmds()

        except MonitorError, e:
            self._close_sock()
            if suppress_exceptions:
                logging.warn(e)
            else:
                raise


    # Private methods

    def _read_up_to_qemu_prompt(self, timeout=PROMPT_TIMEOUT):
        s = ""
        end_time = time.time() + timeout
        while self._data_available(end_time - time.time()):
            data = self._recvall()
            if not data:
                break
            s += data
            try:
                lines = s.splitlines()
                if lines[-1].split()[-1] == "(qemu)":
                    self._log_lines("\n".join(lines[1:]))
                    return True, "\n".join(lines[:-1])
            except IndexError:
                continue
        if s:
            try:
                self._log_lines(s.splitlines()[1:])
            except IndexError:
                pass
        return False, "\n".join(s.splitlines())


    def _send(self, cmd):
        """
        Send a command without waiting for output.

        @param cmd: Command to send
        @raise MonitorLockError: Raised if the lock cannot be acquired
        @raise MonitorSocketError: Raised if a socket error occurs
        """
        if not self._acquire_lock():
            raise MonitorLockError("Could not acquire exclusive lock to send "
                                   "monitor command '%s'" % cmd)

        try:
            try:
                self._socket.sendall(cmd + "\n")
                self._log_lines(cmd)
            except socket.error, e:
                raise MonitorSocketError("Could not send monitor command %r" %
                                         cmd, e)

        finally:
            self._lock.release()


    def _get_supported_cmds(self):
        """
        Get supported human monitor cmds list.
        """
        cmds = self.cmd("help", debug=False)
        if cmds:
            cmd_list = re.findall("^(.*?) ", cmds, re.M)
            self._supported_cmds = [c for c in cmd_list if c]

        if not self._supported_cmds:
            logging.warn("Could not get supported monitor cmds list")


    def _log_response(self, cmd, resp, debug=True):
        """
        Print log message for monitor cmd's response.

        @param cmd: Command string.
        @param resp: Response from monitor command.
        @param debug: Whether to print the commands.
        """
        if self.debug_log or debug:
            logging.debug("(monitor %s) Response to '%s'", self.name, cmd)
            for l in resp.splitlines():
                logging.debug("(monitor %s)    %s", self.name, l)


    # Public methods

    def cmd(self, cmd, timeout=CMD_TIMEOUT, debug=True, fd=None):
        """
        Send command to the monitor.

        @param cmd: Command to send to the monitor
        @param timeout: Time duration to wait for the (qemu) prompt to return
        @param debug: Whether to print the commands being sent and responses
        @return: Output received from the monitor
        @raise MonitorLockError: Raised if the lock cannot be acquired
        @raise MonitorSocketError: Raised if a socket error occurs
        @raise MonitorProtocolError: Raised if the (qemu) prompt cannot be
                found after sending the command
        """
        self._log_command(cmd, debug)
        if not self._acquire_lock():
            raise MonitorLockError("Could not acquire exclusive lock to send "
                                   "monitor command '%s'" % cmd)

        try:
            # Read any data that might be available
            self._recvall()
            if fd is not None:
                if self._passfd is None:
                    self._passfd = virt_passfd_setup.import_passfd()
                # If command includes a file descriptor, use passfd module
                self._passfd.sendfd(self._socket, fd, "%s\n" % cmd)
            else:
                # Send command
                self._send(cmd)
            # Read output
            s, o = self._read_up_to_qemu_prompt(timeout)
            # Remove command echo from output
            o = "\n".join(o.splitlines()[1:])
            # Report success/failure
            if s:
                if o:
                    self._log_response(cmd, o, debug)
                return o
            else:
                msg = ("Could not find (qemu) prompt after command '%s'. "
                       "Output so far: %r" % (cmd, o))
                raise MonitorProtocolError(msg)

        finally:
            self._lock.release()


    def verify_responsive(self):
        """
        Make sure the monitor is responsive by sending a command.
        """
        self.cmd("info status", debug=False)


    def get_status(self):
        return self.cmd("info status", debug=False)


    def verify_status(self, status):
        """
        Verify VM status

        @param status: Optional VM status, 'running' or 'paused'
        @return: return True if VM status is same as we expected
        """
        return (status in self.get_status())


    # Command wrappers
    # Notes:
    # - All of the following commands raise exceptions in a similar manner to
    #   cmd().
    # - A command wrapper should use self._has_command if it requires
    #    information about the monitor's capabilities.
    def send_args_cmd(self, cmdlines, timeout=CMD_TIMEOUT, convert=True):
        """
        Send a command with/without parameters and return its output.
        Have same effect with cmd function.
        Implemented under the same name for both the human and QMP monitors.
        Command with parameters should in following format e.g.:
        'memsave val=0 size=10240 filename=memsave'
        Command without parameter: 'sendkey ctrl-alt-f1'

        @param cmdlines: Commands send to qemu which is seperated by ";". For
                         command with parameters command should send in a string
                         with this format:
                         $command $arg_name=$arg_value $arg_name=$arg_value
        @param timeout: Time duration to wait for (qemu) prompt after command
        @param convert: If command need to convert. For commands such as:
                        $command $arg_value
        @return: The output of the command
        @raise MonitorLockError: Raised if the lock cannot be acquired
        @raise MonitorSendError: Raised if the command cannot be sent
        @raise MonitorProtocolError: Raised if the (qemu) prompt cannot be
                found after sending the command
        """
        cmd_output = ""
        for cmdline in cmdlines.split(";"):
            logging.info(cmdline)
            if not convert:
                return self.cmd(cmdline, timeout)
            if "=" in cmdline:
                command = cmdline.split()[0]
                cmdargs = " ".join(cmdline.split()[1:]).split(",")
                for arg in cmdargs:
                    command += " " + arg.split("=")[-1]
            else:
                command = cmdline
            cmd_output += self.cmd(command, timeout)
        return cmd_output



    def quit(self):
        """
        Send "quit" without waiting for output.
        """
        self._send("quit")


    def info(self, what, debug=True):
        """
        Request info about something and return the output.
        @param debug: Whether to print the commands being sent and responses
        """
        return self.cmd("info %s" % what, debug=debug)


    def query(self, what):
        """
        Alias for info.
        """
        return self.info(what)


    def screendump(self, filename, debug=True):
        """
        Request a screendump.

        @param filename: Location for the screendump
        @return: The command's output
        """
        return self.cmd(cmd="screendump %s" % filename, debug=debug)


    def set_link(self, name, up):
        """
        Set link up/down.

        @param name: Link name
        @param up: Bool value, True=set up this link, False=Set down this link
        @return: The response to the command
        """
        set_link_cmd = "set_link"

        # set_link in RHEL5 host use "up|down" instead of "on|off" which is
        # used in RHEL6 host and Fedora host. So here find out the string
        # this monitor accept.
        o = self.cmd("help %s" % set_link_cmd)
        try:
            on_str, off_str = re.findall("(\w+)\|(\w+)", o)[0]
        except IndexError:
            # take a default value if can't get on/off string from monitor.
            on_str, off_str = "on", "off"

        status = off_str
        if up:
            status = on_str
        return self.cmd("%s %s %s" % (set_link_cmd, name, status))


    def live_snapshot(self, device, snapshot_file, snapshot_format="qcow2"):
        """
        Take a live disk snapshot.

        @param device: device id of base image
        @param snapshot_file: image file name of snapshot
        @param snapshot_format: image format of snapshot

        @return: The response to the command
        """
        cmd = ("snapshot_blkdev %s %s %s" %
               (device, snapshot_file, snapshot_format))
        return self.cmd(cmd)


    def migrate(self, uri, full_copy=False, incremental_copy=False, wait=False):
        """
        Migrate.

        @param uri: destination URI
        @param full_copy: If true, migrate with full disk copy
        @param incremental_copy: If true, migrate with incremental disk copy
        @param wait: If true, wait for completion
        @return: The command's output
        """
        cmd = "migrate"
        if not wait:
            cmd += " -d"
        if full_copy:
            cmd += " -b"
        if incremental_copy:
            cmd += " -i"
        cmd += " %s" % uri
        return self.cmd(cmd)


    def migrate_set_speed(self, value):
        """
        Set maximum speed (in bytes/sec) for migrations.

        @param value: Speed in bytes/sec
        @return: The command's output
        """
        return self.cmd("migrate_set_speed %s" % value)


    def migrate_set_downtime(self, value):
        """
        Set maximum tolerated downtime (in seconds) for migration.

        @param: value: maximum downtime (in seconds)
        @return: The command's output
        """
        return self.cmd("migrate_set_downtime %s" % value)


    def sendkey(self, keystr, hold_time=1):
        """
        Send key combination to VM.

        @param keystr: Key combination string
        @param hold_time: Hold time in ms (should normally stay 1 ms)
        @return: The command's output
        """
        return self.cmd("sendkey %s %s" % (keystr, hold_time))


    def mouse_move(self, dx, dy):
        """
        Move mouse.

        @param dx: X amount
        @param dy: Y amount
        @return: The command's output
        """
        return self.cmd("mouse_move %d %d" % (dx, dy))


    def mouse_button(self, state):
        """
        Set mouse button state.

        @param state: Button state (1=L, 2=M, 4=R)
        @return: The command's output
        """
        return self.cmd("mouse_button %d" % state)


    def getfd(self, fd, name):
        """
        Receives a file descriptor

        @param fd: File descriptor to pass to QEMU
        @param name: File descriptor name (internal to QEMU)
        @return: The command's output
        """
        return self.cmd("getfd %s" % name, fd=fd)


class QMPMonitor(Monitor):
    """
    Wraps QMP monitor commands.
    """

    READ_OBJECTS_TIMEOUT = 5
    CMD_TIMEOUT = 20
    RESPONSE_TIMEOUT = 20
    PROMPT_TIMEOUT = 20

    def __init__(self, name, filename, suppress_exceptions=False):
        """
        Connect to the monitor socket, read the greeting message and issue the
        qmp_capabilities command.  Also make sure the json module is available.

        @param name: Monitor identifier (a string)
        @param filename: Monitor socket filename
        @raise MonitorConnectError: Raised if the connection fails and
                suppress_exceptions is False
        @raise MonitorProtocolError: Raised if the no QMP greeting message is
                received and suppress_exceptions is False
        @raise MonitorNotSupportedError: Raised if json isn't available and
                suppress_exceptions is False
        @note: Other exceptions may be raised if the qmp_capabilities command
                fails.  See cmd()'s docstring.
        """
        try:
            Monitor.__init__(self, name, filename)

            self.protocol = "qmp"
            self._greeting = None
            self._events = []

            # Make sure json is available
            try:
                json
            except NameError:
                raise MonitorNotSupportedError("QMP requires the json module "
                                               "(Python 2.6 and up)")

            # Read greeting message
            end_time = time.time() + 20
            while time.time() < end_time:
                for obj in self._read_objects():
                    if "QMP" in obj:
                        self._greeting = obj
                        break
                if self._greeting:
                    break
                time.sleep(0.1)
            else:
                raise MonitorProtocolError("No QMP greeting message received")

            # Issue qmp_capabilities
            self.cmd("qmp_capabilities")

            self._get_supported_cmds()

        except MonitorError, e:
            self._close_sock()
            if suppress_exceptions:
                logging.warn(e)
            else:
                raise


    # Private methods

    def _build_cmd(self, cmd, args=None, id=None):
        obj = {"execute": cmd}
        if args is not None:
            obj["arguments"] = args
        if id is not None:
            obj["id"] = id
        return obj


    def _read_objects(self, timeout=READ_OBJECTS_TIMEOUT):
        """
        Read lines from the monitor and try to decode them.
        Stop when all available lines have been successfully decoded, or when
        timeout expires.  If any decoded objects are asynchronous events, store
        them in self._events.  Return all decoded objects.

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
        # Keep track of asynchronous events
        self._events += [obj for obj in objs if "event" in obj]
        return objs


    def _send(self, data):
        """
        Send raw data without waiting for response.

        @param data: Data to send
        @raise MonitorSocketError: Raised if a socket error occurs
        """
        try:
            self._socket.sendall(data)
            self._log_lines(str(data))
        except socket.error, e:
            raise MonitorSocketError("Could not send data: %r" % data, e)


    def _get_response(self, id=None, timeout=RESPONSE_TIMEOUT):
        """
        Read a response from the QMP monitor.

        @param id: If not None, look for a response with this id
        @param timeout: Time duration to wait for response
        @return: The response dict, or None if none was found
        """
        end_time = time.time() + timeout
        while self._data_available(end_time - time.time()):
            for obj in self._read_objects():
                if isinstance(obj, dict):
                    if id is not None and obj.get("id") != id:
                        continue
                    if "return" in obj or "error" in obj:
                        return obj


    def _get_supported_cmds(self):
        """
        Get supported qmp cmds list.
        """
        cmds = self.cmd("query-commands", debug=False)
        if cmds:
            self._supported_cmds = [n["name"] for n in cmds if
                                    n.has_key("name")]

        if not self._supported_cmds:
            logging.warn("Could not get supported monitor cmds list")


    def _log_response(self, cmd, resp, debug=True):
        """
        Print log message for monitor cmd's response.

        @param cmd: Command string.
        @param resp: Response from monitor command.
        @param debug: Whether to print the commands.
        """
        def _log_output(o, indent=0):
            logging.debug("(monitor %s)    %s%s",
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
            logging.debug("(monitor %s) Response to '%s' "
                          "(re-formated)", self.name, cmd)
            if isinstance(resp, dict):
                _dump_dict(resp)
            elif isinstance(resp, list):
                _dump_list(resp)
            else:
                for l in str(resp).splitlines():
                    _log_output(l)


    # Public methods

    def cmd(self, cmd, args=None, timeout=CMD_TIMEOUT, debug=True, fd=None):
        """
        Send a QMP monitor command and return the response.

        Note: an id is automatically assigned to the command and the response
        is checked for the presence of the same id.

        @param cmd: Command to send
        @param args: A dict containing command arguments, or None
        @param timeout: Time duration to wait for response
        @param debug: Whether to print the commands being sent and responses
        @param fd: file object or file descriptor to pass

        @return: The response received

        @raise MonitorLockError: Raised if the lock cannot be acquired
        @raise MonitorSocketError: Raised if a socket error occurs
        @raise MonitorProtocolError: Raised if no response is received
        @raise QMPCmdError: Raised if the response is an error message
                            (the exception's args are (cmd, args, data)
                             where data is the error data)
        """
        self._log_command(cmd, debug)
        if not self._acquire_lock():
            raise MonitorLockError("Could not acquire exclusive lock to send "
                                   "QMP command '%s'" % cmd)

        try:
            # Read any data that might be available
            self._read_objects()
            # Send command
            id = virt_utils.generate_random_string(8)
            cmdobj = self._build_cmd(cmd, args, id)
            if fd is not None:
                if self._passfd is None:
                    self._passfd = virt_passfd_setup.import_passfd()
                # If command includes a file descriptor, use passfd module
                self._passfd.sendfd(self._socket, fd, json.dumps(cmdobj) + "\n")
            else:
                self._send(json.dumps(cmdobj) + "\n")
            # Read response
            r = self._get_response(id, timeout)
            if r is None:
                raise MonitorProtocolError("Received no response to QMP "
                                           "command '%s', or received a "
                                           "response with an incorrect id"
                                           % cmd)
            if "return" in r:
                ret = r["return"]
                if ret:
                    self._log_response(cmd, ret, debug)
                return ret
            if "error" in r:
                raise QMPCmdError(cmd, args, r["error"])

        finally:
            self._lock.release()


    def cmd_raw(self, data, timeout=CMD_TIMEOUT):
        """
        Send a raw string to the QMP monitor and return the response.
        Unlike cmd(), return the raw response dict without performing any
        checks on it.

        @param data: The data to send
        @param timeout: Time duration to wait for response
        @return: The response received
        @raise MonitorLockError: Raised if the lock cannot be acquired
        @raise MonitorSocketError: Raised if a socket error occurs
        @raise MonitorProtocolError: Raised if no response is received
        """
        if not self._acquire_lock():
            raise MonitorLockError("Could not acquire exclusive lock to send "
                                   "data: %r" % data)

        try:
            self._read_objects()
            self._send(data)
            r = self._get_response(None, timeout)
            if r is None:
                raise MonitorProtocolError("Received no response to data: %r" %
                                           data)
            return r

        finally:
            self._lock.release()


    def cmd_obj(self, obj, timeout=CMD_TIMEOUT):
        """
        Transform a Python object to JSON, send the resulting string to the QMP
        monitor, and return the response.
        Unlike cmd(), return the raw response dict without performing any
        checks on it.

        @param obj: The object to send
        @param timeout: Time duration to wait for response
        @return: The response received
        @raise MonitorLockError: Raised if the lock cannot be acquired
        @raise MonitorSocketError: Raised if a socket error occurs
        @raise MonitorProtocolError: Raised if no response is received
        """
        return self.cmd_raw(json.dumps(obj) + "\n", timeout)


    def cmd_qmp(self, cmd, args=None, id=None, timeout=CMD_TIMEOUT):
        """
        Build a QMP command from the passed arguments, send it to the monitor
        and return the response.
        Unlike cmd(), return the raw response dict without performing any
        checks on it.

        @param cmd: Command to send
        @param args: A dict containing command arguments, or None
        @param id:  An id for the command, or None
        @param timeout: Time duration to wait for response
        @return: The response received
        @raise MonitorLockError: Raised if the lock cannot be acquired
        @raise MonitorSocketError: Raised if a socket error occurs
        @raise MonitorProtocolError: Raised if no response is received
        """
        return self.cmd_obj(self._build_cmd(cmd, args, id), timeout)


    def verify_responsive(self):
        """
        Make sure the monitor is responsive by sending a command.
        """
        self.cmd(cmd="query-status", debug=False)


    def get_status(self):
        """
        Get VM status.

        @return: return VM status
        """
        return self.cmd(cmd="query-status", debug=False)


    def verify_status(self, status):
        """
        Verify VM status

        @param status: Optional VM status, 'running' or 'paused'
        @return: return True if VM status is same as we expected
        """
        o = dict(self.cmd(cmd="query-status", debug=False))
        if status == 'paused':
            return (o['running'] == False)
        if status == 'running':
            return (o['running'] == True)
        if o['status'] == status:
            return True
        return False


    def get_events(self):
        """
        Return a list of the asynchronous events received since the last
        clear_events() call.

        @return: A list of events (the objects returned have an "event" key)
        @raise MonitorLockError: Raised if the lock cannot be acquired
        """
        if not self._acquire_lock():
            raise MonitorLockError("Could not acquire exclusive lock to read "
                                   "QMP events")
        try:
            self._read_objects()
            return self._events[:]
        finally:
            self._lock.release()


    def get_event(self, name):
        """
        Look for an event with the given name in the list of events.

        @param name: The name of the event to look for (e.g. 'RESET')
        @return: An event object or None if none is found
        """
        for e in self.get_events():
            if e.get("event") == name:
                return e


    def human_monitor_cmd(self, cmd="", timeout=CMD_TIMEOUT,
                          debug=True, fd=None):
        """
        Run human monitor command in QMP through human-monitor-command

        @param cmd: human monitor command.
        @param timeout: Time duration to wait for response
        @param debug: Whether to print the commands being sent and responses
        @param fd: file object or file descriptor to pass

        @return: The response to the command
        """
        self._log_command(cmd, extra_str="(via Human Monitor)")

        args = {"command-line": cmd}
        ret = self.cmd("human-monitor-command", args, timeout, False, fd)

        if ret:
            self._log_response(cmd, ret, debug)
        return ret


    def clear_events(self):
        """
        Clear the list of asynchronous events.

        @raise MonitorLockError: Raised if the lock cannot be acquired
        """
        if not self._acquire_lock():
            raise MonitorLockError("Could not acquire exclusive lock to clear "
                                   "QMP event list")
        self._events = []
        self._lock.release()


    def get_greeting(self):
        """
        Return QMP greeting message.
        """
        return self._greeting


    # Command wrappers
    # Note: all of the following functions raise exceptions in a similar manner
    # to cmd().
    def send_args_cmd(self, cmdlines, timeout=CMD_TIMEOUT, convert=True):
        """
        Send a command with/without parameters and return its output.
        Have same effect with cmd function.
        Implemented under the same name for both the human and QMP monitors.
        Command with parameters should in following format e.g.:
        'memsave val=0 size=10240 filename=memsave'
        Command without parameter: 'query-vnc'

        @param cmdlines: Commands send to qemu which is seperated by ";". For
                         command with parameters command should send in a string
                         with this format:
                         $command $arg_name=$arg_value $arg_name=$arg_value
        @param timeout: Time duration to wait for (qemu) prompt after command
        @param convert: If command need to convert. For commands not in standard
                        format such as: $command $arg_value
        @return: The response to the command
        @raise MonitorLockError: Raised if the lock cannot be acquired
        @raise MonitorSendError: Raised if the command cannot be sent
        @raise MonitorProtocolError: Raised if no response is received
        """
        cmd_output = []
        for cmdline in cmdlines.split(";"):
            command = cmdline.split()[0]
            if self._has_command(command):
                if "=" in cmdline:
                    command = cmdline.split()[0]
                    cmdargs = " ".join(cmdline.split()[1:]).split(",")
                    for arg in cmdargs:
                        command += " " + arg.split("=")[-1]
                else:
                    command = cmdline
                cmd_output.append(self.human_monitor_cmd(command))
            else:
                cmdargs = " ".join(cmdline.split()[1:]).split(",")
                args = {}
                for arg in cmdargs:
                    opt = arg.split('=')
                    try:
                        if re.match("^[0-9]+$", opt[1]):
                            value = int(opt[1])
                        elif re.match("^[0-9]+.[0-9]*$", opt[1]):
                            value = float(opt[1])
                        elif "True" in opt[1] or "true" in opt[1]:
                            value = True
                        elif "false" in opt[1] or "False" in opt[1]:
                            value = False
                        else:
                            value = opt[1].strip()
                        args[opt[0].strip()] = value
                    except:
                        logging.debug("Fail to create args, please check cmd")
                cmd_output.append(self.cmd(command, args, timeout=timeout))
        return cmd_output

    def quit(self):
        """
        Send "quit" and return the response.
        """
        return self.cmd("quit")


    def info(self, what):
        """
        Request info about something and return the response.
        """
        cmd = "query-%s" % what
        if self._has_command(cmd):
            return self.cmd("query-%s" % what)
        else:
            cmd = "info %s" % what
            return self.human_monitor_cmd(cmd)


    def query(self, what):
        """
        Alias for info.
        """
        return self.info(what)


    def screendump(self, filename, debug=True):
        """
        Request a screendump.

        @param filename: Location for the screendump
        @param debug: Whether to print the commands being sent and responses

        @return: The response to the command
        """
        if self._has_command("screendump"):
            args = {"filename": filename}
            return self.cmd(cmd="screendump", args=args, debug=debug)
        else:
            cmdline = "screendump %s" % filename
            return self.human_monitor_cmd(cmdline, debug=debug)


    def sendkey(self, keystr, hold_time=1):
        """
        Send key combination to VM.

        @param keystr: Key combination string
        @param hold_time: Hold time in ms (should normally stay 1 ms)

        @return: The response to the command
        """
        return self.human_monitor_cmd("sendkey %s %s" % (keystr, hold_time))


    def migrate(self, uri, full_copy=False, incremental_copy=False, wait=False):
        """
        Migrate.

        @param uri: destination URI
        @param full_copy: If true, migrate with full disk copy
        @param incremental_copy: If true, migrate with incremental disk copy
        @param wait: If true, wait for completion
        @return: The response to the command
        """
        args = {"uri": uri,
                "blk": full_copy,
                "inc": incremental_copy}
        return self.cmd("migrate", args)


    def migrate_set_speed(self, value):
        """
        Set maximum speed (in bytes/sec) for migrations.

        @param value: Speed in bytes/sec
        @return: The response to the command
        """
        value = utils.convert_data_size(value, "M")
        args = {"value": value}
        return self.cmd("migrate_set_speed", args)


    def set_link(self, name, up):
        """
        Set link up/down.

        @param name: Link name
        @param up: Bool value, True=set up this link, False=Set down this link

        @return: The response to the command
        """
        return self.send_args_cmd("set_link name=%s,up=%s" % (name, str(up)))


    def migrate_set_downtime(self, value):
        """
        Set maximum tolerated downtime (in seconds) for migration.

        @param: value: maximum downtime (in seconds)

        @return: The command's output
        """
        val = value * 10**9
        args = {"value": val}
        return self.cmd("migrate_set_downtime", args)


    def live_snapshot(self, device, snapshot_file, snapshot_format="qcow2"):
        """
        Take a live disk snapshot.

        @param device: device id of base image
        @param snapshot_file: image file name of snapshot
        @param snapshot_format: image format of snapshot

        @return: The response to the command
        """
        args = {"device": device,
                "snapshot-file": snapshot_file,
                "format": snapshot_format}
        return self.cmd("blockdev-snapshot-sync", args)


    def getfd(self, fd, name):
        """
        Receives a file descriptor

        @param fd: File descriptor to pass to QEMU
        @param name: File descriptor name (internal to QEMU)

        @return: The response to the command
        """
        args = {"fdname": name}
        return self.cmd("getfd", args, fd=fd)
