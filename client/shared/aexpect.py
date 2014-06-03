#!/usr/bin/python
"""
A class and functions used for running and controlling child processes.

:copyright: 2008-2009 Red Hat Inc.
"""

import os
import sys
import pty
import select
import termios
import fcntl
import tempfile
import logging
import shutil

BASE_DIR = os.path.join('/tmp', 'aexpect')


def clean_tmp_files():
    """
    Remove all aexpect temporary files.
    """
    if os.path.isdir(BASE_DIR):
        shutil.rmtree(BASE_DIR, ignore_errors=True)

# The following helper functions are shared by the server and the client.


def _lock(filename):
    if not os.path.exists(filename):
        open(filename, "w").close()
    fd = os.open(filename, os.O_RDWR)
    fcntl.lockf(fd, fcntl.LOCK_EX)
    return fd


def _unlock(fd):
    fcntl.lockf(fd, fcntl.LOCK_UN)
    os.close(fd)


def _locked(filename):
    try:
        fd = os.open(filename, os.O_RDWR)
    except Exception:
        return False
    try:
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        os.close(fd)
        return True
    fcntl.lockf(fd, fcntl.LOCK_UN)
    os.close(fd)
    return False


def _wait(filename):
    fd = _lock(filename)
    _unlock(fd)


def _makeraw(shell_fd):
    attr = termios.tcgetattr(shell_fd)
    attr[0] &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK |
                 termios.ISTRIP | termios.INLCR | termios.IGNCR |
                 termios.ICRNL | termios.IXON)
    attr[1] &= ~termios.OPOST
    attr[2] &= ~(termios.CSIZE | termios.PARENB)
    attr[2] |= termios.CS8
    attr[3] &= ~(termios.ECHO | termios.ECHONL | termios.ICANON |
                 termios.ISIG | termios.IEXTEN)
    termios.tcsetattr(shell_fd, termios.TCSANOW, attr)


def _makestandard(shell_fd, echo):
    attr = termios.tcgetattr(shell_fd)
    attr[0] &= ~termios.INLCR
    attr[0] &= ~termios.ICRNL
    attr[0] &= ~termios.IGNCR
    attr[1] &= ~termios.OPOST
    if echo:
        attr[3] |= termios.ECHO
    else:
        attr[3] &= ~termios.ECHO
    termios.tcsetattr(shell_fd, termios.TCSANOW, attr)


def _get_filenames(base_dir, a_id):
    return [os.path.join(base_dir, a_id, s) for s in
            "shell-pid", "status", "output", "inpipe", "ctrlpipe",
            "lock-server-running", "lock-client-starting",
            "server-log"]


def _get_reader_filename(base_dir, a_id, reader):
    return os.path.join(base_dir, a_id, "outpipe-%s" % reader)


# The following is the server part of the module.

if __name__ == "__main__":
    a_id = sys.stdin.readline().strip()
    echo = sys.stdin.readline().strip() == "True"
    readers = sys.stdin.readline().strip().split(",")
    command = sys.stdin.readline().strip() + " && echo %s > /dev/null" % a_id

    # Define filenames to be used for communication
    (shell_pid_filename,
     status_filename,
     output_filename,
     inpipe_filename,
     ctrlpipe_filename,
     lock_server_running_filename,
     lock_client_starting_filename,
     log_filename) = _get_filenames(BASE_DIR, a_id)

    logging_format = '%(asctime)s %(levelname)-5.5s| %(message)s'
    date_format = '%m/%d %H:%M:%S'
    logging.basicConfig(filename=log_filename, level=logging.DEBUG,
                        format=logging_format, datefmt=date_format)
    server_log = logging.getLogger()

    server_log.info('Server %s starting with parameters:' % str(a_id))
    server_log.info('echo: %s' % str(echo))
    server_log.info('readers: %s' % str(readers))
    server_log.info('command: %s' % str(command))

    # Populate the reader filenames list
    reader_filenames = [_get_reader_filename(BASE_DIR, a_id, reader)
                        for reader in readers]

    # Set $TERM = dumb
    os.putenv("TERM", "dumb")

    server_log.info('Forking child process for command')
    (shell_pid, shell_fd) = pty.fork()
    if shell_pid == 0:
        # Child process: run the command in a subshell
        if len(command) > 255:
            new_stack = None
            if len(command) > 2000000:
                # Stack size would probably not suffice (and no open files)
                # (1 + len(command) * 4 / 8290304) * 8196
                # 2MB => 8196kb, 4MB => 16392, ...
                new_stack = (1 + len(command) / 2072576) * 8196
                command = "ulimit -s %s\nulimit -n 819200\n%s" % (new_stack,
                                                                  command)
            tmp_dir = os.path.join(BASE_DIR, a_id)
            tmp_file = tempfile.mktemp(suffix='.sh',
                                       prefix='aexpect-', dir=tmp_dir)
            fd_cmd = open(tmp_file, "w")
            fd_cmd.write(command)
            fd_cmd.close()
            os.execv("/bin/bash", ["/bin/bash", "-c", "source %s" % tmp_file])
            os.remove(tmp_file)
        else:
            os.execv("/bin/bash", ["/bin/bash", "-c", command])
    else:
        # Parent process
        server_log.info('Acquiring server lock on %s' % lock_server_running_filename)
        lock_server_running = _lock(lock_server_running_filename)

        # Set terminal echo on/off and disable pre- and post-processing
        _makestandard(shell_fd, echo)

        server_log.info('Opening output file %s' % output_filename)
        output_file = open(output_filename, "w")
        server_log.info('Opening input pipe %s' % inpipe_filename)
        os.mkfifo(inpipe_filename)
        inpipe_fd = os.open(inpipe_filename, os.O_RDWR)
        server_log.info('Opening control pipe %s' % ctrlpipe_filename)
        os.mkfifo(ctrlpipe_filename)
        ctrlpipe_fd = os.open(ctrlpipe_filename, os.O_RDWR)
        # Open output pipes (readers)
        reader_fds = []
        for filename in reader_filenames:
            server_log.info('Opening output pipe %s' % filename)
            os.mkfifo(filename)
            reader_fds.append(os.open(filename, os.O_RDWR))
        server_log.info('Reader fd list: %s' % reader_fds)

        # Write shell PID to file
        server_log.info('Writing shell PID file %s' % shell_pid_filename)
        fileobj = open(shell_pid_filename, "w")
        fileobj.write(str(shell_pid))
        fileobj.close()

        # Print something to stdout so the client can start working
        print "Server %s ready" % a_id
        sys.stdout.flush()

        # Initialize buffers
        buffers = ["" for reader in readers]

        # Read from child and write to files/pipes
        server_log.info('Entering main read loop')
        while True:
            check_termination = False
            # Make a list of reader pipes whose buffers are not empty
            fds = [fd for (i, fd) in enumerate(reader_fds) if buffers[i]]
            # Wait until there's something to do
            r, w, x = select.select([shell_fd, inpipe_fd, ctrlpipe_fd],
                                    fds, [], 0.5)
            # If a reader pipe is ready for writing --
            for (i, fd) in enumerate(reader_fds):
                if fd in w:
                    bytes_written = os.write(fd, buffers[i])
                    buffers[i] = buffers[i][bytes_written:]
            if ctrlpipe_fd in r:
                cmd_len = int(os.read(ctrlpipe_fd, 10))
                data = os.read(ctrlpipe_fd, cmd_len)
                if data == "raw":
                    _makeraw(shell_fd)
                elif data == "standard":
                    _makestandard(shell_fd, echo)
            # If there's data to read from the child process --
            if shell_fd in r:
                try:
                    data = os.read(shell_fd, 16384)
                except OSError:
                    data = ""
                if not data:
                    check_termination = True
                # Remove carriage returns from the data -- they often cause
                # trouble and are normally not needed
                data = data.replace("\r", "")
                output_file.write(data)
                output_file.flush()
                for i in range(len(readers)):
                    buffers[i] += data
            # If os.read() raised an exception or there was nothing to read --
            if check_termination or shell_fd not in r:
                pid, status = os.waitpid(shell_pid, os.WNOHANG)
                if pid:
                    status = os.WEXITSTATUS(status)
                    break
            # If there's data to read from the client --
            if inpipe_fd in r:
                data = os.read(inpipe_fd, 1024)
                os.write(shell_fd, data)

        server_log.info('Out of the main read loop. Writing status to %s' % status_filename)
        fileobj = open(status_filename, "w")
        fileobj.write(str(status))
        fileobj.close()

        # Wait for the client to finish initializing
        _wait(lock_client_starting_filename)

        # Close all files and pipes
        output_file.close()
        os.close(inpipe_fd)
        server_log.info('Closed input pipe')
        for fd in reader_fds:
            os.close(fd)
            server_log.info('Closed reader fd %s' % fd)

        _unlock(lock_server_running)
        server_log.info('Exiting normally')
        sys.exit(0)


# The following is the client part of the module.

import subprocess
import time
import signal
import re
import threading
import utils


class ExpectError(Exception):

    def __init__(self, patterns, output):
        Exception.__init__(self, patterns, output)
        self.patterns = patterns
        self.output = output

    def _pattern_str(self):
        if len(self.patterns) == 1:
            return "pattern %r" % self.patterns[0]
        else:
            return "patterns %r" % self.patterns

    def __str__(self):
        return ("Unknown error occurred while looking for %s    (output: %r)" %
                (self._pattern_str(), self.output))


class ExpectTimeoutError(ExpectError):

    def __str__(self):
        return ("Timeout expired while looking for %s    (output: %r)" %
                (self._pattern_str(), self.output))


class ExpectProcessTerminatedError(ExpectError):

    def __init__(self, patterns, status, output):
        ExpectError.__init__(self, patterns, output)
        self.status = status

    def __str__(self):
        return ("Process terminated while looking for %s    "
                "(status: %s,    output: %r)" % (self._pattern_str(),
                                                 self.status, self.output))


class ShellError(Exception):

    def __init__(self, cmd, output):
        Exception.__init__(self, cmd, output)
        self.cmd = cmd
        self.output = output

    def __str__(self):
        return ("Could not execute shell command %r    (output: %r)" %
                (self.cmd, self.output))


class ShellTimeoutError(ShellError):

    def __str__(self):
        return ("Timeout expired while waiting for shell command to "
                "complete: %r    (output: %r)" % (self.cmd, self.output))


class ShellProcessTerminatedError(ShellError):
    # Raised when the shell process itself (e.g. ssh, netcat, telnet)
    # terminates unexpectedly

    def __init__(self, cmd, status, output):
        ShellError.__init__(self, cmd, output)
        self.status = status

    def __str__(self):
        return ("Shell process terminated while waiting for command to "
                "complete: %r    (status: %s,    output: %r)" %
                (self.cmd, self.status, self.output))


class ShellCmdError(ShellError):
    # Raised when a command executed in a shell terminates with a nonzero
    # exit code (status)

    def __init__(self, cmd, status, output):
        ShellError.__init__(self, cmd, output)
        self.status = status

    def __str__(self):
        return ("Shell command failed: %r    (status: %s,    output: %r)" %
                (self.cmd, self.status, self.output))


class ShellStatusError(ShellError):
    # Raised when the command's exit status cannot be obtained

    def __str__(self):
        return ("Could not get exit status of command: %r    (output: %r)" %
                (self.cmd, self.output))


def run_tail(command, termination_func=None, output_func=None, output_prefix="",
             timeout=1.0, auto_close=True):
    """
    Run a subprocess in the background and collect its output and exit status.

    Run command as a subprocess.  Call output_func with each line of output
    from the subprocess (prefixed by output_prefix).  Call termination_func
    when the subprocess terminates.  Return when timeout expires or when the
    subprocess exits -- whichever occurs first.

    :param command: The shell command to execute
    :param termination_func: A function to call when the process terminates
            (should take an integer exit status parameter)
    :param output_func: A function to call with each line of output from
            the subprocess (should take a string parameter)
    :param output_prefix: A string to pre-pend to each line of the output,
            before passing it to stdout_func
    :param timeout: Time duration (in seconds) to wait for the subprocess to
            terminate before returning
    :param auto_close: If True, close() the instance automatically when its
                reference count drops to zero (default False).

    :return: A Expect object.
    """
    process = Tail(command=command,
                   termination_func=termination_func,
                   output_func=output_func,
                   output_prefix=output_prefix,
                   auto_close=auto_close)

    end_time = time.time() + timeout
    while time.time() < end_time and process.is_alive():
        time.sleep(0.1)

    return process


def run_bg(command, termination_func=None, output_func=None, output_prefix="",
           timeout=1.0, auto_close=True):
    """
    Run a subprocess in the background and collect its output and exit status.

    Run command as a subprocess.  Call output_func with each line of output
    from the subprocess (prefixed by output_prefix).  Call termination_func
    when the subprocess terminates.  Return when timeout expires or when the
    subprocess exits -- whichever occurs first.

    :param command: The shell command to execute
    :param termination_func: A function to call when the process terminates
            (should take an integer exit status parameter)
    :param output_func: A function to call with each line of output from
            the subprocess (should take a string parameter)
    :param output_prefix: A string to pre-pend to each line of the output,
            before passing it to stdout_func
    :param timeout: Time duration (in seconds) to wait for the subprocess to
            terminate before returning
    :param auto_close: If True, close() the instance automatically when its
                reference count drops to zero (default False).

    :return: A Expect object.
    """
    process = Expect(command=command,
                     termination_func=termination_func,
                     output_func=output_func,
                     output_prefix=output_prefix,
                     auto_close=auto_close)

    end_time = time.time() + timeout
    while time.time() < end_time and process.is_alive():
        time.sleep(0.1)

    return process


def run_fg(command, output_func=None, output_prefix="", timeout=1.0):
    """
    Run a subprocess in the foreground and collect its output and exit status.

    Run command as a subprocess.  Call output_func with each line of output
    from the subprocess (prefixed by prefix).  Return when timeout expires or
    when the subprocess exits -- whichever occurs first.  If timeout expires
    and the subprocess is still running, kill it before returning.

    :param command: The shell command to execute
    :param output_func: A function to call with each line of output from
            the subprocess (should take a string parameter)
    :param output_prefix: A string to pre-pend to each line of the output,
            before passing it to stdout_func
    :param timeout: Time duration (in seconds) to wait for the subprocess to
            terminate before killing it and returning

    :return: A 2-tuple containing the exit status of the process and its
            STDOUT/STDERR output.  If timeout expires before the process
            terminates, the returned status is None.
    """
    process = run_bg(command, None, output_func, output_prefix, timeout)
    output = process.get_output()
    if process.is_alive():
        status = None
    else:
        status = process.get_status()
    process.close()
    return (status, output)


class Spawn(object):

    """
    This class is used for spawning and controlling a child process.

    A new instance of this class can either run a new server (a small Python
    program that reads output from the child process and reports it to the
    client and to a text file) or attach to an already running server.
    When a server is started it runs the child process.
    The server writes output from the child's STDOUT and STDERR to a text file.
    The text file can be accessed at any time using get_output().
    In addition, the server opens as many pipes as requested by the client and
    writes the output to them.
    The pipes are requested and accessed by classes derived from Spawn.
    These pipes are referred to as "readers".
    The server also receives input from the client and sends it to the child
    process.
    An instance of this class can be pickled.  Every derived class is
    responsible for restoring its own state by properly defining
    __getinitargs__().

    The first named pipe is used by _tail(), a function that runs in the
    background and reports new output from the child as it is produced.
    The second named pipe is used by a set of functions that read and parse
    output as requested by the user in an interactive manner, similar to
    pexpect.
    When unpickled it automatically
    resumes _tail() if needed.
    """

    def __init__(self, command=None, a_id=None, auto_close=False, echo=False,
                 linesep="\n"):
        """
        Initialize the class and run command as a child process.

        :param command: Command to run, or None if accessing an already running
                server.
        :param a_id: ID of an already running server, if accessing a running
                server, or None if starting a new one.
        :param auto_close: If True, close() the instance automatically when its
                reference count drops to zero (default False).
        :param echo: Boolean indicating whether echo should be initially
                enabled for the pseudo terminal running the subprocess.  This
                parameter has an effect only when starting a new server.
        :param linesep: Line separator to be appended to strings sent to the
                child process by sendline().
        """
        self.a_id = a_id or utils.generate_random_string(8)
        self.log_file = None

        base_dir = os.path.join(BASE_DIR, self.a_id)

        # Define filenames for communication with server
        try:
            os.makedirs(base_dir)
        except Exception:
            pass
        (self.shell_pid_filename,
         self.status_filename,
         self.output_filename,
         self.inpipe_filename,
         self.ctrlpipe_filename,
         self.lock_server_running_filename,
         self.lock_client_starting_filename,
         self.server_log_filename) = _get_filenames(BASE_DIR,
                                                    self.a_id)

        self.command = command

        # Remember some attributes
        self.auto_close = auto_close
        self.echo = echo
        self.linesep = linesep

        # Make sure the 'readers' and 'close_hooks' attributes exist
        if not hasattr(self, "readers"):
            self.readers = []
        if not hasattr(self, "close_hooks"):
            self.close_hooks = []

        # Define the reader filenames
        self.reader_filenames = dict(
            (reader, _get_reader_filename(BASE_DIR, self.a_id, reader))
            for reader in self.readers)

        # Let the server know a client intends to open some pipes;
        # if the executed command terminates quickly, the server will wait for
        # the client to release the lock before exiting
        lock_client_starting = _lock(self.lock_client_starting_filename)

        # Start the server (which runs the command)
        if command:
            sub = subprocess.Popen("%s %s" % (sys.executable, __file__),
                                   shell=True,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
            # Send parameters to the server
            sub.stdin.write("%s\n" % self.a_id)
            sub.stdin.write("%s\n" % echo)
            sub.stdin.write("%s\n" % ",".join(self.readers))
            sub.stdin.write("%s\n" % command)
            # Wait for the server to complete its initialization
            while "Server %s ready" % self.a_id not in sub.stdout.readline():
                pass

        # Open the reading pipes
        self.reader_fds = {}
        try:
            assert(_locked(self.lock_server_running_filename))
            for reader, filename in self.reader_filenames.items():
                self.reader_fds[reader] = os.open(filename, os.O_RDONLY)
        except Exception:
            pass

        # Allow the server to continue
        _unlock(lock_client_starting)

    # The following two functions are defined to make sure the state is set
    # exclusively by the constructor call as specified in __getinitargs__().
    def __reduce__(self):
        return self.__class__, (self.__getinitargs__())

    def __getstate__(self):
        pass

    def __setstate__(self, state):
        pass

    def __getinitargs__(self):
        # Save some information when pickling -- will be passed to the
        # constructor upon unpickling
        return (None, self.a_id, self.auto_close, self.echo, self.linesep)

    def __del__(self):
        self._close_reader_fds()
        if self.auto_close:
            self.close()

    def _add_reader(self, reader):
        """
        Add a reader whose file descriptor can be obtained with _get_fd().
        Should be called before __init__().  Intended for use by derived
        classes.

        :param reader: The name of the reader.
        """
        if not hasattr(self, "readers"):
            self.readers = []
        self.readers.append(reader)

    def _add_close_hook(self, hook):
        """
        Add a close hook function to be called when close() is called.
        The function will be called after the process terminates but before
        final cleanup.  Intended for use by derived classes.

        :param hook: The hook function.
        """
        if not hasattr(self, "close_hooks"):
            self.close_hooks = []
        self.close_hooks.append(hook)

    def _get_fd(self, reader):
        """
        Return an open file descriptor corresponding to the specified reader
        pipe.  If no such reader exists, or the pipe could not be opened,
        return None.  Intended for use by derived classes.

        :param reader: The name of the reader.
        """
        return self.reader_fds.get(reader)

    def _close_reader_fds(self):
        """
        Close all reader file descriptors.
        """
        for fd in self.reader_fds.values():
            try:
                os.close(fd)
            except OSError:
                pass

    def get_id(self):
        """
        Return the instance's a_id attribute, which may be used to access the
        process in the future.
        """
        return self.a_id

    def get_pid(self):
        """
        Return the PID of the process.

        Note: this may be the PID of the shell process running the user given
        command.
        """
        try:
            fileobj = open(self.shell_pid_filename, "r")
            pid = int(fileobj.read())
            fileobj.close()
            return pid
        except Exception:
            return None

    def get_status(self):
        """
        Wait for the process to exit and return its exit status, or None
        if the exit status is not available.
        """
        _wait(self.lock_server_running_filename)
        try:
            fileobj = open(self.status_filename, "r")
            status = int(fileobj.read())
            fileobj.close()
            return status
        except Exception:
            return None

    def get_output(self):
        """
        Return the STDOUT and STDERR output of the process so far.
        """
        try:
            fileobj = open(self.output_filename, "r")
            output = fileobj.read()
            fileobj.close()
            return output
        except Exception:
            return ""

    def get_stripped_output(self):
        """
        Return the STDOUT and STDERR output without the console codes escape
        and sequences of the process so far.
        """
        return utils.strip_console_codes(self.get_output())

    def is_alive(self):
        """
        Return True if the process is running.
        """
        return _locked(self.lock_server_running_filename)

    def is_defunct(self):
        """
        Return True if the process is defunct (zombie).
        """
        return utils.process_or_children_is_defunct(self.get_pid())

    def kill(self, sig=signal.SIGKILL):
        """
        Kill the child process if alive
        """
        # Kill it if it's alive
        if self.is_alive():
            utils.kill_process_tree(self.get_pid(), sig)

    def close(self, sig=signal.SIGKILL):
        """
        Kill the child process if it's alive and remove temporary files.

        :param sig: The signal to send the process when attempting to kill it.
        """
        self.kill(sig=sig)
        # Wait for the server to exit
        _wait(self.lock_server_running_filename)
        # Call all cleanup routines
        for hook in self.close_hooks:
            hook(self)
        # Close reader file descriptors
        self._close_reader_fds()
        self.reader_fds = {}
        # Remove all used files
        for filename in (_get_filenames(BASE_DIR, self.a_id)):
            try:
                os.unlink(filename)
            except OSError:
                pass

    def set_linesep(self, linesep):
        """
        Sets the line separator string (usually "\\n").

        :param linesep: Line separator string.
        """
        self.linesep = linesep

    def send(self, cont=""):
        """
        Send a string to the child process.

        :param cont: String to send to the child process.
        """
        try:
            fd = os.open(self.inpipe_filename, os.O_RDWR)
            os.write(fd, cont)
            os.close(fd)
        except Exception:
            pass

    def sendline(self, cont=""):
        """
        Send a string followed by a line separator to the child process.

        :param cont: String to send to the child process.
        """
        self.send(cont + self.linesep)

    def send_ctrl(self, control_str=""):
        """
        Send a control string to the aexpect process.

        :param control_str: Control string to send to the child process
                            container.
        """
        try:
            fd = os.open(self.ctrlpipe_filename, os.O_RDWR)
            os.write(fd, "%10d%s" % (len(control_str), control_str))
            os.close(fd)
        except Exception:
            pass


_thread_kill_requested = False


def kill_tail_threads():
    """
    Kill all Tail threads.

    After calling this function no new threads should be started.
    """
    global _thread_kill_requested
    _thread_kill_requested = True

    for t in threading.enumerate():
        if hasattr(t, "name") and t.name.startswith("tail_thread"):
            t.join(10)
    _thread_kill_requested = False


class Tail(Spawn):

    """
    This class runs a child process in the background and sends its output in
    real time, line-by-line, to a callback function.

    See Spawn's docstring.

    This class uses a single pipe reader to read data in real time from the
    child process and report it to a given callback function.
    When the child process exits, its exit status is reported to an additional
    callback function.

    When this class is unpickled, it automatically resumes reporting output.
    """

    def __init__(self, command=None, a_id=None, auto_close=False, echo=False,
                 linesep="\n", termination_func=None, termination_params=(),
                 output_func=None, output_params=(), output_prefix="",
                 thread_name=None):
        """
        Initialize the class and run command as a child process.

        :param command: Command to run, or None if accessing an already running
                server.
        :param a_id: ID of an already running server, if accessing a running
                server, or None if starting a new one.
        :param auto_close: If True, close() the instance automatically when its
                reference count drops to zero (default False).
        :param echo: Boolean indicating whether echo should be initially
                enabled for the pseudo terminal running the subprocess.  This
                parameter has an effect only when starting a new server.
        :param linesep: Line separator to be appended to strings sent to the
                child process by sendline().
        :param termination_func: Function to call when the process exits.  The
                function must accept a single exit status parameter.
        :param termination_params: Parameters to send to termination_func
                before the exit status.
        :param output_func: Function to call whenever a line of output is
                available from the STDOUT or STDERR streams of the process.
                The function must accept a single string parameter.  The string
                does not include the final newline.
        :param output_params: Parameters to send to output_func before the
                output line.
        :param output_prefix: String to prepend to lines sent to output_func.
        :param thread_name: Name of thread to better identify hanging threads.
        """
        # Add a reader and a close hook
        self._add_reader("tail")
        self._add_close_hook(Tail._join_thread)
        self._add_close_hook(Tail._close_log_file)

        # Init the superclass
        Spawn.__init__(self, command, a_id, auto_close, echo, linesep)
        if thread_name is None:
            self.thread_name = ("tail_thread_%s_%s") % (self.a_id,
                                                        str(command)[:10])
        else:
            self.thread_name = thread_name

        # Remember some attributes
        self.termination_func = termination_func
        self.termination_params = termination_params
        self.output_func = output_func
        self.output_params = output_params
        self.output_prefix = output_prefix

        # Start the thread in the background
        self.tail_thread = None
        if termination_func or output_func:
            self._start_thread()

    def __reduce__(self):
        return self.__class__, (self.__getinitargs__())

    def __getinitargs__(self):
        return Spawn.__getinitargs__(self) + (self.termination_func,
                                              self.termination_params,
                                              self.output_func,
                                              self.output_params,
                                              self.output_prefix,
                                              self.thread_name)

    def set_termination_func(self, termination_func):
        """
        Set the termination_func attribute. See __init__() for details.

        :param termination_func: Function to call when the process terminates.
                Must take a single parameter -- the exit status.
        """
        self.termination_func = termination_func
        if termination_func and not self.tail_thread:
            self._start_thread()

    def set_termination_params(self, termination_params):
        """
        Set the termination_params attribute. See __init__() for details.

        :param termination_params: Parameters to send to termination_func
                before the exit status.
        """
        self.termination_params = termination_params

    def set_output_func(self, output_func):
        """
        Set the output_func attribute. See __init__() for details.

        :param output_func: Function to call for each line of STDOUT/STDERR
                output from the process.  Must take a single string parameter.
        """
        self.output_func = output_func
        if output_func and not self.tail_thread:
            self._start_thread()

    def set_output_params(self, output_params):
        """
        Set the output_params attribute. See __init__() for details.

        :param output_params: Parameters to send to output_func before the
                output line.
        """
        self.output_params = output_params

    def set_output_prefix(self, output_prefix):
        """
        Set the output_prefix attribute. See __init__() for details.

        :param output_prefix: String to pre-pend to each line sent to
                output_func (see set_output_callback()).
        """
        self.output_prefix = output_prefix

    def set_log_file(self, filename):
        """
        Set a log file name for this tail instance.

        :param filename: Base name of the log.
        """
        self.log_file = filename

    def _close_log_file(self):
        if self.log_file is not None:
            utils.close_log_file(self.log_file)

    def _tail(self):
        def print_line(text):
            # Pre-pend prefix and remove trailing whitespace
            text = self.output_prefix + text.rstrip()
            # Pass text to output_func
            try:
                params = self.output_params + (text,)
                self.output_func(*params)
            except TypeError:
                pass

        try:
            fd = self._get_fd("tail")
            bfr = ""
            while True:
                global _thread_kill_requested
                if _thread_kill_requested:
                    try:
                        os.close(fd)
                    except:
                        pass
                    return
                try:
                    # See if there's any data to read from the pipe
                    r, w, x = select.select([fd], [], [], 0.05)
                except Exception:
                    break
                if fd in r:
                    # Some data is available; read it
                    new_data = os.read(fd, 1024)
                    if not new_data:
                        break
                    bfr += new_data
                    # Send the output to output_func line by line
                    # (except for the last line)
                    if self.output_func:
                        lines = bfr.split("\n")
                        for line in lines[:-1]:
                            print_line(line)
                    # Leave only the last line
                    last_newline_index = bfr.rfind("\n")
                    bfr = bfr[last_newline_index + 1:]
                else:
                    # No output is available right now; flush the bfr
                    if bfr:
                        print_line(bfr)
                        bfr = ""
            # The process terminated; print any remaining output
            if bfr:
                print_line(bfr)
            # Get the exit status, print it and send it to termination_func
            status = self.get_status()
            if status is None:
                return
            print_line("(Process terminated with status %s)" % status)
            try:
                params = self.termination_params + (status,)
                self.termination_func(*params)
            except TypeError:
                pass
        finally:
            self.tail_thread = None

    def _start_thread(self):
        self.tail_thread = threading.Thread(target=self._tail,
                                            name=self.thread_name)
        self.tail_thread.start()

    def _join_thread(self):
        # Wait for the tail thread to exit
        # (it's done this way because self.tail_thread may become None at any
        # time)
        t = self.tail_thread
        if t:
            t.join()


class Expect(Tail):

    """
    This class runs a child process in the background and provides expect-like
    services.

    It also provides all of Tail's functionality.
    """

    def __init__(self, command=None, a_id=None, auto_close=True, echo=False,
                 linesep="\n", termination_func=None, termination_params=(),
                 output_func=None, output_params=(), output_prefix="",
                 thread_name=None):
        """
        Initialize the class and run command as a child process.

        :param command: Command to run, or None if accessing an already running
                server.
        :param a_id: ID of an already running server, if accessing a running
                server, or None if starting a new one.
        :param auto_close: If True, close() the instance automatically when its
                reference count drops to zero (default False).
        :param echo: Boolean indicating whether echo should be initially
                enabled for the pseudo terminal running the subprocess.  This
                parameter has an effect only when starting a new server.
        :param linesep: Line separator to be appended to strings sent to the
                child process by sendline().
        :param termination_func: Function to call when the process exits.  The
                function must accept a single exit status parameter.
        :param termination_params: Parameters to send to termination_func
                before the exit status.
        :param output_func: Function to call whenever a line of output is
                available from the STDOUT or STDERR streams of the process.
                The function must accept a single string parameter.  The string
                does not include the final newline.
        :param output_params: Parameters to send to output_func before the
                output line.
        :param output_prefix: String to prepend to lines sent to output_func.
        """
        # Add a reader
        self._add_reader("expect")

        # Init the superclass
        Tail.__init__(self, command, a_id, auto_close, echo, linesep,
                      termination_func, termination_params,
                      output_func, output_params, output_prefix, thread_name)

    def __reduce__(self):
        return self.__class__, (self.__getinitargs__())

    def __getinitargs__(self):
        return Tail.__getinitargs__(self)

    def read_nonblocking(self, internal_timeout=None, timeout=None):
        """
        Read from child until there is nothing to read for timeout seconds.

        :param internal_timeout: Time (seconds) to wait before we give up
                                 reading from the child process, or None to
                                 use the default value.
        :param timeout: Timeout for reading child process output.
        """
        if internal_timeout is None:
            internal_timeout = 0.1
        end_time = None
        if timeout:
            end_time = time.time() + timeout
        fd = self._get_fd("expect")
        data = ""
        while True:
            try:
                r, w, x = select.select([fd], [], [], internal_timeout)
            except Exception:
                return data
            if fd in r:
                new_data = os.read(fd, 1024)
                if not new_data:
                    return data
                data += new_data
            else:
                return data
            if end_time and time.time() > end_time:
                return data

    def match_patterns(self, cont, patterns):
        """
        Match cont against a list of patterns.

        Return the index of the first pattern that matches a substring of cont.
        None and empty strings in patterns are ignored.
        If no match is found, return None.

        :param cont: input string
        :param patterns: List of strings (regular expression patterns).
        """
        for i in range(len(patterns)):
            if not patterns[i]:
                continue
            if re.search(patterns[i], cont):
                return i

    def match_patterns_multiline(self, cont, patterns):
        """
        Match list of lines against a list of patterns.

        Return the index of the first pattern that matches a substring of cont.
        None and empty strings in patterns are ignored.
        If no match is found, return None.

        :param cont: List of strings (input strings)
        :param patterns: List of strings (regular expression patterns). The
                         pattern priority is from the last to first.
        """
        for i in range(-len(patterns), 0):
            if not patterns[i]:
                continue
            for line in cont:
                if re.search(patterns[i], line):
                    return i

    def read_until_output_matches(self, patterns, filter_func=lambda x: x,
                                  timeout=60, internal_timeout=None,
                                  print_func=None, match_func=None):
        """
        Read from child using read_nonblocking until a pattern matches.

        Read using read_nonblocking until a match is found using match_patterns,
        or until timeout expires. Before attempting to search for a match, the
        data is filtered using the filter_func function provided.

        :param patterns: List of strings (regular expression patterns)
        :param filter_func: Function to apply to the data read from the child before
                attempting to match it against the patterns (should take and
                return a string)
        :param timeout: The duration (in seconds) to wait until a match is
                found
        :param internal_timeout: The timeout to pass to read_nonblocking
        :param print_func: A function to be used to print the data being read
                (should take a string parameter)
        :param match_func: Function to compare the output and patterns.
        :return: Tuple containing the match index and the data read so far
        :raise ExpectTimeoutError: Raised if timeout expires
        :raise ExpectProcessTerminatedError: Raised if the child process
                terminates while waiting for output
        :raise ExpectError: Raised if an unknown error occurs
        """
        if not match_func:
            match_func = self.match_patterns
        fd = self._get_fd("expect")
        o = ""
        end_time = time.time() + timeout
        while True:
            try:
                r, w, x = select.select([fd], [], [],
                                        max(0, end_time - time.time()))
            except (select.error, TypeError):
                break
            if not r:
                raise ExpectTimeoutError(patterns, o)
            # Read data from child
            data = self.read_nonblocking(internal_timeout,
                                         end_time - time.time())
            if not data:
                break
            # Print it if necessary
            if print_func:
                for line in data.splitlines():
                    print_func(line)
            # Look for patterns
            o += data
            match = match_func(filter_func(o), patterns)
            if match is not None:
                return match, o

        # Check if the child has terminated
        if utils.wait_for(lambda: not self.is_alive(), 5, 0, 0.1):
            raise ExpectProcessTerminatedError(patterns, self.get_status(), o)
        else:
            # This shouldn't happen
            raise ExpectError(patterns, o)

    def read_until_last_word_matches(self, patterns, timeout=60,
                                     internal_timeout=None, print_func=None):
        """
        Read using read_nonblocking until the last word of the output matches
        one of the patterns (using match_patterns), or until timeout expires.

        :param patterns: A list of strings (regular expression patterns)
        :param timeout: The duration (in seconds) to wait until a match is
                found
        :param internal_timeout: The timeout to pass to read_nonblocking
        :param print_func: A function to be used to print the data being read
                (should take a string parameter)
        :return: A tuple containing the match index and the data read so far
        :raise ExpectTimeoutError: Raised if timeout expires
        :raise ExpectProcessTerminatedError: Raised if the child process
                terminates while waiting for output
        :raise ExpectError: Raised if an unknown error occurs
        """
        def get_last_word(cont):
            if cont:
                return cont.split()[-1]
            else:
                return ""

        return self.read_until_output_matches(patterns, get_last_word,
                                              timeout, internal_timeout,
                                              print_func)

    def read_until_last_line_matches(self, patterns, timeout=60,
                                     internal_timeout=None, print_func=None):
        """
        Read using read_nonblocking until the last non-empty line matches a pattern.

        Read using read_nonblocking until the last non-empty line of the output
        matches one of the patterns (using match_patterns), or until timeout
        expires. Return a tuple containing the match index (or None if no match
        was found) and the data read so far.

        :param patterns: A list of strings (regular expression patterns)
        :param timeout: The duration (in seconds) to wait until a match is
                found
        :param internal_timeout: The timeout to pass to read_nonblocking
        :param print_func: A function to be used to print the data being read
                (should take a string parameter)
        :return: A tuple containing the match index and the data read so far
        :raise ExpectTimeoutError: Raised if timeout expires
        :raise ExpectProcessTerminatedError: Raised if the child process
                terminates while waiting for output
        :raise ExpectError: Raised if an unknown error occurs
        """
        def get_last_nonempty_line(cont):
            nonempty_lines = [l for l in cont.splitlines() if l.strip()]
            if nonempty_lines:
                return nonempty_lines[-1]
            else:
                return ""

        return self.read_until_output_matches(patterns, get_last_nonempty_line,
                                              timeout, internal_timeout,
                                              print_func)

    def read_until_any_line_matches(self, patterns, timeout=60,
                                    internal_timeout=None, print_func=None):
        """
        Read using read_nonblocking until any line matches a pattern.

        Read using read_nonblocking until any line of the output matches
        one of the patterns (using match_patterns_multiline), or until timeout
        expires. Return a tuple containing the match index (or None if no match
        was found) and the data read so far.

        :param patterns: A list of strings (regular expression patterns)
                         Consider using '^' in the beginning.
        :param timeout: The duration (in seconds) to wait until a match is
                found
        :param internal_timeout: The timeout to pass to read_nonblocking
        :param print_func: A function to be used to print the data being read
                (should take a string parameter)
        :return: A tuple containing the match index and the data read so far
        :raise ExpectTimeoutError: Raised if timeout expires
        :raise ExpectProcessTerminatedError: Raised if the child process
                terminates while waiting for output
        :raise ExpectError: Raised if an unknown error occurs
        """
        return self.read_until_output_matches(patterns,
                                              lambda x: x.splitlines(
                                              ), timeout,
                                              internal_timeout, print_func,
                                              self.match_patterns_multiline)


class ShellSession(Expect):

    """
    This class runs a child process in the background.  It it suited for
    processes that provide an interactive shell, such as SSH and Telnet.

    It provides all services of Expect and Tail.  In addition, it
    provides command running services, and a utility function to test the
    process for responsiveness.
    """

    def __init__(self, command=None, a_id=None, auto_close=True, echo=False,
                 linesep="\n", termination_func=None, termination_params=(),
                 output_func=None, output_params=(), output_prefix="",
                 thread_name=None, prompt=r"[\#\$]\s*$",
                 status_test_command="echo $?"):
        """
        Initialize the class and run command as a child process.

        :param command: Command to run, or None if accessing an already running
                server.
        :param a_id: ID of an already running server, if accessing a running
                server, or None if starting a new one.
        :param auto_close: If True, close() the instance automatically when its
                reference count drops to zero (default True).
        :param echo: Boolean indicating whether echo should be initially
                enabled for the pseudo terminal running the subprocess.  This
                parameter has an effect only when starting a new server.
        :param linesep: Line separator to be appended to strings sent to the
                child process by sendline().
        :param termination_func: Function to call when the process exits.  The
                function must accept a single exit status parameter.
        :param termination_params: Parameters to send to termination_func
                before the exit status.
        :param output_func: Function to call whenever a line of output is
                available from the STDOUT or STDERR streams of the process.
                The function must accept a single string parameter.  The string
                does not include the final newline.
        :param output_params: Parameters to send to output_func before the
                output line.
        :param output_prefix: String to prepend to lines sent to output_func.
        :param prompt: Regular expression describing the shell's prompt line.
        :param status_test_command: Command to be used for getting the last
                exit status of commands run inside the shell (used by
                cmd_status_output() and friends).
        """
        # Init the superclass
        Expect.__init__(self, command, a_id, auto_close, echo, linesep,
                        termination_func, termination_params,
                        output_func, output_params, output_prefix, thread_name)

        # Remember some attributes
        self.prompt = prompt
        self.status_test_command = status_test_command

    def __reduce__(self):
        return self.__class__, (self.__getinitargs__())

    def __getinitargs__(self):
        return Expect.__getinitargs__(self) + (self.prompt,
                                               self.status_test_command)

    @classmethod
    def remove_command_echo(cls, cont, cmd):
        if cont and cont.splitlines()[0] == cmd:
            cont = "".join(cont.splitlines(True)[1:])
        return cont

    @classmethod
    def remove_last_nonempty_line(cls, cont):
        return "".join(cont.rstrip().splitlines(True)[:-1])

    def set_prompt(self, prompt):
        """
        Set the prompt attribute for later use by read_up_to_prompt.

        :param String that describes the prompt contents.
        """
        self.prompt = prompt

    def set_status_test_command(self, status_test_command):
        """
        Set the command to be sent in order to get the last exit status.

        :param status_test_command: Command that will be sent to get the last
                exit status.
        """
        self.status_test_command = status_test_command

    def is_responsive(self, timeout=5.0):
        """
        Return True if the process responds to STDIN/terminal input.

        Send a newline to the child process (e.g. SSH or Telnet) and read some
        output using read_nonblocking().
        If all is OK, some output should be available (e.g. the shell prompt).
        In that case return True.  Otherwise return False.

        :param timeout: Time duration to wait before the process is considered
                unresponsive.
        """
        # Read all output that's waiting to be read, to make sure the output
        # we read next is in response to the newline sent
        self.read_nonblocking(internal_timeout=0, timeout=timeout)
        # Send a newline
        self.sendline()
        # Wait up to timeout seconds for some output from the child
        end_time = time.time() + timeout
        while time.time() < end_time:
            time.sleep(0.5)
            if self.read_nonblocking(0, end_time - time.time()).strip():
                return True
        # No output -- report unresponsive
        return False

    def read_up_to_prompt(self, timeout=60, internal_timeout=None,
                          print_func=None):
        """
        Read using read_nonblocking until the last non-empty line matches the prompt.

        Read using read_nonblocking until the last non-empty line of the output
        matches the prompt regular expression set by set_prompt, or until
        timeout expires.

        :param timeout: The duration (in seconds) to wait until a match is
                found
        :param internal_timeout: The timeout to pass to read_nonblocking
        :param print_func: A function to be used to print the data being
                read (should take a string parameter)

        :return: The data read so far
        :raise ExpectTimeoutError: Raised if timeout expires
        :raise ExpectProcessTerminatedError: Raised if the shell process
                terminates while waiting for output
        :raise ExpectError: Raised if an unknown error occurs
        """
        return self.read_until_last_line_matches([self.prompt], timeout,
                                                 internal_timeout,
                                                 print_func)[1]

    def cmd_output(self, cmd, timeout=60, internal_timeout=None,
                   print_func=None):
        """
        Send a command and return its output.

        :param cmd: Command to send (must not contain newline characters)
        :param timeout: The duration (in seconds) to wait for the prompt to
                return
        :param internal_timeout: The timeout to pass to read_nonblocking
        :param print_func: A function to be used to print the data being read
                (should take a string parameter)

        :return: The output of cmd
        :raise ShellTimeoutError: Raised if timeout expires
        :raise ShellProcessTerminatedError: Raised if the shell process
                terminates while waiting for output
        :raise ShellError: Raised if an unknown error occurs
        """
        logging.debug("Sending command: %s" % cmd)
        self.read_nonblocking(0, timeout)
        self.sendline(cmd)
        try:
            o = self.read_up_to_prompt(timeout, internal_timeout, print_func)
        except ExpectError, e:
            o = self.remove_command_echo(e.output, cmd)
            if isinstance(e, ExpectTimeoutError):
                raise ShellTimeoutError(cmd, o)
            elif isinstance(e, ExpectProcessTerminatedError):
                raise ShellProcessTerminatedError(cmd, e.status, o)
            else:
                raise ShellError(cmd, o)

        # Remove the echoed command and the final shell prompt
        return self.remove_last_nonempty_line(self.remove_command_echo(o, cmd))

    def cmd_output_safe(self, cmd, timeout=60, internal_timeout=None,
                        print_func=None):
        """
        Send a command and return its output (serial sessions).

        In serial sessions, frequently the kernel might print debug or
        error messages that make read_up_to_prompt to timeout. Let's try
        to be a little more robust and send a carriage return, to see if
        we can get to the prompt.

        :param cmd: Command to send (must not contain newline characters)
        :param timeout: The duration (in seconds) to wait for the prompt to
                return
        :param internal_timeout: The timeout to pass to read_nonblocking
        :param print_func: A function to be used to print the data being read
                (should take a string parameter)

        :return: The output of cmd
        :raise ShellTimeoutError: Raised if timeout expires
        :raise ShellProcessTerminatedError: Raised if the shell process
                terminates while waiting for output
        :raise ShellError: Raised if an unknown error occurs
        """
        logging.debug("Sending command (safe): %s" % cmd)
        self.read_nonblocking(0, timeout)
        self.sendline(cmd)
        o = ""
        success = False
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            try:
                o += self.read_up_to_prompt(0.5)
                success = True
                break
            except ExpectError, e:
                o = self.remove_command_echo(e.output, cmd)
                if isinstance(e, ExpectTimeoutError):
                    self.sendline()
                elif isinstance(e, ExpectProcessTerminatedError):
                    raise ShellProcessTerminatedError(cmd, e.status, o)
                else:
                    raise ShellError(cmd, o)

        if not success:
            raise ShellTimeoutError(cmd, o)

        # Remove the echoed command and the final shell prompt
        return self.remove_last_nonempty_line(self.remove_command_echo(o, cmd))

    def cmd_status_output(self, cmd, timeout=60, internal_timeout=None,
                          print_func=None):
        """
        Send a command and return its exit status and output.

        :param cmd: Command to send (must not contain newline characters)
        :param timeout: The duration (in seconds) to wait for the prompt to
                return
        :param internal_timeout: The timeout to pass to read_nonblocking
        :param print_func: A function to be used to print the data being read
                (should take a string parameter)

        :return: A tuple (status, output) where status is the exit status and
                output is the output of cmd
        :raise ShellTimeoutError: Raised if timeout expires
        :raise ShellProcessTerminatedError: Raised if the shell process
                terminates while waiting for output
        :raise ShellStatusError: Raised if the exit status cannot be obtained
        :raise ShellError: Raised if an unknown error occurs
        """
        o = self.cmd_output(cmd, timeout, internal_timeout, print_func)
        try:
            # Send the 'echo $?' (or equivalent) command to get the exit status
            s = self.cmd_output(self.status_test_command, 10, internal_timeout)
        except ShellError:
            raise ShellStatusError(cmd, o)

        # Get the first line consisting of digits only
        digit_lines = [l for l in s.splitlines() if l.strip().isdigit()]
        if digit_lines:
            return int(digit_lines[0].strip()), o
        else:
            raise ShellStatusError(cmd, o)

    def cmd_status(self, cmd, timeout=60, internal_timeout=None,
                   print_func=None):
        """
        Send a command and return its exit status.

        :param cmd: Command to send (must not contain newline characters)
        :param timeout: The duration (in seconds) to wait for the prompt to
                return
        :param internal_timeout: The timeout to pass to read_nonblocking
        :param print_func: A function to be used to print the data being read
                (should take a string parameter)

        :return: The exit status of cmd
        :raise ShellTimeoutError: Raised if timeout expires
        :raise ShellProcessTerminatedError: Raised if the shell process
                terminates while waiting for output
        :raise ShellStatusError: Raised if the exit status cannot be obtained
        :raise ShellError: Raised if an unknown error occurs
        """
        return self.cmd_status_output(cmd, timeout, internal_timeout,
                                      print_func)[0]

    def cmd(self, cmd, timeout=60, internal_timeout=None, print_func=None,
            ok_status=[0, ], ignore_all_errors=False):
        """
        Send a command and return its output. If the command's exit status is
        nonzero, raise an exception.

        :param cmd: Command to send (must not contain newline characters)
        :param timeout: The duration (in seconds) to wait for the prompt to
                return
        :param internal_timeout: The timeout to pass to read_nonblocking
        :param print_func: A function to be used to print the data being read
                (should take a string parameter)
        :param ok_status: do not raise ShellCmdError in case that exit status
                is one of ok_status. (default is [0,])
        :param ignore_all_errors: toggles whether or not an exception should be
                raised  on any error.

        :return: The output of cmd
        :raise ShellTimeoutError: Raised if timeout expires
        :raise ShellProcessTerminatedError: Raised if the shell process
                terminates while waiting for output
        :raise ShellError: Raised if the exit status cannot be obtained or if
                an unknown error occurs
        :raise ShellStatusError: Raised if the exit status cannot be obtained
        :raise ShellError: Raised if an unknown error occurs
        :raise ShellCmdError: Raised if the exit status is nonzero
        """
        try:
            s, o = self.cmd_status_output(cmd, timeout, internal_timeout,
                                          print_func)
            if s not in ok_status:
                raise ShellCmdError(cmd, s, o)
            return o
        except Exception:
            if ignore_all_errors:
                pass
            else:
                raise

    def get_command_output(self, cmd, timeout=60, internal_timeout=None,
                           print_func=None):
        """
        Alias for cmd_output() for backward compatibility.
        """
        return self.cmd_output(cmd, timeout, internal_timeout, print_func)

    def get_command_status_output(self, cmd, timeout=60, internal_timeout=None,
                                  print_func=None):
        """
        Alias for cmd_status_output() for backward compatibility.
        """
        return self.cmd_status_output(cmd, timeout, internal_timeout,
                                      print_func)

    def get_command_status(self, cmd, timeout=60, internal_timeout=None,
                           print_func=None):
        """
        Alias for cmd_status() for backward compatibility.
        """
        return self.cmd_status(cmd, timeout, internal_timeout, print_func)
