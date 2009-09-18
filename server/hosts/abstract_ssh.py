import os, time, types, socket, shutil, glob, logging, traceback
from autotest_lib.client.common_lib import error, logging_manager
from autotest_lib.server import utils, autotest
from autotest_lib.server.hosts import remote


def make_ssh_command(user="root", port=22, opts='', connect_timeout=30):
    base_command = ("/usr/bin/ssh -a -x %s -o BatchMode=yes "
                    "-o ConnectTimeout=%d -o ServerAliveInterval=300 "
                    "-l %s -p %d")
    assert isinstance(connect_timeout, (int, long))
    assert connect_timeout > 0 # can't disable the timeout
    return base_command % (opts, connect_timeout, user, port)


# import site specific Host class
SiteHost = utils.import_site_class(
    __file__, "autotest_lib.server.hosts.site_host", "SiteHost",
    remote.RemoteHost)


# this constant can be passed to run() to tee stdout/stdout to the logging
# module.
TEE_TO_LOGS = object()


class AbstractSSHHost(SiteHost):
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


    def _encode_remote_paths(self, paths):
        """ Given a list of file paths, encodes it as a single remote path, in
        the style used by rsync and scp. """
        escaped_paths = [utils.scp_remote_escape(path) for path in paths]
        return '%s@%s:"%s"' % (self.user, self.hostname,
                               " ".join(escaped_paths))


    def _make_rsync_cmd(self, sources, dest, delete_dest, preserve_symlinks):
        """ Given a list of source paths and a destination path, produces the
        appropriate rsync command for copying them. Remote paths must be
        pre-encoded. """
        ssh_cmd = make_ssh_command(self.user, self.port)
        if delete_dest:
            delete_flag = "--delete"
        else:
            delete_flag = ""
        if preserve_symlinks:
            symlink_flag = ""
        else:
            symlink_flag = "-L"
        command = "rsync %s %s --timeout=1800 --rsh='%s' -az %s %s"
        return command % (symlink_flag, delete_flag, ssh_cmd,
                          " ".join(sources), dest)


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


    def _set_umask_perms(self, dest):
        """Given a destination file/dir (recursively) set the permissions on
        all the files and directories to the max allowed by running umask."""

        # now this looks strange but I haven't found a way in Python to _just_
        # get the umask, apparently the only option is to try to set it
        umask = os.umask(0)
        os.umask(umask)

        max_privs = 0777 & ~umask

        def set_file_privs(filename):
            file_stat = os.stat(filename)

            file_privs = max_privs
            # if the original file permissions do not have at least one
            # executable bit then do not set it anywhere
            if not file_stat.st_mode & 0111:
                file_privs &= ~0111

            os.chmod(filename, file_privs)

        # try a bottom-up walk so changes on directory permissions won't cut
        # our access to the files/directories inside it
        for root, dirs, files in os.walk(dest, topdown=False):
            # when setting the privileges we emulate the chmod "X" behaviour
            # that sets to execute only if it is a directory or any of the
            # owner/group/other already has execute right
            for dirname in dirs:
                os.chmod(os.path.join(root, dirname), max_privs)

            for filename in files:
                set_file_privs(os.path.join(root, filename))


        # now set privs for the dest itself
        if os.path.isdir(dest):
            os.chmod(dest, max_privs)
        else:
            set_file_privs(dest)


    def get_file(self, source, dest, delete_dest=False, preserve_perm=True,
                 preserve_symlinks=False):
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
                preserve_perm: tells get_file() to try to preserve the sources
                               permissions on files and dirs
                preserve_symlinks: try to preserve symlinks instead of
                                   transforming them into files/dirs on copy

        Raises:
                AutoservRunError: the scp command failed
        """
        if isinstance(source, basestring):
            source = [source]
        dest = os.path.abspath(dest)

        try:
            remote_source = self._encode_remote_paths(source)
            local_dest = utils.sh_escape(dest)
            rsync = self._make_rsync_cmd([remote_source], local_dest,
                                         delete_dest, preserve_symlinks)
            utils.run(rsync)
        except error.CmdError, e:
            logging.warn("warning: rsync failed with: %s", e)
            logging.info("attempting to copy with scp instead")

            # scp has no equivalent to --delete, just drop the entire dest dir
            if delete_dest and os.path.isdir(dest):
                shutil.rmtree(dest)
                os.mkdir(dest)

            remote_source = self._make_rsync_compatible_source(source, False)
            if remote_source:
                remote_source = self._encode_remote_paths(remote_source)
                local_dest = utils.sh_escape(dest)
                scp = self._make_scp_cmd([remote_source], local_dest)
                try:
                    utils.run(scp)
                except error.CmdError, e:
                    raise error.AutoservRunError(e.args[0], e.args[1])

        if not preserve_perm:
            # we have no way to tell scp to not try to preserve the
            # permissions so set them after copy instead.
            # for rsync we could use "--no-p --chmod=ugo=rwX" but those
            # options are only in very recent rsync versions
            self._set_umask_perms(dest)


    def send_file(self, source, dest, delete_dest=False,
                  preserve_symlinks=False):
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
                preserve_symlinks: controls if symlinks on the source will be
                    copied as such on the destination or transformed into the
                    referenced file/directory

        Raises:
                AutoservRunError: the scp command failed
        """
        if isinstance(source, basestring):
            source = [source]
        remote_dest = self._encode_remote_paths([dest])

        try:
            local_sources = [utils.sh_escape(path) for path in source]
            rsync = self._make_rsync_cmd(local_sources, remote_dest,
                                         delete_dest, preserve_symlinks)
            utils.run(rsync)
        except error.CmdError, e:
            logging.warn("Command rsync failed with: %s", e)
            logging.info("Attempting to copy with scp instead")

            # scp has no equivalent to --delete, just drop the entire dest dir
            if delete_dest:
                is_dir = self.run("ls -d %s/" % dest,
                                  ignore_status=True).exit_status == 0
                if is_dir:
                    cmd = "rm -rf %s && mkdir %s"
                    cmd %= (dest, dest)
                    self.run(cmd)

            local_sources = self._make_rsync_compatible_source(source, True)
            if local_sources:
                scp = self._make_scp_cmd(local_sources, remote_dest)
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
        except error.AutoservSSHTimeout:
            msg = "Host (ssh) verify timed out (timeout = %d)" % timeout
            raise error.AutoservSSHTimeout(msg)
        except error.AutoservSshPermissionDeniedError:
            #let AutoservSshPermissionDeniedError be visible to the callers
            raise
        except error.AutoservRunError, e:
            # convert the generic AutoservRunError into something more
            # specific for this context
            raise error.AutoservSshPingHostError(e.description + '\n' +
                                                 repr(e.result_obj))


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


    def wait_down(self, timeout=None, warning_timer=None):
        """
        Wait until the remote host is down or the timeout expires.

        In fact, it will wait until an ssh connection to the remote
        host fails.

        Args:
            timeout: time limit in seconds before returning even
                     if the host is still up.
            warning_timer: time limit in seconds that will generate
                     a warning if the host is not down yet.

        Returns:
                True if the host was found to be down, False otherwise
        """
        current_time = time.time()
        if timeout:
            end_time = current_time + timeout

        if warning_timer:
            warn_time = current_time + warning_timer

        while not timeout or current_time < end_time:
            if not self.is_up():
                return True

            if warning_timer and current_time > warn_time:
                self.record("WARN", None, "shutdown",
                            "Shutdown took longer than %ds" % warning_timer)
                # Print the warning only once.
                warning_timer = None
                # If a machine is stuck switching runlevels
                # This may cause the machine to reboot.
                self.run('kill -HUP 1', ignore_status=True)

            time.sleep(1)
            current_time = time.time()

        return False


    # tunable constants for the verify & repair code
    AUTOTEST_GB_DISKSPACE_REQUIRED = 20


    def verify_connectivity(self):
        super(AbstractSSHHost, self).verify_connectivity()

        logging.info('Pinging host ' + self.hostname)
        self.ssh_ping()
        logging.info("Host (ssh) %s is alive", self.hostname)

        if self.is_shutting_down():
            raise error.AutoservHostIsShuttingDownError("Host is shutting down")


    def verify_software(self):
        super(AbstractSSHHost, self).verify_software()
        try:
            autodir = autotest._get_autodir(self)
            if autodir:
                self.check_diskspace(autodir,
                                     self.AUTOTEST_GB_DISKSPACE_REQUIRED)
        except error.AutoservHostError:
            raise           # only want to raise if it's a space issue
        except Exception:
            # autotest dir may not exist, etc. ignore
            logging.debug('autodir space check exception, this is probably '
                          'safe to ignore\n' + traceback.format_exc())
