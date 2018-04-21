"""This class defines the Remote host class, mixing in the SiteHost class
if it is available."""

import logging
import os
import socket
import time
import urllib

from autotest.client.shared import error
from autotest.client.shared.settings import settings
from autotest.server import utils
from autotest.server.hosts import base_classes, install_server


class InstallServerUnavailable(Exception):
    pass


def get_install_server_info():
    server_info = {}
    settings.parse_config_file()
    for option, value in settings.config.items('INSTALL_SERVER'):
        server_info[option] = value

    return server_info


def install_server_is_configured():
    server_info = get_install_server_info()
    if server_info.get('xmlrpc_url', None):
        return True
    return False


class RemoteHost(base_classes.Host):

    """
    This class represents a remote machine on which you can run
    programs.

    It may be accessed through a network, a serial line, ...
    It is not the machine autoserv is running on.

    Implementation details:
    This is an abstract class, leaf subclasses must implement the methods
    listed here and in parent classes which have no implementation. They
    may reimplement methods which already have an implementation. You
    must not instantiate this class but should instantiate one of those
    leaf subclasses.
    """

    DEFAULT_REBOOT_TIMEOUT = base_classes.Host.DEFAULT_REBOOT_TIMEOUT
    LAST_BOOT_TAG = object()
    DEFAULT_HALT_TIMEOUT = 2 * 60

    VAR_LOG_MESSAGES_COPY_PATH = "/var/tmp/messages.autotest_start"

    VAR_LOG_MESSAGES_PATHS = ["/var/log/messages", "/var/log/syslog"]

    INSTALL_SERVER_MAPPING = {'cobbler': install_server.CobblerInterface}

    def _initialize(self, hostname, autodir=None, profile='',
                    *args, **dargs):
        super(RemoteHost, self)._initialize(*args, **dargs)

        self.hostname = hostname
        self.autodir = autodir
        self.profile = profile
        self.tmp_dirs = []

    def __repr__(self):
        return "<remote host: %s, profile: %s>" % (self.hostname,
                                                   self.profile)

    def close(self):
        super(RemoteHost, self).close()
        self.stop_loggers()

        if hasattr(self, 'tmp_dirs'):
            for dir in self.tmp_dirs:
                try:
                    self.run('rm -rf "%s"' % (utils.sh_escape(dir)))
                except error.AutoservRunError:
                    pass

    def machine_install(self, profile='', timeout=None):
        """
        Install a profile using the install server.

        :param profile: Profile name inside the install server database.
        """
        if timeout is None:
            timeout = settings.get_value('INSTALL_SERVER',
                                         'default_install_timeout',
                                         type=int,
                                         default=3600)
        server_info = get_install_server_info()
        if install_server_is_configured():
            if not profile:
                profile = self.profile
            if profile in ['Do_not_install', 'N/A']:
                return
            num_attempts = int(server_info.get('num_attempts', 2))
            ServerInterface = self.INSTALL_SERVER_MAPPING[server_info['type']]
            end_time = time.time() + (timeout / 10)
            step = int(timeout / 100)
            server_interface = None
            while time.time() < end_time:
                try:
                    server_interface = ServerInterface(**server_info)
                    break
                except socket.error:
                    logging.error('Install server unavailable. Trying '
                                  'again in %s s...', step)
                    time.sleep(step)

            if server_interface is None:
                raise InstallServerUnavailable("%s install server at (%s) "
                                               "unavailable. Tried to "
                                               "communicate for %s s" %
                                               (server_info['type'],
                                                server_info['xmlrpc_url'],
                                                timeout / 10))

            server_interface.install_host(self, profile=profile,
                                          timeout=timeout,
                                          num_attempts=num_attempts)

    def hardreset(self, timeout=DEFAULT_REBOOT_TIMEOUT, wait=True,
                  num_attempts=1, halt=False, **wait_for_restart_kwargs):
        """
        Reboot the machine using the install server.

        :params timeout: timelimit in seconds before the machine is
                         considered unreachable
        :params wait: Whether or not to wait for the machine to reboot
        :params num_attempts: Number of times to attempt hard reset erroring
                              on the last attempt.
        :params halt: Halts the machine before hardresetting.
        :params **wait_for_restart_kwargs: keyword arguments passed to
                wait_for_restart()
        """
        server_info = get_install_server_info()

        if server_info.get('xmlrpc_url', None) is not None:
            ServerInterface = self.INSTALL_SERVER_MAPPING[server_info['type']]
            server_interface = ServerInterface(**server_info)
            try:
                old_boot_id = self.get_boot_id()
            except error.AutoservSSHTimeout:
                old_boot_id = 'unknown boot_id prior to RemoteHost.hardreset'

            def reboot():
                power_state = "reboot"
                if halt:
                    self.halt()
                    power_state = "on"
                server_interface.power_host(host=self, state=power_state)
                self.record("GOOD", None, "reboot.start", "hard reset")
                if wait:
                    warning_msg = ('Machine failed to respond to hard reset '
                                   'attempt (%s/%s)')
                    for attempt in xrange(num_attempts - 1):
                        try:
                            self.wait_for_restart(timeout, log_failure=False,
                                                  old_boot_id=old_boot_id,
                                                  **wait_for_restart_kwargs)
                        except error.AutoservShutdownError:
                            logging.warning(warning_msg, attempt + 1,
                                            num_attempts)
                            # re-send the hard reset command
                            server_interface.power_host(host=self,
                                                        state=power_state)
                        else:
                            break
                    else:
                        # Run on num_attempts=1 or last retry
                        try:
                            self.wait_for_restart(timeout,
                                                  old_boot_id=old_boot_id,
                                                  **wait_for_restart_kwargs)
                        except error.AutoservShutdownError:
                            logging.warning(warning_msg, num_attempts,
                                            num_attempts)
                            msg = "Host did not shutdown"
                            raise error.AutoservShutdownError(msg)

            if self.job:
                self.job.disable_warnings("POWER_FAILURE")
            try:
                if wait:
                    self.log_reboot(reboot)
                else:
                    reboot()
            finally:
                if self.job:
                    self.job.enable_warnings("POWER_FAILURE")

        else:
            raise error.AutoservUnsupportedError("Empty install server setup "
                                                 "on global_config.ini")

    def _var_log_messages_path(self):
        """
        Find possible paths for a messages file.
        """
        for path in self.VAR_LOG_MESSAGES_PATHS:
            try:
                self.run('test -f %s' % path)
                logging.debug("Found remote path %s", path)
                return path
            except Exception:
                logging.debug("Remote path %s is missing", path)

        return None

    def job_start(self):
        """
        Abstract method, called the first time a remote host object
        is created for a specific host after a job starts.

        This method depends on the create_host factory being used to
        construct your host object. If you directly construct host objects
        you will need to call this method yourself (and enforce the
        single-call rule).
        """
        messages_file = self._var_log_messages_path()
        if messages_file is not None:
            try:
                self.run('rm -f %s' % self.VAR_LOG_MESSAGES_COPY_PATH)
                self.run('cp %s %s' % (messages_file,
                                       self.VAR_LOG_MESSAGES_COPY_PATH))
            except Exception, e:
                # Non-fatal error
                logging.info('Failed to copy %s at startup: %s',
                             messages_file, e)
        else:
            logging.info("No remote messages path found, looked %s",
                         self.VAR_LOG_MESSAGES_PATHS)

    def get_autodir(self):
        return self.autodir

    def set_autodir(self, autodir):
        """
        This method is called to make the host object aware of the
        where autotest is installed. Called in server/autotest.py
        after a successful install
        """
        self.autodir = autodir

    def sysrq_reboot(self):
        self.run('echo b > /proc/sysrq-trigger &')

    def halt(self, timeout=DEFAULT_HALT_TIMEOUT, wait=True):
        self.run('/sbin/halt')
        if wait:
            self.wait_down(timeout=timeout)

    def reboot(self, timeout=DEFAULT_REBOOT_TIMEOUT, label=LAST_BOOT_TAG,
               kernel_args=None, wait=True, fastsync=False,
               reboot_cmd=None, **dargs):
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
                fastsync - Don't wait for the sync to complete, just start one
                        and move on. This is for cases where rebooting prompty
                        is more important than data integrity and/or the
                        machine may have disks that cause sync to never return.
                reboot_cmd - Reboot command to execute.
        """
        if self.job:
            if label == self.LAST_BOOT_TAG:
                label = self.job.last_boot_tag
            else:
                self.job.last_boot_tag = label

        self.reboot_setup(label=label, kernel_args=kernel_args, **dargs)

        if label or kernel_args:
            if not label:
                label = self.bootloader.get_default_title()
            self.bootloader.boot_once(label)
            if kernel_args:
                self.bootloader.add_args(label, kernel_args)

        # define a function for the reboot and run it in a group
        print("Reboot: initiating reboot")

        def reboot():
            self.record("GOOD", None, "reboot.start")
            try:
                current_boot_id = self.get_boot_id()

                # sync before starting the reboot, so that a long sync during
                # shutdown isn't timed out by wait_down's short timeout
                if not fastsync:
                    self.run('sync; sync', timeout=timeout, ignore_status=True)

                if reboot_cmd:
                    self.run(reboot_cmd)
                else:
                    # Try several methods of rebooting in increasing harshness.
                    self.run('(('
                             ' sync &'
                             ' sleep 5; reboot &'
                             ' sleep 60; reboot -f &'
                             ' sleep 10; reboot -nf &'
                             ' sleep 10; telinit 6 &'
                             ') </dev/null >/dev/null 2>&1 &)')
            except error.AutoservRunError:
                self.record("ABORT", None, "reboot.start",
                            "reboot command failed")
                raise
            if wait:
                self.wait_for_restart(timeout, old_boot_id=current_boot_id,
                                      **dargs)

        # if this is a full reboot-and-wait, run the reboot inside a group
        if wait:
            self.log_reboot(reboot)
        else:
            reboot()

    def reboot_followup(self, *args, **dargs):
        super(RemoteHost, self).reboot_followup(*args, **dargs)
        if self.job:
            self.job.profilers.handle_reboot(self)

    def wait_for_restart(self, timeout=DEFAULT_REBOOT_TIMEOUT, **dargs):
        """
        Wait for the host to come back from a reboot. This wraps the
        generic wait_for_restart implementation in a reboot group.
        """
        def reboot_func():
            super(RemoteHost, self).wait_for_restart(timeout=timeout, **dargs)
        self.log_reboot(reboot_func)

    def cleanup(self):
        super(RemoteHost, self).cleanup()
        self.reboot()

    def get_tmp_dir(self, parent='/tmp'):
        """
        Return the pathname of a directory on the host suitable
        for temporary file storage.

        The directory and its content will be deleted automatically
        on the destruction of the Host object that was used to obtain
        it.
        """
        self.run("mkdir -p %s" % parent)
        template = os.path.join(parent, 'autoserv-XXXXXX')
        dir_name = self.run("mktemp -d %s" % template).stdout.rstrip()
        self.tmp_dirs.append(dir_name)
        return dir_name

    def get_platform_label(self):
        """
        Return the platform label, or None if platform label is not set.
        """

        if self.job:
            keyval_path = os.path.join(self.job.resultdir, 'host_keyvals',
                                       self.hostname)
            keyvals = utils.read_keyval(keyval_path)
            return keyvals.get('platform', None)
        else:
            return None

    def get_all_labels(self):
        """
        Return all labels, or empty list if label is not set.
        """
        if self.job:
            keyval_path = os.path.join(self.job.resultdir, 'host_keyvals',
                                       self.hostname)
            keyvals = utils.read_keyval(keyval_path)
            all_labels = keyvals.get('labels', '')
            if all_labels:
                all_labels = all_labels.split(',')
                return [urllib.unquote(label) for label in all_labels]
        return []

    def delete_tmp_dir(self, tmpdir):
        """
        Delete the given temporary directory on the remote machine.
        """
        self.run('rm -rf "%s"' % utils.sh_escape(tmpdir), ignore_status=True)
        self.tmp_dirs.remove(tmpdir)

    def check_uptime(self):
        """
        Check that uptime is available and monotonically increasing.
        """
        if not self.is_up():
            raise error.AutoservHostError('Client does not appear to be up')
        result = self.run("/bin/cat /proc/uptime", 30)
        return result.stdout.strip().split()[0]

    def are_wait_up_processes_up(self):
        """
        Checks if any HOSTS waitup processes are running yet on the
        remote host.

        Returns True if any the waitup processes are running, False
        otherwise.
        """
        processes = self.get_wait_up_processes()
        if len(processes) == 0:
            return True  # wait up processes aren't being used
        for procname in processes:
            exit_status = self.run("{ ps -e || ps; } | grep '%s'" % procname,
                                   ignore_status=True).exit_status
            if exit_status == 0:
                return True
        return False
