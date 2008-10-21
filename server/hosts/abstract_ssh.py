import os, time, types
from autotest_lib.client.common_lib import error
from autotest_lib.server import utils
from autotest_lib.server.hosts import site_host


def make_ssh_command(user="root", port=22, opts='', connect_timeout=30):
    base_command = ("/usr/bin/ssh -a -x %s -o BatchMode=yes "
                    "-o ConnectTimeout=%d "
                    "-o ServerAliveInterval=300 "
                    "-l %s -p %d")
    assert isinstance(connect_timeout, (int, long))
    assert connect_timeout > 0 # can't disable the timeout
    return base_command % (opts, connect_timeout, user, port)


class AbstractSSHHost(site_host.SiteHost):
    """ This class represents a generic implementation of most of the
    framework necessary for controlling a host via ssh. It implements
    almost all of the abstract Host methods, except for the core
    Host.run method. """

    def _initialize(self, hostname, user="root", port=22, password="",
                    *args, **dargs):
        super(AbstractSSHHost, self)._initialize(hostname=hostname,
                                                 *args, **dargs)

        self.user = user
        self.port = port
        self.password = password


    def _copy_files(self, sources, dest):
        """
        Copy files from one machine to another.

        This is for internal use by other methods that intend to move
        files between machines. It expects a list of source files and
        a destination (a filename if the source is a single file, a
        destination otherwise). The names must already be
        pre-processed into the appropriate rsync/scp friendly
        format (%s@%s:%s).
        """

        print '_copy_files: copying %s to %s' % (sources, dest)
        try:
            ssh = make_ssh_command(self.user, self.port)
            command = "rsync -L --rsh='%s' -az %s %s"
            command %= (ssh, " ".join(sources), dest)
            utils.run(command)
        except Exception, e:
            print "warning: rsync failed with: %s" % e
            print "attempting to copy with scp instead"
            try:
                command = "scp -rpq -P %d %s '%s'"
                command %= (self.port, ' '.join(sources), dest)
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
        if isinstance(source, basestring):
            source = [source]

        processed_source = []
        for path in source:
            if path.endswith('/'):
                format_string = '%s@%s:"%s*"'
            else:
                format_string = '%s@%s:"%s"'
            entry = format_string % (self.user, self.hostname,
                                     utils.scp_remote_escape(path))
            processed_source.append(entry)

        processed_dest = utils.sh_escape(os.path.abspath(dest))
        if os.path.isdir(dest):
            processed_dest += "/"

        self._copy_files(processed_source, processed_dest)


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
        if isinstance(source, basestring):
            source = [source]

        processed_source = []
        for path in source:
            if path.endswith('/'):
                format_string = '"%s/"*'
            else:
                format_string = '"%s"'
            entry = format_string % (utils.sh_escape(os.path.abspath(path)),)
            processed_source.append(entry)

        remote_dest = '%s@%s:"%s"' % (self.user, self.hostname,
                                      utils.scp_remote_escape(dest))

        self._copy_files(processed_source, remote_dest)
        self.run('find "%s" -type d -print0 | xargs -0r chmod o+rx' % dest)
        self.run('find "%s" -type f -print0 | xargs -0r chmod o+r' % dest)
        if self.target_file_owner:
            self.run('chown -R %s %s' % (self.target_file_owner, dest))


    def ssh_ping(self, timeout=60):
        try:
            self.run("true", timeout=timeout, connect_timeout=timeout)
        except error.AutoservSSHTimeout:
            msg = "ssh ping timed out (timeout = %d)" % timeout
            raise error.AutoservSSHTimeout(msg)
        except error.AutoservRunError, e:
            msg = "command true failed in ssh ping"
            raise error.AutoservRunError(msg, e.result_obj)


    def is_up(self):
        """
        Check if the remote host is up.

        Returns:
                True if the remote host is up, False otherwise
        """
        try:
            self.ssh_ping()
        except error.AutoservError:
            return False
        else:
            return True


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
            end_time = time.time() + timeout

        while not timeout or time.time() < end_time:
            if self.is_up():
                try:
                    if self.are_wait_up_processes_up():
                        return True
                except error.AutoservError:
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
            end_time = time.time() + timeout

        while not timeout or time.time() < end_time:
            if not self.is_up():
                return True
            time.sleep(1)

        return False

    # tunable constants for the verify & repair code
    AUTOTEST_GB_DISKSPACE_REQUIRED = 20
    HOURS_TO_WAIT_FOR_RECOVERY = 2.5

    def verify(self):
        super(AbstractSSHHost, self).verify()

        print 'Pinging host ' + self.hostname
        self.ssh_ping()

        try:
            autodir = autotest._get_autodir(self)
            if autodir:
                print 'Checking diskspace for %s on %s' % (self.hostname,
                                                           autodir)
                self.check_diskspace(autodir,
                                     self.AUTOTEST_GB_DISKSPACE_REQUIRED)
        except error.AutoservHostError:
            raise           # only want to raise if it's a space issue
        except Exception:
            pass            # autotest dir may not exist, etc. ignore


    def repair_filesystem_only(self):
        super(AbstractSSHHost, self).repair_filesystem_only()
        self.wait_up(int(self.HOURS_TO_WAIT_FOR_RECOVERY * 3600))
        self.reboot()


    def repair_full(self):
        super(AbstractSSHHost, self).repair_full()
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
