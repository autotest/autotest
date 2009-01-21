import os, sys, time, types, socket, traceback, shutil, glob
from autotest_lib.client.common_lib import error, debug
from autotest_lib.server import utils, autotest
from autotest_lib.server.hosts import site_host


def make_ssh_command(user="root", port=22, opts='', connect_timeout=30):
    base_command = ("/usr/bin/ssh -a -x %s -o BatchMode=yes "
                    "-o ConnectTimeout=%d -o ServerAliveInterval=300 "
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
        self.ip = socket.getaddrinfo(self.hostname, None)[0][4][0]
        self.user = user
        self.port = port
        self.password = password


    def _encode_remote_path(self, path):
        """ Given a file path, encodes it as a remote path, in the style used
        by rsync and scp. """
        return '%s@%s:"%s"' % (self.user, self.hostname,
                               utils.scp_remote_escape(path))


    def _make_rsync_cmd(self, sources, dest, delete_dest):
        """ Given a list of source paths and a destination path, produces the
        appropriate rsync command for copying them. Remote paths must be
        pre-encoded. """
        ssh_cmd = make_ssh_command(self.user, self.port)
        if delete_dest:
            delete_flag = "--delete"
        else:
            delete_flag = ""
        command = "rsync -L %s --rsh='%s' -az %s %s"
        return command % (delete_flag, ssh_cmd, " ".join(sources), dest)


    def _make_scp_cmd(self, sources, dest):
        """ Given a list of source paths and a destination path, produces the
        appropriate scp command for encoding it. Remote paths must be
        pre-encoded. """
        command = "scp -rpq -P %d %s '%s'"
        return command % (self.port, " ".join(sources), dest)


    def _make_rsync_compatible_globs(self, path, is_local):
        """ Given an rsync-style path, returns a list of globbed paths
        that will hopefully provide equivalent behaviour for scp. Does not
        support the full range of rsync pattern matching behaviour, only that
        exposed in the get/send_file interface (trailing slashes).

        The is_local param is flag indicating if the paths should be
        interpreted as local or remote paths. """

        # non-trailing slash paths should just work
        if len(path) == 0 or path[-1] != "/":
            return [path]

        # make a function to test if a pattern matches any files
        if is_local:
            def glob_matches_files(path):
                return len(glob.glob(path)) > 0
        else:
            def glob_matches_files(path):
                result = self.run("ls \"%s\"" % utils.sh_escape(path),
                                  ignore_status=True)
                return result.exit_status == 0

        # take a set of globs that cover all files, and see which are needed
        patterns = ["*", ".[!.]*"]
        patterns = [p for p in patterns if glob_matches_files(path + p)]

        # convert them into a set of paths suitable for the commandline
        path = utils.sh_escape(path)
        if is_local:
            return ["\"%s\"%s" % (path, pattern) for pattern in patterns]
        else:
            return ["\"%s\"" % (path + pattern) for pattern in patterns]


    def _make_rsync_compatible_source(self, source, is_local):
        """ Applies the same logic as _make_rsync_compatible_globs, but
        applies it to an entire list of sources, producing a new list of
        sources, properly quoted. """
        return sum((self._make_rsync_compatible_globs(path, is_local)
                    for path in source), [])


    def get_file(self, source, dest, delete_dest=False):
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
                delete_dest: if this is true, the command will also clear
                             out any old files at dest that are not in the
                             source

        Raises:
                AutoservRunError: the scp command failed
        """
        if isinstance(source, basestring):
            source = [source]
        dest = os.path.abspath(dest)

        try:
            remote_source = [self._encode_remote_path(p) for p in source]
            local_dest = utils.sh_escape(dest)
            rsync = self._make_rsync_cmd(remote_source, local_dest,
                                         delete_dest)
            utils.run(rsync)
        except error.CmdError, e:
            print "warning: rsync failed with: %s" % e
            print "attempting to copy with scp instead"

            # scp has no equivalent to --delete, just drop the entire dest dir
            if delete_dest and os.path.isdir(dest):
                shutil.rmtree(dest)
                os.mkdir(dest)

            remote_source = self._make_rsync_compatible_source(source, False)
            if remote_source:
                local_dest = utils.sh_escape(dest)
                scp = self._make_scp_cmd(remote_source, local_dest)
                try:
                    utils.run(scp)
                except error.CmdError, e:
                    raise error.AutoservRunError(e.args[0], e.args[1])


    def send_file(self, source, dest, delete_dest=False):
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
                delete_dest: if this is true, the command will also clear
                             out any old files at dest that are not in the
                             source

        Raises:
                AutoservRunError: the scp command failed
        """
        if isinstance(source, basestring):
            source = [source]
        remote_dest = self._encode_remote_path(dest)

        try:
            local_source = [utils.sh_escape(path) for path in source]
            rsync = self._make_rsync_cmd(local_source, remote_dest,
                                         delete_dest)
            utils.run(rsync)
        except error.CmdError, e:
            print "warning: rsync failed with: %s" % e
            print "attempting to copy with scp instead"

            # scp has no equivalent to --delete, just drop the entire dest dir
            if delete_dest:
                is_dir = self.run("ls -d %s/" % remote_dest,
                                  ignore_status=True).exit_status == 0
                if is_dir:
                    cmd = "rm -rf %s && mkdir %s"
                    cmd %= (remote_dest, remote_dest)
                    self.run(cmd)

            local_source = self._make_rsync_compatible_source(source, True)
            if local_source:
                scp = self._make_scp_cmd(local_source, remote_dest)
                try:
                    utils.run(scp)
                except error.CmdError, e:
                    raise error.AutoservRunError(e.args[0], e.args[1])

        self.run('find "%s" -type d -print0 | xargs -0r chmod o+rx' % dest)
        self.run('find "%s" -type f -print0 | xargs -0r chmod o+r' % dest)
        if self.target_file_owner:
            self.run('chown -R %s %s' % (self.target_file_owner, dest))


    def ssh_ping(self, timeout=60):
        try:
            self.run("true", timeout=timeout, connect_timeout=timeout)
            print "ssh_ping of %s completed sucessfully" % self.hostname
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

        if self.is_shutting_down():
            raise error.AutoservHostError("Host is shutting down")

        try:
            autodir = autotest._get_autodir(self)
            if autodir:
                self.check_diskspace(autodir,
                                     self.AUTOTEST_GB_DISKSPACE_REQUIRED)
        except error.AutoservHostError:
            raise           # only want to raise if it's a space issue
        except Exception:
            pass            # autotest dir may not exist, etc. ignore


    def repair_filesystem_only(self):
        super(AbstractSSHHost, self).repair_filesystem_only()

        TIMEOUT = int(self.HOURS_TO_WAIT_FOR_RECOVERY * 3600)
        if self.is_shutting_down():
            print 'Host is shutting down, waiting for a restart'
            self.wait_for_restart(TIMEOUT)
        else:
            self.wait_up(TIMEOUT)
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


class LoggerFile(object):
    def write(self, data):
        if data:
            debug.get_logger().debug(data.rstrip("\n"))


    def flush(self):
        pass
