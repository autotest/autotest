import glob
import logging
import os
import shutil
import socket
import tempfile
import time
import traceback

from autotest.client.shared import autotemp, error
from autotest.client.shared.settings import settings
from autotest.server import utils, autotest_remote
from autotest.server.hosts import remote

enable_master_ssh = settings.get_value('AUTOSERV', 'enable_master_ssh',
                                       type=bool, default=False)


def _make_ssh_cmd_default(user="root", port=22, opts='', hosts_file='/dev/null',
                          connect_timeout=30, alive_interval=300):
    base_command = ("/usr/bin/ssh -a -x %s -o StrictHostKeyChecking=no "
                    "-o UserKnownHostsFile=%s -o BatchMode=yes "
                    "-o ConnectTimeout=%d -o ServerAliveInterval=%d "
                    "-l %s -p %d")
    assert isinstance(connect_timeout, (int, long))
    assert connect_timeout > 0  # can't disable the timeout
    return base_command % (opts, hosts_file, connect_timeout,
                           alive_interval, user, port)


make_ssh_command = utils.import_site_function(
    __file__, "autotest.server.hosts.site_host", "make_ssh_command",
    _make_ssh_cmd_default)


# import site specific Host class
SiteHost = utils.import_site_class(
    __file__, "autotest.server.hosts.site_host", "SiteHost",
    remote.RemoteHost)


class AbstractSSHHost(SiteHost):

    """
    This class represents a generic implementation of most of the
    framework necessary for controlling a host via ssh. It implements
    almost all of the abstract Host methods, except for the core
    Host.run method.
    """

    def _initialize(self, hostname, user="root", port=22, password="",
                    *args, **dargs):
        super(AbstractSSHHost, self)._initialize(hostname=hostname,
                                                 *args, **dargs)
        self.ip = socket.getaddrinfo(self.hostname, None)[0][4][0]
        self.user = user
        self.port = port
        self.password = password
        self._use_rsync = None
        self.known_hosts_file = tempfile.mkstemp()[1]

        """
        Master SSH connection background job, socket temp directory and socket
        control path option. If master-SSH is enabled, these fields will be
        initialized by start_master_ssh when a new SSH connection is initiated.
        """
        self.master_ssh_job = None
        self.master_ssh_tempdir = None
        self.master_ssh_option = ''

    def use_rsync(self):
        if self._use_rsync is not None:
            return self._use_rsync

        # Check if rsync is available on the remote host. If it's not,
        # don't try to use it for any future file transfers.
        self._use_rsync = self._check_rsync()
        if not self._use_rsync:
            logging.warn("rsync not available on remote host %s -- disabled",
                         self.hostname)
        return self._use_rsync

    def _check_rsync(self):
        """
        Check if rsync is available on the remote host.
        """
        try:
            self.run("rsync --version", stdout_tee=None, stderr_tee=None)
        except error.AutoservRunError:
            return False
        return True

    def _encode_remote_paths(self, paths, escape=True):
        """
        Given a list of file paths, encodes it as a single remote path, in
        the style used by rsync and scp.
        """
        if escape:
            paths = [utils.scp_remote_escape(path) for path in paths]
        return '%s@%s:"%s"' % (self.user, self.hostname, " ".join(paths))

    def _make_rsync_cmd(self, sources, dest, delete_dest, preserve_symlinks):
        """
        Given a list of source paths and a destination path, produces the
        appropriate rsync command for copying them. Remote paths must be
        pre-encoded.
        """
        ssh_cmd = make_ssh_command(user=self.user, port=self.port,
                                   opts=self.master_ssh_option,
                                   hosts_file=self.known_hosts_file)
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

    def _make_ssh_cmd(self, cmd):
        """
        Create a base ssh command string for the host which can be used
        to run commands directly on the machine
        """
        base_cmd = make_ssh_command(user=self.user, port=self.port,
                                    opts=self.master_ssh_option,
                                    hosts_file=self.known_hosts_file)

        return '%s %s "%s"' % (base_cmd, self.hostname, utils.sh_escape(cmd))

    def _make_scp_cmd(self, sources, dest):
        """
        Given a list of source paths and a destination path, produces the
        appropriate scp command for encoding it. Remote paths must be
        pre-encoded.
        """
        command = ("scp -rq %s -o StrictHostKeyChecking=no "
                   "-o UserKnownHostsFile=%s -P %d %s '%s'")
        return command % (self.master_ssh_option, self.known_hosts_file,
                          self.port, " ".join(sources), dest)

    def _make_rsync_compatible_globs(self, path, is_local):
        """
        Given an rsync-style path, returns a list of globbed paths
        that will hopefully provide equivalent behaviour for scp. Does not
        support the full range of rsync pattern matching behaviour, only that
        exposed in the get/send_file interface (trailing slashes).

        The is_local param is flag indicating if the paths should be
        interpreted as local or remote paths.
        """

        # non-trailing slash paths should just work
        if len(path) == 0 or path[-1] != "/":
            return [path]

        # make a function to test if a pattern matches any files
        if is_local:
            def glob_matches_files(path, pattern):
                return len(glob.glob(path + pattern)) > 0
        else:
            def glob_matches_files(path, pattern):
                result = self.run("ls \"%s\"%s" % (utils.sh_escape(path),
                                                   pattern),
                                  stdout_tee=None, ignore_status=True)
                return result.exit_status == 0

        # take a set of globs that cover all files, and see which are needed
        patterns = ["*", ".[!.]*"]
        patterns = [p for p in patterns if glob_matches_files(path, p)]

        # convert them into a set of paths suitable for the commandline
        if is_local:
            return ["\"%s\"%s" % (utils.sh_escape(path), pattern)
                    for pattern in patterns]
        else:
            return [utils.scp_remote_escape(path) + pattern
                    for pattern in patterns]

    def _make_rsync_compatible_source(self, source, is_local):
        """
        Applies the same logic as _make_rsync_compatible_globs, but
        applies it to an entire list of sources, producing a new list of
        sources, properly quoted.
        """
        return sum((self._make_rsync_compatible_globs(path, is_local)
                    for path in source), [])

    def _set_umask_perms(self, dest):
        """
        Given a destination file/dir (recursively) set the permissions on
        all the files and directories to the max allowed by running umask.
        """

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

        # Start a master SSH connection if necessary.
        self.start_master_ssh()

        if isinstance(source, basestring):
            source = [source]
        dest = os.path.abspath(dest)

        # If rsync is disabled or fails, try scp.
        try_scp = True
        if self.use_rsync():
            try:
                remote_source = self._encode_remote_paths(source)
                local_dest = utils.sh_escape(dest)
                rsync = self._make_rsync_cmd([remote_source], local_dest,
                                             delete_dest, preserve_symlinks)
                utils.run(rsync)
                try_scp = False
            except error.CmdError as e:
                logging.warn("trying scp, rsync failed: %s" % e)

        if try_scp:
            # scp has no equivalent to --delete, just drop the entire dest dir
            if delete_dest and os.path.isdir(dest):
                shutil.rmtree(dest)
                os.mkdir(dest)

            remote_source = self._make_rsync_compatible_source(source, False)
            if remote_source:
                # _make_rsync_compatible_source() already did the escaping
                remote_source = self._encode_remote_paths(remote_source,
                                                          escape=False)
                local_dest = utils.sh_escape(dest)
                scp = self._make_scp_cmd([remote_source], local_dest)
                try:
                    utils.run(scp)
                except error.CmdError as e:
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

        # Start a master SSH connection if necessary.
        self.start_master_ssh()

        if isinstance(source, basestring):
            source_is_dir = os.path.isdir(source)
            source = [source]
        remote_dest = self._encode_remote_paths([dest])

        # If rsync is disabled or fails, try scp.
        try_scp = True
        if self.use_rsync():
            try:
                local_sources = [utils.sh_escape(path) for path in source]
                rsync = self._make_rsync_cmd(local_sources, remote_dest,
                                             delete_dest, preserve_symlinks)
                utils.run(rsync)
                try_scp = False
            except error.CmdError as e:
                logging.warn("trying scp, rsync failed: %s" % e)

        if try_scp:
            # scp has no equivalent to --delete, just drop the entire dest dir
            if delete_dest:
                dest_exists = False
                try:
                    self.run("test -x %s" % dest)
                    dest_exists = True
                except error.AutoservRunError:
                    pass

                dest_is_dir = False
                if dest_exists:
                    try:
                        self.run("test -d %s" % dest)
                        dest_is_dir = True
                    except error.AutoservRunError:
                        pass

                # If there is a list of more than one path, destination *has*
                # to be a dir. If there's a single path being transferred and
                # it is a dir, the destination also has to be a dir. Therefore
                # it has to be created on the remote machine in case it doesn't
                # exist, otherwise we will have an scp failure.
                if len(source) > 1 or source_is_dir:
                    dest_is_dir = True

                if dest_exists and dest_is_dir:
                    cmd = "rm -rf %s && mkdir %s" % (dest, dest)
                    self.run(cmd)

                elif not dest_exists and dest_is_dir:
                    cmd = "mkdir %s" % dest
                    self.run(cmd)

            local_sources = self._make_rsync_compatible_source(source, True)
            if local_sources:
                scp = self._make_scp_cmd(local_sources, remote_dest)
                try:
                    utils.run(scp)
                except error.CmdError as e:
                    raise error.AutoservRunError(e.args[0], e.args[1])

    def ssh_ping(self, timeout=60):
        try:
            # Complex inheritance confuses pylint here
            # pylint: disable=E1123
            self.run("true", timeout=timeout, connect_timeout=timeout)
        except error.AutoservSSHTimeout:
            msg = "Host (ssh) verify timed out (timeout = %d)" % timeout
            raise error.AutoservSSHTimeout(msg)
        except error.AutoservSshPermissionDeniedError:
            # let AutoservSshPermissionDeniedError be visible to the callers
            raise
        except error.AutoservRunError as e:
            # convert the generic AutoservRunError into something more
            # specific for this context
            raise error.AutoservSshPingHostError(e.description + '\n' +
                                                 repr(e.result_obj))

    def is_up(self):
        """
        Check if the remote host is up.

        :return: True if the remote host is up, False otherwise
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

        :param timeout time limit in seconds before returning even
            if the host is not up.

        :return: True if the host was found to be up, False otherwise
        """
        if timeout:
            end_time = time.time() + timeout

        while not timeout or time.time() < end_time:
            if self.is_up():
                try:
                    if self.are_wait_up_processes_up():
                        logging.debug('Host %s is now up', self.hostname)
                        return True
                except error.AutoservError:
                    pass
            time.sleep(1)

        logging.debug('Host %s is still down after waiting %d seconds',
                      self.hostname, int(timeout + time.time() - end_time))
        return False

    def wait_down(self, timeout=None, warning_timer=None, old_boot_id=None):
        """
        Wait until the remote host is down or the timeout expires.

        If old_boot_id is provided, this will wait until either the machine
        is unpingable or self.get_boot_id() returns a value different from
        old_boot_id. If the boot_id value has changed then the function
        returns true under the assumption that the machine has shut down
        and has now already come back up.

        If old_boot_id is None then until the machine becomes unreachable the
        method assumes the machine has not yet shut down.

        :param timeout Time limit in seconds before returning even
            if the host is still up.
        :param warning_timer Time limit in seconds that will generate
            a warning if the host is not down yet.
        :param old_boot_id A string containing the result of self.get_boot_id()
            prior to the host being told to shut down. Can be None if this is
            not available.

        :return: True if the host was found to be down, False otherwise
        """
        # TODO: there is currently no way to distinguish between knowing
        # TODO: boot_id was unsupported and not knowing the boot_id.
        current_time = time.time()
        if timeout:
            end_time = current_time + timeout

        if warning_timer:
            warn_time = current_time + warning_timer

        if old_boot_id is not None:
            logging.debug('Host %s pre-shutdown boot_id is %s',
                          self.hostname, old_boot_id)

        while not timeout or current_time < end_time:
            try:
                new_boot_id = self.get_boot_id()
            except error.AutoservError:
                logging.debug('Host %s is now unreachable over ssh, is down',
                              self.hostname)
                return True
            else:
                # if the machine is up but the boot_id value has changed from
                # old boot id, then we can assume the machine has gone down
                # and then already come back up
                if old_boot_id is not None and old_boot_id != new_boot_id:
                    logging.debug('Host %s now has boot_id %s and so must '
                                  'have rebooted', self.hostname, new_boot_id)
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
    AUTOTEST_GB_DISKSPACE_REQUIRED = settings.get_value("SERVER",
                                                        "gb_diskspace_required",
                                                        type=int,
                                                        default=20)

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
            self.check_diskspace(autotest_remote.Autotest.get_install_dir(self),
                                 self.AUTOTEST_GB_DISKSPACE_REQUIRED)
        except error.AutoservHostError:
            raise           # only want to raise if it's a space issue
        except autotest_remote.AutodirNotFoundError:
            # autotest_remote dir may not exist, etc. ignore
            logging.debug('autodir space check exception, this is probably '
                          'safe to ignore\n' + traceback.format_exc())

    def close(self):
        super(AbstractSSHHost, self).close()
        self._cleanup_master_ssh()
        os.remove(self.known_hosts_file)

    def _cleanup_master_ssh(self):
        """
        Release all resources (process, temporary directory) used by an active
        master SSH connection.
        """
        # If a master SSH connection is running, kill it.
        if self.master_ssh_job is not None:
            utils.nuke_subprocess(self.master_ssh_job.sp)
            self.master_ssh_job = None

        # Remove the temporary directory for the master SSH socket.
        if self.master_ssh_tempdir is not None:
            self.master_ssh_tempdir.clean()
            self.master_ssh_tempdir = None
            self.master_ssh_option = ''

    def start_master_ssh(self):
        """
        Called whenever a slave SSH connection needs to be initiated (e.g., by
        run, rsync, scp). If master SSH support is enabled and a master SSH
        connection is not active already, start a new one in the background.
        Also, cleanup any zombie master SSH connections (e.g., dead due to
        reboot).
        """
        if not enable_master_ssh:
            return

        # If a previously started master SSH connection is not running
        # anymore, it needs to be cleaned up and then restarted.
        if self.master_ssh_job is not None:
            if self.master_ssh_job.sp.poll() is not None:
                logging.info("Master ssh connection to %s is down.",
                             self.hostname)
                self._cleanup_master_ssh()

        # Start a new master SSH connection.
        if self.master_ssh_job is None:
            # Create a shared socket in a temp location.
            self.master_ssh_tempdir = autotemp.tempdir(unique_id='ssh-master')
            self.master_ssh_option = ("-o ControlPath=%s/socket" %
                                      self.master_ssh_tempdir.name)

            # Start the master SSH connection in the background.
            master_cmd = self.ssh_command(options="-N -o ControlMaster=yes")
            logging.info("Starting master ssh connection '%s'" % master_cmd)
            self.master_ssh_job = utils.BgJob(master_cmd)

    def clear_known_hosts(self):
        """Clears out the temporary ssh known_hosts file.

        This is useful if the test SSHes to the machine, then reinstalls it,
        then SSHes to it again.  It can be called after the reinstall to
        reduce the spam in the logs.
        """
        logging.info("Clearing known hosts for host '%s', file '%s'.",
                     self.hostname, self.known_hosts_file)
        # Clear out the file by opening it for writing and then closing.
        fh = open(self.known_hosts_file, "w")
        fh.close()
