#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the SSHHost class.

Implementation details:
You should import the "hosts" package instead of importing each type of host.

        SSHHost: a remote machine with a ssh access
"""

import types, os, sys, signal, subprocess, time, re, socket, pdb, traceback
from autotest_lib.client.common_lib import error, pxssh, global_config, debug
from autotest_lib.server import utils, autotest
from autotest_lib.server.hosts import site_host, bootloader

LAST_BOOT_TAG = object()


class PermissionDeniedError(error.AutoservRunError):
    pass


class SSHHost(site_host.SiteHost):
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

    DEFAULT_REBOOT_TIMEOUT = site_host.SiteHost.DEFAULT_REBOOT_TIMEOUT

    def __init__(self, hostname, user="root", port=22, autodir=None,
                 password='', target_file_owner=None, *args, **dargs):
        """
        Construct a SSHHost object

        Args:
                hostname: network hostname or address of remote machine
                user: user to log in as on the remote machine
                port: port the ssh daemon is listening on on the remote
                        machine
        """
        dargs["hostname"] = hostname
        super(SSHHost, self).__init__(*args, **dargs)

        self.ip = socket.getaddrinfo(self.hostname, None)[0][4][0]
        self.user = user
        self.port = port
        self.tmp_dirs = []
        self.autodir = autodir
        self.password = password
        self.ssh_host_log = debug.get_logger()

        self.start_loggers()


    def __del__(self):
        """
        Destroy a SSHHost object
        """
        super(SSHHost, self).__del__()

        self.stop_loggers()

        if hasattr(self, 'tmp_dirs'):
            for dir in self.tmp_dirs:
                try:
                    self.run('rm -rf "%s"' % (utils.sh_escape(dir)))
                except error.AutoservRunError:
                    pass


    def wait_for_restart(self, timeout=DEFAULT_REBOOT_TIMEOUT):
        """ Wait for the host to come back from a reboot. This wraps the
        generic wait_for_restart implementation in a reboot group. """
        def reboot_func():
            super(SSHHost, self).wait_for_restart(timeout=timeout)
        self.log_reboot(reboot_func)


    @staticmethod
    def ssh_base_command(connect_timeout=30):
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
        echo_cmd = "echo \`date '+%m/%d/%y %H:%M:%S'\` Connected. >&2"
        if not env.strip():
            env = ""
        else:
            env = "export %s;" % env
        full_cmd = '%s "%s;%s %s"' % (ssh_cmd, echo_cmd, env,
                                      utils.sh_escape(command))
        result = utils.run(full_cmd, timeout, True, stdout, stderr,
                           verbose=False)

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
            stdout_tee=None, stderr_tee=None, connect_timeout=30, options=''):
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
        self.ssh_host_log.debug("ssh: %s" % command)
        env = " ".join("=".join(pair) for pair in self.env.iteritems())
        try:
            try:
                return self._run(command, timeout,
                                 ignore_status, stdout,
                                 stderr, connect_timeout,
                                 env, options)
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


    def verify(self):
        super(SSHHost, self).verify()

        print 'Pinging host ' + self.hostname
        self.ssh_ping()

        try:
            autodir = autotest._get_autodir(self)
            if autodir:
                print 'Checking diskspace for %s on %s' % (self.hostname,
                                                           autodir)
                self.check_diskspace(autodir, 20)
        except error.AutoservHostError:
            raise           # only want to raise if it's a space issue
        except:
            pass            # autotest dir may not exist, etc. ignore


    def repair_filesystem_only(self):
        super(SSHHost, self).repair_filesystem_only()
        self.wait_up(int(2.5 * 60 * 60)) # wait for 2.5 hours
        self.reboot()


    def repair_full(self):
        super(SSHHost, self).repair_full()
        try:
            self.repair_filesystem_only()
            self.verify()
        except Exception:
            # the filesystem-only repair failed, try something more drastic
            print "Filesystem-only repair failed"
            traceback.print_exc()
            try:
                self.machine_install()
            except NotImplementedError, e:
                sys.stderr.write(str(e) + "\n\n")


    def sysrq_reboot(self):
        self.run('echo b > /proc/sysrq-trigger &')


    def reboot(self, timeout=DEFAULT_REBOOT_TIMEOUT, label=LAST_BOOT_TAG,
               kernel_args=None, wait=True, **dargs):
        """
        Reboot the remote host.

        Args:
                timeout - How long to wait for the reboot.
                label - The label we should boot into.  If None, we will
                        boot into the default kernel.  If it's LAST_BOOT_TAG,
                        we'll boot into whichever kernel was .boot'ed last
                        (or the default kernel if we haven't .boot'ed in this
                        job).  If it's None, we'll boot into the default kernel.
                        If it's something else, we'll boot into that.
                wait - Should we wait to see if the machine comes back up.
        """
        if self.job:
            if label == LAST_BOOT_TAG:
                label = self.job.last_boot_tag
            else:
                self.job.last_boot_tag = label
        
        self.reboot_setup(label=label, kernel_args=kernel_args, **dargs)

        if label or kernel_args:
            self.bootloader.install_boottool()
            if not label:
                default = int(self.bootloader.get_default())
                label = self.bootloader.get_titles()[default]
            self.bootloader.boot_once(label)
            if kernel_args:
                self.bootloader.add_args(label, kernel_args)

        # define a function for the reboot and run it in a group
        print "Reboot: initiating reboot"
        def reboot():
            self.record("GOOD", None, "reboot.start")
            try:
                self.run('(sleep 5; reboot) '
                         '</dev/null >/dev/null 2>&1 &')
            except error.AutoservRunError:
                self.record("ABORT", None, "reboot.start",
                              "reboot command failed")
                raise
            if wait:
                self.wait_for_restart(timeout)
                self.reboot_followup(**dargs)

        # if this is a full reboot-and-wait, run the reboot inside a group
        if wait:
            self.log_reboot(reboot)
        else:
            reboot()


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
            utils.run('rsync -L --rsh="%s -p %d" -az %s %s' % (
                self.ssh_base_command(), self.port, ' '.join(sources), dest))
        except Exception, e:
            print "warning: rsync failed with: %s" % e
            print "attempting to copy with scp instead"
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
        self.run('find "%s" -type d -print0 | xargs -0r chmod o+rx' % dest)
        self.run('find "%s" -type f -print0 | xargs -0r chmod o+r' % dest)
        if self.target_file_owner:
            self.run('chown -R %s %s' % (self.target_file_owner, dest))


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
            exit_status = self.run("{ ps -e || ps; } | grep '%s'" % procname,
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


    def check_uptime(self):
        """
        Check that uptime is available and monotonically increasing.
        """
        if not self.ping():
            raise error.AutoservHostError('Client is not pingable')
        result = self.run("/bin/cat /proc/uptime", 30)
        return result.stdout.strip().split()[0]


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


    def set_autodir(self, autodir):
        '''
        This method is called to make the host object aware of the
        where autotest is installed. Called in server/autotest.py
        after a successful install
        '''
        self.autodir = autodir


    def get_crashinfo(self, test_start_time):
        print "Collecting crash information..."
        super(SSHHost, self).get_crashinfo(test_start_time)

        # wait for four hours, to see if the machine comes back up
        current_time = time.strftime("%b %d %H:%M:%S", time.localtime())
        print "Waiting four hours for %s to come up (%s)" % (self.hostname,
                                                             current_time)
        if not self.wait_up(timeout=4*60*60):
            print "%s down, unable to collect crash info" % self.hostname
            return
        else:
            print "%s is back up, collecting crash info" % self.hostname

        # find a directory to put the crashinfo into
        if self.job:
            infodir = self.job.resultdir
        else:
            infodir = os.path.abspath(os.getcwd())
        infodir = os.path.join(infodir, "crashinfo.%s" % self.hostname)
        if not os.path.exists(infodir):
            os.mkdir(infodir)

        # collect various log files
        log_files = ["/var/log/messages", "/var/log/monitor-ssh-reboots"]
        for log in log_files:
            print "Collecting %s..." % log
            try:
                self.get_file(log, infodir)
            except Exception, e:
                print "crashinfo collection of %s failed with:\n%s" % (log, e)

        # collect dmesg
        print "Collecting dmesg..."
        try:
            result = self.run("dmesg").stdout
            file(os.path.join(infodir, "dmesg"), "w").write(result)
        except Exception, e:
            print "crashinfo collection of dmesg failed with:\n%s" % e


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
