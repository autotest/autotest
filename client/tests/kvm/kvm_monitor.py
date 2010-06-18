"""
Interfaces to the QEMU monitor.

@copyright: 2008-2010 Red Hat Inc.
"""

import socket, time, threading, logging
import kvm_utils


class MonitorError(Exception):
    pass


class MonitorConnectError(MonitorError):
    pass


class MonitorSendError(MonitorError):
    pass


class MonitorLockError(MonitorError):
    pass


class MonitorProtocolError(MonitorError):
    pass


class Monitor:
    """
    Common code for monitor classes.
    """

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
        self._socket.setblocking(False)

        try:
            self._socket.connect(filename)
        except socket.error:
            raise MonitorConnectError("Could not connect to monitor socket")


    def __del__(self):
        # Automatically close the connection when the instance is garbage
        # collected
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except socket.error:
            pass
        self._socket.close()


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


    def _acquire_lock(self, timeout=20):
        end_time = time.time() + timeout
        while time.time() < end_time:
            if self._lock.acquire(False):
                return True
            time.sleep(0.05)
        return False


    def _recvall(self):
        s = ""
        while True:
            try:
                data = self._socket.recv(1024)
            except socket.error:
                break
            if not data:
                break
            s += data
        return s


class HumanMonitor(Monitor):
    """
    Wraps "human monitor" commands.
    """

    def __init__(self, name, filename, suppress_exceptions=False):
        """
        Connect to the monitor socket and find the (qemu) prompt.

        @param name: Monitor identifier (a string)
        @param filename: Monitor socket filename
        @raise MonitorConnectError: Raised if the connection fails and
                suppress_exceptions is False
        @raise MonitorProtocolError: Raised if the initial (qemu) prompt isn't
                found and suppress_exceptions is False
        @note: Other exceptions may be raised.  See _get_command_output's
                docstring.
        """
        try:
            Monitor.__init__(self, name, filename)

            self.protocol = "human"

            # Find the initial (qemu) prompt
            s, o = self._read_up_to_qemu_prompt(20)
            if not s:
                raise MonitorProtocolError("Could not find (qemu) prompt "
                                           "after connecting to monitor. "
                                           "Output so far: %r" % o)

            # Save the output of 'help' for future use
            self._help_str = self._get_command_output("help")

        except MonitorError, e:
            if suppress_exceptions:
                logging.warn(e)
            else:
                raise


    # Private methods

    def _read_up_to_qemu_prompt(self, timeout=20):
        o = ""
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                data = self._socket.recv(1024)
                if not data:
                    break
                o += data
                if o.splitlines()[-1].split()[-1] == "(qemu)":
                    return True, "\n".join(o.splitlines()[:-1])
            except (socket.error, IndexError):
                time.sleep(0.01)
        return False, "\n".join(o.splitlines())


    def _send_command(self, command):
        """
        Send a command without waiting for output.

        @param command: Command to send
        @return: True if successful, False otherwise
        @raise MonitorLockError: Raised if the lock cannot be acquired
        @raise MonitorSendError: Raised if the command cannot be sent
        """
        if not self._acquire_lock(20):
            raise MonitorLockError("Could not acquire exclusive lock to send "
                                   "monitor command '%s'" % command)

        try:
            try:
                self._socket.sendall(command + "\n")
            except socket.error:
                raise MonitorSendError("Could not send monitor command '%s'" %
                                       command)

        finally:
            self._lock.release()


    def _get_command_output(self, command, timeout=20):
        """
        Send command to the monitor.

        @param command: Command to send to the monitor
        @param timeout: Time duration to wait for the (qemu) prompt to return
        @return: Output received from the monitor
        @raise MonitorLockError: Raised if the lock cannot be acquired
        @raise MonitorSendError: Raised if the command cannot be sent
        @raise MonitorProtocolError: Raised if the (qemu) prompt cannot be
                found after sending the command
        """
        if not self._acquire_lock(20):
            raise MonitorLockError("Could not acquire exclusive lock to send "
                                   "monitor command '%s'" % command)

        try:
            # Read any data that might be available
            self._recvall()
            # Send command
            self._send_command(command)
            # Read output
            s, o = self._read_up_to_qemu_prompt(timeout)
            # Remove command echo from output
            o = "\n".join(o.splitlines()[1:])
            # Report success/failure
            if s:
                return o
            else:
                msg = ("Could not find (qemu) prompt after command '%s'. "
                       "Output so far: %r" % (command, o))
                raise MonitorProtocolError(msg)

        finally:
            self._lock.release()


    # Public methods

    def is_responsive(self):
        """
        Make sure the monitor is responsive by sending a command.

        @return: True if responsive, False otherwise
        """
        try:
            self._get_command_output("help")
            return True
        except MonitorError:
            return False


    # Command wrappers
    # Notes:
    # - All of the following commands raise exceptions in a similar manner to
    #   cmd() and _get_command_output().
    # - A command wrapper should use self._help_str if it requires information
    #   about the monitor's capabilities.

    def cmd(self, command, timeout=20):
        """
        Send a simple command with no parameters and return its output.
        Should only be used for commands that take no parameters and are
        implemented under the same name for both the human and QMP monitors.

        @param command: Command to send
        @param timeout: Time duration to wait for (qemu) prompt after command
        @return: The output of the command
        @raise MonitorLockError: Raised if the lock cannot be acquired
        @raise MonitorSendError: Raised if the command cannot be sent
        @raise MonitorProtocolError: Raised if the (qemu) prompt cannot be
                found after sending the command
        """
        return self._get_command_output(command, timeout)


    def quit(self):
        """
        Send "quit" without waiting for output.
        """
        self._send_command("quit")


    def info(self, what):
        """
        Request info about something and return the output.
        """
        return self._get_command_output("info %s" % what)


    def query(self, what):
        """
        Alias for info.
        """
        return self.info(what)


    def screendump(self, filename):
        """
        Request a screendump.

        @param filename: Location for the screendump
        @return: The command's output
        """
        return self._get_command_output("screendump %s" % filename)


    def migrate(self, uri, full_copy=False, incremental_copy=False, wait=False):
        """
        Migrate.

        @param uri: destination URI
        @param full_copy: If true, migrate with full disk copy
        @param incremental_copy: If true, migrate with incremental disk copy
        @param wait: If true, wait for completion
        @return: The command's output
        """
        logging.debug("Migrating to: %s" % uri)
        cmd = "migrate"
        if not wait:
            cmd += " -d"
        if full_copy:
            cmd += " -b"
        if incremental_copy:
            cmd += " -i"
        cmd += " %s" % uri
        return self._get_command_output(cmd)


    def migrate_set_speed(self, value):
        """
        Set maximum speed (in bytes/sec) for migrations.

        @param value: Speed in bytes/sec
        @return: The command's output
        """
        return self._get_command_output("migrate_set_speed %s" % value)


    def sendkey(self, keystr, hold_time=1):
        """
        Send key combination to VM.

        @param keystr: Key combination string
        @param hold_time: Hold time in ms (should normally stay 1 ms)
        @return: The command's output
        """
        return self._get_command_output("sendkey %s %s" % (keystr, hold_time))


    def mouse_move(self, dx, dy):
        """
        Move mouse.

        @param dx: X amount
        @param dy: Y amount
        @return: The command's output
        """
        return self._get_command_output("mouse_move %d %d" % (dx, dy))


    def mouse_button(self, state):
        """
        Set mouse button state.

        @param state: Button state (1=L, 2=M, 4=R)
        @return: The command's output
        """
        return self._get_command_output("mouse_button %d" % state)
