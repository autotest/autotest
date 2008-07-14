#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the SSHHost class.

Implementation details:
You should import the "hosts" package instead of importing each type of host.

        SSHHost: a remote machine with a ssh access
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)
"""


import types, os, sys, signal, subprocess, time, re, socket, pdb

from autotest_lib.client.common_lib import error, pxssh, global_config
from autotest_lib.server import utils
import remote, bootloader


class PermissionDeniedError(error.AutoservRunError):
    pass


class SSHHost(remote.RemoteHost):
    """
    This class represents a remote machine controlled through an ssh
    session on which you can run programs.

    It is not the machine autoserv is running on. The machine must be
    configured for password-less login, for example through public key
    authentication.

    It includes support for controlling the machine through a serial
    console on which you can run programs. If such a serial console is
    set up on the machine then capabilities such as hard reset and
    boot strap monitoring are available. If the machine does not have a
    serial console available then ordinary SSH-based commands will
    still be available, but attempts to use extensions such as
    console logging or hard reset will fail silently.

    Implementation details:
    This is a leaf class in an abstract class hierarchy, it must
    implement the unimplemented methods in parent classes.
    """

    DEFAULT_REBOOT_TIMEOUT = 1800
    job = None

    def __init__(self, hostname, user="root", port=22, initialize=True,
                 conmux_log="console.log",
                 conmux_server=None, conmux_attach=None,
                 netconsole_log=None, netconsole_port=6666, autodir=None,
                 password=''):
        """
        Construct a SSHHost object

        Args:
                hostname: network hostname or address of remote machine
                user: user to log in as on the remote machine
                port: port the ssh daemon is listening on on the remote
                        machine
        """
        self.hostname= hostname
        self.user= user
        self.port= port
        self.tmp_dirs= []
        self.initialize = initialize
        self.autodir = autodir
        self.password = password

        super(SSHHost, self).__init__()

        self.conmux_server = conmux_server
        if conmux_attach:
            self.conmux_attach = conmux_attach
        else:
            self.conmux_attach = os.path.abspath(os.path.join(
                                    self.serverdir, '..',
                                    'conmux', 'conmux-attach'))
        self.logger_popen = None
        self.warning_stream = None
        self.__start_console_log(conmux_log)

        self.bootloader = bootloader.Bootloader(self)

        self.__netconsole_param = ""
        self.netlogger_popen = None
        if netconsole_log:
            self.__init_netconsole_params(netconsole_port)
            self.__start_netconsole_log(netconsole_log, netconsole_port)
            self.__load_netconsole_module()


    @staticmethod
    def __kill(popen):
        return_code = popen.poll()
        if return_code is None:
            try:
                os.kill(popen.pid, signal.SIGTERM)
            except OSError:
                pass


    def __del__(self):
        """
        Destroy a SSHHost object
        """
        for dir in self.tmp_dirs:
            try:
                self.run('rm -rf "%s"' % (utils.sh_escape(dir)))
            except error.AutoservRunError:
                pass
        # kill the console logger
        if getattr(self, 'logger_popen', None):
            self.__kill(self.logger_popen)
            if self.job:
                self.job.warning_loggers.discard(
                    self.warning_stream)
            self.warning_stream.close()
        # kill the netconsole logger
        if getattr(self, 'netlogger_popen', None):
            self.__unload_netconsole_module()
            self.__kill(self.netlogger_popen)


    def __init_netconsole_params(self, port):
        """
        Connect to the remote machine and determine the values to use for the
        required netconsole parameters.
        """
        # PROBLEM: on machines with multiple IPs this may not make any sense
        # It also doesn't work with IPv6
        remote_ip = socket.gethostbyname(self.hostname)
        local_ip = socket.gethostbyname(socket.gethostname())
        # Get the gateway of the remote machine
        try:
            traceroute = self.run('traceroute -n %s' % local_ip)
        except error.AutoservRunError:
            return
        first_node = traceroute.stdout.split("\n")[0]
        match = re.search(r'\s+((\d+\.){3}\d+)\s+', first_node)
        if match:
            router_ip = match.group(1)
        else:
            return
        # Look up the MAC address of the gateway
        try:
            self.run('ping -c 1 %s' % router_ip)
            arp = self.run('arp -n -a %s' % router_ip)
        except error.AutoservRunError:
            return
        match = re.search(r'\s+(([0-9A-F]{2}:){5}[0-9A-F]{2})\s+', arp.stdout)
        if match:
            gateway_mac = match.group(1)
        else:
            return
        self.__netconsole_param = 'netconsole=@%s/,%s@%s/%s' % (remote_ip,
                                                                port,
                                                                local_ip,
                                                                gateway_mac)


    def __start_netconsole_log(self, logfilename, port):
        """
        Log the output of netconsole to a specified file
        """
        if logfilename == None:
            return
        cmd = ['nc', '-u', '-l', '-p', str(port)]
        logfile = open(logfilename, 'a', 0)
        self.netlogger_popen = subprocess.Popen(cmd, stdout=logfile)


    def __load_netconsole_module(self):
        """
        Make a best effort to load the netconsole module.

        Note that loading the module can fail even when the remote machine is
        working correctly if netconsole is already compiled into the kernel
        and started.
        """
        if not self.__netconsole_param:
            return
        try:
            self.run('modprobe netconsole %s' % self.__netconsole_param)
        except error.AutoservRunError:
            # if it fails there isn't much we can do, just keep going
            pass


    def __unload_netconsole_module(self):
        try:
            self.run('modprobe -r netconsole')
        except error.AutoservRunError:
            pass


    def _wait_for_restart(self, timeout=DEFAULT_REBOOT_TIMEOUT):
        """ Underlying wait_for_restart function. For use from either
        the public wait_for_restart(), or from SSHHost methods that wait
        as part of a larger reboot process."""
        if not self.wait_down(300):     # Make sure he's dead, Jim
            self.__record("ABORT", None, "reboot.verify", "shutdown failed")
            raise error.AutoservRebootError("Host did not shut down")
        self.wait_up(timeout)
        time.sleep(2) # this is needed for complete reliability
        if self.wait_up(timeout):
            self.__record("GOOD", None, "reboot.verify")
        else:
            self.__record("ABORT", None, "reboot.verify",
                          "Host did not return from reboot")
            raise error.AutoservRebootError(
                "Host did not return from reboot")
        print "Reboot complete"


    def wait_for_restart(self, timeout=DEFAULT_REBOOT_TIMEOUT):
        """ Wait for the machine to come back from a reboot. This wraps the
        logging of the reboot in a group, and grabs the kernel version on
        the remote machine and includes it in the status logs. """
        def reboot_func():
            self._wait_for_restart(timeout=timeout)
        self.__run_reboot_group(reboot_func)


    def hardreset(self, timeout=DEFAULT_REBOOT_TIMEOUT, wait=True,
                  conmux_command='hardreset'):
        """
        Reach out and slap the box in the power switch.
        Args:
                conmux_command: The command to run via the conmux interface
                timeout: timelimit in seconds before the machine is considered unreachable
                wait: Whether or not to wait for the machine to reboot

        """
        conmux_command = r"'~$%s'" % conmux_command
        if not self.__console_run(conmux_command):
            self.__record("ABORT", None, "reboot.start", "hard reset unavailable")
            raise error.AutoservUnsupportedError(
                'Hard reset unavailable')

        if wait:
            self._wait_for_restart(timeout)
        self.__record("GOOD", None, "reboot.start", "hard reset")


    def __conmux_hostname(self):
        if self.conmux_server:
            return '%s/%s' % (self.conmux_server, self.hostname)
        else:
            return self.hostname


    def __start_console_log(self, logfilename):
        """
        Log the output of the console session to a specified file
        """
        if logfilename == None:
            return
        if not self.conmux_attach or not os.path.exists(self.conmux_attach):
            return

        r, w = os.pipe()
        script_path = os.path.join(self.serverdir,
                                   'warning_monitor.py')
        cmd = [self.conmux_attach, self.__conmux_hostname(),
               '%s %s %s %d' % (sys.executable, script_path,
                                logfilename, w)]
        dev_null = open(os.devnull, 'w')

        self.warning_stream = os.fdopen(r, 'r', 0)
        if self.job:
            self.job.warning_loggers.add(self.warning_stream)
        self.logger_popen = subprocess.Popen(cmd, stderr=dev_null)
        os.close(w)


    def __console_run(self, cmd):
        """
        Send a command to the conmux session
        """
        if not self.conmux_attach or not os.path.exists(self.conmux_attach):
            return False
        cmd = '%s %s echo %s 2> /dev/null' % (self.conmux_attach,
                                              self.__conmux_hostname(),
                                              cmd)
        result = utils.system(cmd, ignore_status=True)
        return result == 0


    def __run_reboot_group(self, reboot_func):
        if self.job:
            self.job.run_reboot(reboot_func, self.get_kernel_ver)
        else:
            reboot_func()


    def __record(self, status_code, subdir, operation, status = ''):
        if self.job:
            self.job.record(status_code, subdir, operation, status)
        else:
            if not subdir:
                subdir = "----"
            msg = "%s\t%s\t%s\t%s" % (status_code, subdir, operation, status)
            sys.stderr.write(msg + "\n")


    def ssh_base_command(self, connect_timeout=30):
        SSH_BASE_COMMAND = '/usr/bin/ssh -a -x -o ' + \
                           'BatchMode=yes -o ConnectTimeout=%d ' + \
                           '-o ServerAliveInterval=300'
        assert isinstance(connect_timeout, (int, long))
        assert connect_timeout > 0 # can't disable the timeout
        return SSH_BASE_COMMAND % connect_timeout


    def ssh_command(self, connect_timeout=30, options=''):
        """Construct an ssh command with proper args for this host."""
        ssh = self.ssh_base_command(connect_timeout)
        return r'%s %s -l %s -p %d %s' % (ssh,
                                          options,
                                          self.user,
                                          self.port,
                                          self.hostname)


    def _run(self, command, timeout, ignore_status, stdout, stderr,
             connect_timeout, env, options):
        """Helper function for run()."""

        ssh_cmd = self.ssh_command(connect_timeout, options)
        echo_cmd = 'echo Connected. >&2'
        full_cmd = '%s "%s;%s %s"' % (ssh_cmd, echo_cmd, env,
                                      utils.sh_escape(command))
        result = utils.run(full_cmd, timeout, True, stdout, stderr)

        # The error messages will show up in band (indistinguishable
        # from stuff sent through the SSH connection), so we have the
        # remote computer echo the message "Connected." before running
        # any command.  Since the following 2 errors have to do with
        # connecting, it's safe to do these checks.
        if result.exit_status == 255:
            if re.search(r'^ssh: connect to host .* port .*: '
                         r'Connection timed out\r$', result.stderr):
                raise error.AutoservSSHTimeout("ssh timed out",
                                               result)
            if result.stderr == "Permission denied.\r\n":
                msg = "ssh permission denied"
                raise PermissionDeniedError(msg, result)

        if not ignore_status and result.exit_status > 0:
            raise error.AutoservRunError("command execution error",
                                         result)

        return result


    def run(self, command, timeout=3600, ignore_status=False,
            stdout_tee=None, stderr_tee=None, connect_timeout=30):
        """
        Run a command on the remote host.

        Args:
                command: the command line string
                timeout: time limit in seconds before attempting to
                        kill the running process. The run() function
                        will take a few seconds longer than 'timeout'
                        to complete if it has to kill the process.
                ignore_status: do not raise an exception, no matter
                        what the exit code of the command is.

        Returns:
                a hosts.base_classes.CmdResult object

        Raises:
                AutoservRunError: the exit code of the command
                        execution was not 0
                AutoservSSHTimeout: ssh connection has timed out
        """
        stdout = stdout_tee or sys.stdout
        stderr = stderr_tee or sys.stdout
        print "ssh: %s" % command
        env = " ".join("=".join(pair) for pair in self.env.iteritems())
        try:
            try:
                return self._run(command, timeout,
                                 ignore_status, stdout,
                                 stderr, connect_timeout,
                                 env, '')
            except PermissionDeniedError:
                print("Permission denied to ssh; re-running"
                      "with increased logging:")
                return self._run(command, timeout,
                                 ignore_status, stdout,
                                 stderr, connect_timeout,
                                 env, '-v -v -v')
        except error.CmdError, cmderr:
            # We get a CmdError here only if there is timeout of
            # that command.  Catch that and stuff it into
            # AutoservRunError and raise it.
            raise error.AutoservRunError(cmderr.args[0],
                                         cmderr.args[1])


    def run_short(self, command, **kwargs):
        """
        Calls the run() command with a short default timeout.

        Args:
                Takes the same arguments as does run(),
                with the exception of the timeout argument which
                here is fixed at 60 seconds.
                It returns the result of run.
        """
        return self.run(command, timeout=60, **kwargs)


    def run_grep(self, command, timeout=30, ignore_status=False,
                             stdout_ok_regexp=None, stdout_err_regexp=None,
                             stderr_ok_regexp=None, stderr_err_regexp=None,
                             connect_timeout=30):
        """
        Run a command on the remote host and look for regexp
        in stdout or stderr to determine if the command was
        successul or not.

        Args:
                command: the command line string
                timeout: time limit in seconds before attempting to
                        kill the running process. The run() function
                        will take a few seconds longer than 'timeout'
                        to complete if it has to kill the process.
                ignore_status: do not raise an exception, no matter
                        what the exit code of the command is.
                stdout_ok_regexp: regexp that should be in stdout
                        if the command was successul.
                stdout_err_regexp: regexp that should be in stdout
                        if the command failed.
                stderr_ok_regexp: regexp that should be in stderr
                        if the command was successul.
                stderr_err_regexp: regexp that should be in stderr
                        if the command failed.

        Returns:
                if the command was successul, raises an exception
                otherwise.

        Raises:
                AutoservRunError:
                - the exit code of the command execution was not 0.
                - If stderr_err_regexp is found in stderr,
                - If stdout_err_regexp is found in stdout,
                - If stderr_ok_regexp is not found in stderr.
                - If stdout_ok_regexp is not found in stdout,
        """

        # We ignore the status, because we will handle it at the end.
        result = self.run(command, timeout, ignore_status=True,
                          connect_timeout=connect_timeout)

        # Look for the patterns, in order
        for (regexp, stream) in ((stderr_err_regexp, result.stderr),
                                 (stdout_err_regexp, result.stdout)):
            if regexp and stream:
                err_re = re.compile (regexp)
                if err_re.search(stream):
                    raise error.AutoservRunError(
                        '%s failed, found error pattern: '
                        '"%s"' % (command, regexp), result)

        for (regexp, stream) in ((stderr_ok_regexp, result.stderr),
                                 (stdout_ok_regexp, result.stdout)):
            if regexp and stream:
                ok_re = re.compile (regexp)
                if ok_re.search(stream):
                    if ok_re.search(stream):
                        return

        if not ignore_status and result.exit_status > 0:
            raise error.AutoservRunError("command execution error",
                                         result)


    def reboot(self, timeout=DEFAULT_REBOOT_TIMEOUT, label=None,
               kernel_args=None, wait=True):
        """
        Reboot the remote host.

        Args:
                timeout
        """
        self.reboot_setup()

        # forcibly include the "netconsole" kernel arg
        if self.__netconsole_param:
            if kernel_args is None:
                kernel_args = self.__netconsole_param
            else:
                kernel_args += " " + self.__netconsole_param
            # unload the (possibly loaded) module to avoid shutdown issues
            self.__unload_netconsole_module()
        if label or kernel_args:
            self.bootloader.install_boottool()
        if label:
            self.bootloader.set_default(label)
        if kernel_args:
            if not label:
                default = int(self.bootloader.get_default())
                label = self.bootloader.get_titles()[default]
            self.bootloader.add_args(label, kernel_args)

        # define a function for the reboot and run it in a group
        print "Reboot: initiating reboot"
        def reboot():
            self.__record("GOOD", None, "reboot.start")
            try:
                self.run('(sleep 5; reboot) '
                         '</dev/null >/dev/null 2>&1 &')
            except error.AutoservRunError:
                self.__record("ABORT", None, "reboot.start",
                              "reboot command failed")
                raise
            if wait:
                self._wait_for_restart(timeout)
                self.reboot_followup()

        # if this is a full reboot-and-wait, run the reboot inside a group
        if wait:
            self.__run_reboot_group(reboot)
        else:
            reboot()


    def reboot_followup(self):
        super(SSHHost, self).reboot_followup()
        self.__load_netconsole_module() # if the builtin fails


    def __copy_files(self, sources, dest):
        """
        Copy files from one machine to another.

        This is for internal use by other methods that intend to move
        files between machines. It expects a list of source files and
        a destination (a filename if the source is a single file, a
        destination otherwise). The names must already be
        pre-processed into the appropriate rsync/scp friendly
        format (%s@%s:%s).
        """

        print '__copy_files: copying %s to %s' % (sources, dest)
        try:
            utils.run('rsync --rsh="%s" -az %s %s' % (
                self.ssh_base_command(), ' '.join(sources), dest))
        except Exception:
            try:
                utils.run('scp -rpq -P %d %s "%s"' % (
                    self.port, ' '.join(sources), dest))
            except error.CmdError, cmderr:
                raise error.AutoservRunError(cmderr.args[0], cmderr.args[1])


    def get_file(self, source, dest):
        """
        Copy files from the remote host to a local path.

        Directories will be copied recursively.
        If a source component is a directory with a trailing slash,
        the content of the directory will be copied, otherwise, the
        directory itself and its content will be copied. This
        behavior is similar to that of the program 'rsync'.

        Args:
                source: either
                        1) a single file or directory, as a string
                        2) a list of one or more (possibly mixed)
                                files or directories
                dest: a file or a directory (if source contains a
                        directory or more than one element, you must
                        supply a directory dest)

        Raises:
                AutoservRunError: the scp command failed
        """
        if isinstance(source, types.StringTypes):
            source= [source]

        processed_source= []
        for entry in source:
            if entry.endswith('/'):
                format_string= '%s@%s:"%s*"'
            else:
                format_string= '%s@%s:"%s"'
            entry= format_string % (self.user, self.hostname,
                    utils.scp_remote_escape(entry))
            processed_source.append(entry)

        processed_dest= os.path.abspath(dest)
        if os.path.isdir(dest):
            processed_dest= "%s/" % (utils.sh_escape(processed_dest),)
        else:
            processed_dest= utils.sh_escape(processed_dest)

        self.__copy_files(processed_source, processed_dest)


    def send_file(self, source, dest):
        """
        Copy files from a local path to the remote host.

        Directories will be copied recursively.
        If a source component is a directory with a trailing slash,
        the content of the directory will be copied, otherwise, the
        directory itself and its content will be copied. This
        behavior is similar to that of the program 'rsync'.

        Args:
                source: either
                        1) a single file or directory, as a string
                        2) a list of one or more (possibly mixed)
                                files or directories
                dest: a file or a directory (if source contains a
                        directory or more than one element, you must
                        supply a directory dest)

        Raises:
                AutoservRunError: the scp command failed
        """
        if isinstance(source, types.StringTypes):
            source= [source]

        processed_source= []
        for entry in source:
            if entry.endswith('/'):
                format_string= '"%s/"*'
            else:
                format_string= '"%s"'
            entry= format_string % (utils.sh_escape(os.path.abspath(entry)),)
            processed_source.append(entry)

        remote_dest = '%s@%s:"%s"' % (
                    self.user, self.hostname,
                    utils.scp_remote_escape(dest))

        self.__copy_files(processed_source, remote_dest)
        self.run('find "%s" -type d | xargs -i -r chmod o+rx "{}"' % dest)
        self.run('find "%s" -type f | xargs -i -r chmod o+r "{}"' % dest)


    def get_tmp_dir(self):
        """
        Return the pathname of a directory on the host suitable
        for temporary file storage.

        The directory and its content will be deleted automatically
        on the destruction of the Host object that was used to obtain
        it.
        """
        dir_name=self.run("mktemp -d /tmp/autoserv-XXXXXX").stdout.rstrip(" \n")
        self.tmp_dirs.append(dir_name)
        return dir_name


    def is_up(self):
        """
        Check if the remote host is up.

        Returns:
                True if the remote host is up, False otherwise
        """
        try:
            self.ssh_ping()
        except:
            return False
        return True


    def _is_wait_up_process_up(self):
        """
        Checks if any SSHHOST waitup processes are running yet on the
        remote host.

        Returns True if any the waitup processes are running, False
        otherwise.
        """
        processes = self.get_wait_up_processes()
        if len(processes) == 0:
            return True # wait up processes aren't being used
        for procname in processes:
            exit_status = self.run("ps -e | grep '%s'" % procname,
                                   ignore_status=True).exit_status
            if exit_status == 0:
                return True
        return False


    def wait_up(self, timeout=None):
        """
        Wait until the remote host is up or the timeout expires.

        In fact, it will wait until an ssh connection to the remote
        host can be established, and getty is running.

        Args:
                timeout: time limit in seconds before returning even
                        if the host is not up.

        Returns:
                True if the host was found to be up, False otherwise
        """
        if timeout:
            end_time= time.time() + timeout

        while not timeout or time.time() < end_time:
            try:
                self.ssh_ping()
            except (error.AutoservRunError,
                    error.AutoservSSHTimeout):
                pass
            else:
                try:
                    if self._is_wait_up_process_up():
                        return True
                except (error.AutoservRunError, error.AutoservSSHTimeout):
                    pass
            time.sleep(1)

        return False


    def wait_down(self, timeout=None):
        """
        Wait until the remote host is down or the timeout expires.

        In fact, it will wait until an ssh connection to the remote
        host fails.

        Args:
                timeout: time limit in seconds before returning even
                        if the host is not up.

        Returns:
                True if the host was found to be down, False otherwise
        """
        if timeout:
            end_time= time.time() + timeout

        while not timeout or time.time() < end_time:
            try:
                self.ssh_ping()
            except:
                return True
            time.sleep(1)

        return False


    def ensure_up(self):
        """
        Ensure the host is up if it is not then do not proceed;
        this prevents cacading failures of tests
        """
        print 'Ensuring that %s is up before continuing' % self.hostname
        if hasattr(self, 'hardreset') and not self.wait_up(300):
            print "Performing a hardreset on %s" % self.hostname
            try:
                self.hardreset()
            except error.AutoservUnsupportedError:
                print "Hardreset is unsupported on %s" % self.hostname
        if not self.wait_up(60 * 30):
            # 30 minutes should be more than enough
            raise error.AutoservHostError
        print 'Host up, continuing'


    def get_num_cpu(self):
        """
        Get the number of CPUs in the host according to
        /proc/cpuinfo.

        Returns:
                The number of CPUs
        """

        proc_cpuinfo = self.run("cat /proc/cpuinfo",
                        stdout_tee=open('/dev/null', 'w')).stdout
        cpus = 0
        for line in proc_cpuinfo.splitlines():
            if line.startswith('processor'):
                cpus += 1
        return cpus


    def check_uptime(self):
        """
        Check that uptime is available and monotonically increasing.
        """
        if not self.ping():
            raise error.AutoservHostError('Client is not pingable')
        result = self.run("/bin/cat /proc/uptime", 30)
        return result.stdout.strip().split()[0]


    def get_arch(self):
        """
        Get the hardware architecture of the remote machine
        """
        arch = self.run('/bin/uname -m').stdout.rstrip()
        if re.match(r'i\d86$', arch):
            arch = 'i386'
        return arch


    def get_kernel_ver(self):
        """
        Get the kernel version of the remote machine
        """
        return self.run('/bin/uname -r').stdout.rstrip()


    def get_cmdline(self):
        """
        Get the kernel command line of the remote machine
        """
        return self.run('cat /proc/cmdline').stdout.rstrip()


    def ping(self):
        """
        Ping the remote system, and return whether it's available
        """
        fpingcmd = "%s -q %s" % ('/usr/bin/fping', self.hostname)
        rc = utils.system(fpingcmd, ignore_status = 1)
        return (rc == 0)


    def ssh_ping(self, timeout = 60):
        try:
            self.run('true', timeout = timeout, connect_timeout = timeout)
        except error.AutoservSSHTimeout:
            msg = "ssh ping timed out. timeout = %s" % timeout
            raise error.AutoservSSHTimeout(msg)
        except error.AutoservRunError, exc:
            msg = "command true failed in ssh ping"
            raise error.AutoservRunError(msg, exc.args[1])


    def get_autodir(self):
        return self.autodir


    def ssh_setup_key(self):
        try:
            print 'Performing ssh key setup on %s:%d as %s' % \
                (self.hostname, self.port, self.user)

            host = pxssh.pxssh()
            host.login(self.hostname, self.user, self.password, port=self.port)

            try:
                public_key = utils.get_public_key()

                host.sendline('mkdir -p ~/.ssh')
                host.prompt()
                host.sendline('chmod 700 ~/.ssh')
                host.prompt()
                host.sendline("echo '%s' >> ~/.ssh/authorized_keys; " %
                        (public_key))
                host.prompt()
                host.sendline('chmod 600 ~/.ssh/authorized_keys')
                host.prompt()

                print 'SSH key setup complete'

            finally:
                host.logout()

        except:
            pass


    def setup(self):
        super(SSHHost, self).setup()
        if not self.password == '':
            try:
                self.ssh_ping()
            except error.AutoservRunError:
                self.ssh_setup_key()
