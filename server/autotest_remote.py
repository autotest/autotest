# Copyright 2007 Google Inc. Released under the GPL v2

import glob
import logging
import os
import re
import sys
import tempfile
import time
import traceback

from autotest.client import os_dep
from autotest.client import utils as client_utils
from autotest.client.shared import base_job, error, autotemp
from autotest.client.shared import packages
from autotest.client.shared.settings import settings, SettingsError
from autotest.server import installable_object, prebuild, utils

autoserv_prebuild = settings.get_value('AUTOSERV', 'enable_server_prebuild',
                                       type=bool, default=False)

CLIENT_BINARY = 'autotest-local-streamhandler'


class AutodirNotFoundError(Exception):

    """No Autotest installation could be found."""


# Paths you'll find when autotest is installed via distro package
SYSTEM_WIDE_PATHS = ['/usr/bin/autotest-local',
                     '/usr/bin/autotest-local-streamhandler',
                     '/usr/bin/autotest-daemon',
                     '/usr/bin/autotest-daemon-monitor']


def _server_system_wide_install():
    for path in SYSTEM_WIDE_PATHS:
        try:
            os_dep.command(path)
        except ValueError:
            return False
    return True


def _client_system_wide_install(host):
    for path in SYSTEM_WIDE_PATHS:
        try:
            host.run('test -x %s' % utils.sh_escape(path))
        except:
            return False
    return True

# For now, the only fully developed distro package is in Fedora/RHEL
_yum_install_cmd = 'yum -y install autotest-framework'
_yum_uninstall_cmd = 'yum -y remove autotest-framework'
INSTALL_CLIENT_CMD_MAPPING = {'Fedora': _yum_install_cmd,
                              'RHEL': _yum_install_cmd}
UNINSTALL_CLIENT_CMD_MAPPING = {'Fedora': _yum_uninstall_cmd,
                                'RHEL': _yum_uninstall_cmd}


class BaseAutotest(installable_object.InstallableObject):

    """
    This class represents the Autotest program.

    Autotest is used to run tests automatically and collect the results.
    It also supports profilers.

    Implementation details:
    This is a leaf class in an abstract class hierarchy, it must
    implement the unimplemented methods in parent classes.
    """

    def __init__(self, host=None):
        self.host = host
        self.got = False
        self.installed = False
        self.serverdir = utils.get_server_dir()
        self.os_vendor = client_utils.get_os_vendor()
        self.server_system_wide_install = _server_system_wide_install()
        super(BaseAutotest, self).__init__()

    install_in_tmpdir = False

    @classmethod
    def set_install_in_tmpdir(cls, flag):
        """
        Sets a flag that controls whether or not Autotest should by
        default be installed in a "standard" directory (e.g. /home/autotest) or
        a temporary directory.
        """
        cls.install_in_tmpdir = flag

    @classmethod
    def get_client_autodir_paths(cls, host):
        return settings.get_value('AUTOSERV', 'client_autodir_paths', type=list)

    @classmethod
    def get_installed_autodir(cls, host):
        """
        Find where the Autotest client is installed on the host.
        :return: an absolute path to an installed Autotest client root.
        :raise AutodirNotFoundError if no Autotest installation can be found.
        """
        autodir = host.get_autodir()
        if autodir:
            logging.debug('Using existing host autodir: %s', autodir)
            return autodir

        if not _server_system_wide_install():
            for path in Autotest.get_client_autodir_paths(host):
                try:
                    autotest_binary = os.path.join(path, CLIENT_BINARY)
                    host.run('test -x %s' % utils.sh_escape(autotest_binary))
                    host.run('test -w %s' % utils.sh_escape(path))
                    logging.debug('Found existing autodir at %s', path)
                    return path
                except error.AutoservRunError:
                    logging.debug('%s does not exist on %s', autotest_binary,
                                  host.hostname)
        else:
            for path in Autotest.get_client_autodir_paths(host):
                host.run('test -w %s' % utils.sh_escape(path))
                logging.debug('Found existing autodir at %s', path)
                host.autodir = path
                return path

        raise AutodirNotFoundError

    @classmethod
    def get_install_dir(cls, host):
        """
        Determines the location where autotest should be installed on
        host. If self.install_in_tmpdir is set, it will return a unique
        temporary directory that autotest can be installed in. Otherwise, looks
        for an existing installation to use; if none is found, looks for a
        usable directory in the global config client_autodir_paths.
        """
        try:
            install_dir = cls.get_installed_autodir(host)
        except AutodirNotFoundError:
            install_dir = cls._find_installable_dir(host)

        if cls.install_in_tmpdir:
            return host.get_tmp_dir(parent=install_dir)
        return install_dir

    @classmethod
    def _find_installable_dir(cls, host):
        client_autodir_paths = cls.get_client_autodir_paths(host)
        for path in client_autodir_paths:
            try:
                host.run('mkdir -p %s' % utils.sh_escape(path))
                host.run('test -w %s' % utils.sh_escape(path))
                return path
            except error.AutoservRunError:
                logging.debug('Failed to create %s', path)
        raise error.AutoservInstallError(
            'Unable to find a place to install Autotest; tried %s' %
            ', '.join(client_autodir_paths))

    def _create_test_output_dir(self, host, autodir):
        tmpdir = os.path.join(autodir, 'tmp')
        state_autodir = settings.get_value('COMMON', 'test_output_dir',
                                           default=tmpdir)
        host.run('mkdir -p %s' % utils.sh_escape(state_autodir))

    def get_fetch_location(self):
        repos = settings.get_value("PACKAGES", 'fetch_location', type=list,
                                   default=[])
        repos.reverse()
        return repos

    def install(self, host=None, autodir=None):
        self._install(host=host, autodir=autodir)

    def install_full_client(self, host=None, autodir=None):
        self._install(host=host, autodir=autodir, use_autoserv=False,
                      use_packaging=False)

    def install_no_autoserv(self, host=None, autodir=None):
        self._install(host=host, autodir=autodir, use_autoserv=False)

    def _install_using_packaging(self, host, autodir):
        repos = self.get_fetch_location()
        if not repos:
            raise error.PackageInstallError("No repos to install an "
                                            "autotest client from")
        pkgmgr = packages.PackageManager(autodir, hostname=host.hostname,
                                         repo_urls=repos,
                                         do_locking=False,
                                         run_function=host.run,
                                         run_function_dargs=dict(timeout=600))
        # The packages dir is used to store all the packages that
        # are fetched on that client. (for the tests,deps etc.
        # too apart from the client)
        pkg_dir = os.path.join(autodir, 'packages')
        # clean up the autodir except for the packages directory
        host.run('cd %s && ls | grep -v "^packages$"'
                 ' | xargs rm -rf && rm -rf .[^.]*' % autodir)
        pkgmgr.install_pkg('autotest', 'client', pkg_dir, autodir,
                           preserve_install_dir=True)
        self._create_test_output_dir(host, autodir)
        logging.info("Installation of autotest completed")
        self.installed = True

    def _install_using_send_file(self, host, autodir):
        dirs_to_exclude = set(["tests", "site_tests", "deps", "profilers"])
        light_files = [os.path.join(self.source_material, f)
                       for f in os.listdir(self.source_material)
                       if f not in dirs_to_exclude]

        # there should be one and only one grubby tarball
        grubby_glob = os.path.join(self.source_material,
                                   "deps/grubby/grubby-*.tar.bz2")
        grubby_tarball_paths = glob.glob(grubby_glob)
        if grubby_tarball_paths:
            grubby_tarball_path = grubby_tarball_paths[0]
            if os.path.exists(grubby_tarball_path):
                light_files.append(grubby_tarball_path)

        host.send_file(light_files, autodir, delete_dest=True)

        profilers_autodir = os.path.join(autodir, 'profilers')
        profilers_init = os.path.join(self.source_material, 'profilers',
                                      '__init__.py')
        host.run("mkdir -p %s" % profilers_autodir)
        host.send_file(profilers_init, profilers_autodir, delete_dest=True)
        dirs_to_exclude.discard("profilers")

        # create empty dirs for all the stuff we excluded
        commands = []
        for path in dirs_to_exclude:
            abs_path = os.path.join(autodir, path)
            abs_path = utils.sh_escape(abs_path)
            commands.append("mkdir -p '%s'" % abs_path)
            commands.append("touch '%s'/__init__.py" % abs_path)
        host.run(';'.join(commands))

    def _install(self, host=None, autodir=None, use_autoserv=True,
                 use_packaging=True):
        """
        Install autotest.

        :param host A Host instance on which autotest will be installed
        :param autodir Location on the remote host to install to
        :param use_autoserv Enable install modes that depend on the client
            running with the autoserv harness
        :param use_packaging Enable install modes that use the packaging system

        @exception AutoservError If it wasn't possible to install the client
                after trying all available methods
        """
        if not host:
            host = self.host
        if not self.got:
            self.get()
        host.wait_up(timeout=30)
        host.setup()
        logging.info("Installing autotest on %s", host.hostname)

        if self.server_system_wide_install:
            msg_install = ("Autotest seems to be installed in the "
                           "client on a system wide location, proceeding...")

            logging.info("Verifying client package install")
            if _client_system_wide_install(host):
                logging.info(msg_install)
                self.installed = True
                return

            install_cmd = INSTALL_CLIENT_CMD_MAPPING.get(self.os_vendor, None)
            if install_cmd is not None:
                logging.info(msg_install)
                host.run(install_cmd)
                if _client_system_wide_install(host):
                    logging.info("Autotest seems to be installed in the "
                                 "client on a system wide location, proceeding...")
                    self.installed = True
                    return

            raise error.AutoservError("The autotest client package "
                                      "does not seem to be installed "
                                      "on %s" % host.hostname)

        # set up the autotest directory on the remote machine
        if not autodir:
            autodir = self.get_install_dir(host)
        logging.info('Using installation dir %s', autodir)
        host.set_autodir(autodir)
        host.run('mkdir -p %s' % utils.sh_escape(autodir))

        # make sure there are no files in $AUTODIR/results
        results_path = os.path.join(autodir, 'results')
        host.run('rm -rf %s/*' % utils.sh_escape(results_path),
                 ignore_status=True)

        # Fetch the autotest client from the nearest repository
        if use_packaging:
            try:
                self._install_using_packaging(host, autodir)
                self._create_test_output_dir(host, autodir)
                logging.info("Installation of autotest completed")
                self.installed = True
                return
            except (error.PackageInstallError, error.AutoservRunError,
                    SettingsError), e:
                logging.info("Could not install autotest using the packaging "
                             "system: %s. Trying other methods", e)

        # try to install from file or directory
        if self.source_material:
            supports_autoserv_packaging = settings.get_value("PACKAGES",
                                                             "serve_packages_from_autoserv",
                                                             type=bool)
            # Copy autotest recursively
            if supports_autoserv_packaging and use_autoserv:
                self._install_using_send_file(host, autodir)
            else:
                host.send_file(self.source_material, autodir, delete_dest=True)
            self._create_test_output_dir(host, autodir)
            logging.info("Installation of autotest completed")
            self.installed = True
            return

        raise error.AutoservError('Could not install autotest on '
                                  'target machine: %s' % host.name)

    def uninstall(self, host=None):
        """
        Uninstall (i.e. delete) autotest. Removes the autotest client install
        from the specified host.

        :params host a Host instance from which the client will be removed
        """
        if not self.installed:
            return
        if self.server_system_wide_install:
            uninstall_cmd = UNINSTALL_CLIENT_CMD_MAPPING.get(self.os_vendor,
                                                             None)
            if uninstall_cmd is not None:
                logging.info("Trying to uninstall autotest using distro "
                             "provided package manager")
                host.run(uninstall_cmd)
            return
        if not host:
            host = self.host
        autodir = host.get_autodir()
        if not autodir:
            return

        # perform the actual uninstall
        host.run("rm -rf %s" % utils.sh_escape(autodir), ignore_status=True)
        host.set_autodir(None)
        self.installed = False

    def get(self, location=None):
        if not location:
            location = os.path.join(self.serverdir, '../client')
            location = os.path.abspath(location)
        if not self.server_system_wide_install:
            # If there's stuff run on our client directory already, it
            # can cause problems. Try giving it a quick clean first.
            cwd = os.getcwd()
            os.chdir(location)
            try:
                utils.system('tools/make_clean', ignore_status=True)
            finally:
                os.chdir(cwd)
        super(BaseAutotest, self).get(location)
        self.got = True

    def run(self, control_file, results_dir='.', host=None, timeout=None,
            tag=None, parallel_flag=False, background=False,
            client_disconnect_timeout=None):
        """
        Run an autotest job on the remote machine.

        :param control_file: An open file-like-obj of the control file.
        :param results_dir: A str path where the results should be stored
                on the local filesystem.
        :param host: A Host instance on which the control file should
                be run.
        :param timeout: Maximum number of seconds to wait for the run or None.
        :param tag: Tag name for the client side instance of autotest.
        :param parallel_flag: Flag set when multiple jobs are run at the
                same time.
        :param background: Indicates that the client should be launched as
                a background job; the code calling run will be responsible
                for monitoring the client and collecting the results.
        :param client_disconnect_timeout: Seconds to wait for the remote host
                to come back after a reboot. Defaults to the host setting for
                DEFAULT_REBOOT_TIMEOUT.

        :raise AutotestRunError: If there is a problem executing
                the control file.
        """
        host = self._get_host_and_setup(host)
        results_dir = os.path.abspath(results_dir)

        if client_disconnect_timeout is None:
            client_disconnect_timeout = host.DEFAULT_REBOOT_TIMEOUT

        if tag:
            results_dir = os.path.join(results_dir, tag)

        atrun = _Run(host, results_dir, tag, parallel_flag, background)
        self._do_run(control_file, results_dir, host, atrun, timeout,
                     client_disconnect_timeout)

    def _get_host_and_setup(self, host):
        if not host:
            host = self.host
        if not self.installed:
            self.install(host)

        host.wait_up(timeout=30)
        return host

    def _do_run(self, control_file, results_dir, host, atrun, timeout,
                client_disconnect_timeout):
        try:
            atrun.verify_machine()
        except:
            logging.error("Verify failed on %s. Reinstalling autotest",
                          host.hostname)
            self.install(host)
        atrun.verify_machine()
        debug = os.path.join(results_dir, 'debug')
        try:
            os.makedirs(debug)
        except Exception:
            pass

        delete_file_list = [atrun.remote_control_file,
                            atrun.remote_control_state,
                            atrun.manual_control_file,
                            atrun.manual_control_state]
        cmd = ';'.join('rm -f ' + control for control in delete_file_list)
        host.run(cmd, ignore_status=True)

        tmppath = utils.get(control_file)

        # build up the initialization prologue for the control file
        prologue_lines = []

        # Add the additional user arguments
        prologue_lines.append("args = %r\n" % self.job.args)

        # If the packaging system is being used, add the repository list.
        repos = None
        try:
            repos = self.get_fetch_location()
            pkgmgr = packages.PackageManager('autotest', hostname=host.hostname,
                                             repo_urls=repos)
            prologue_lines.append('job.add_repository(%s)\n' % repos)
        except SettingsError, e:
            # If repos is defined packaging is enabled so log the error
            if repos:
                logging.error(e)

        # on full-size installs, turn on any profilers the server is using
        if not atrun.background:
            running_profilers = host.job.profilers.add_log.iteritems()
            for profiler, (args, dargs) in running_profilers:
                call_args = [repr(profiler)]
                call_args += [repr(arg) for arg in args]
                call_args += ["%s=%r" % item for item in dargs.iteritems()]
                prologue_lines.append("job.profilers.add(%s)\n"
                                      % ", ".join(call_args))
        cfile = "".join(prologue_lines)

        cfile += open(tmppath).read()
        open(tmppath, "w").write(cfile)

        # Create and copy state file to remote_control_file + '.state'
        state_file = host.job.preprocess_client_state()
        host.send_file(state_file, atrun.remote_control_init_state)
        os.remove(state_file)

        # Copy control_file to remote_control_file on the host
        host.send_file(tmppath, atrun.remote_control_file)
        if os.path.abspath(tmppath) != os.path.abspath(control_file):
            os.remove(tmppath)

        atrun.execute_control(
            timeout=timeout,
            client_disconnect_timeout=client_disconnect_timeout)

    def run_timed_test(self, test_name, results_dir='.', host=None,
                       timeout=None, *args, **dargs):
        """
        Assemble a tiny little control file to just run one test,
        and run it as an autotest client-side test
        """
        if not host:
            host = self.host
        if not self.installed:
            self.install(host)
        opts = ["%s=%s" % (o[0], repr(o[1])) for o in dargs.items()]
        cmd = ", ".join([repr(test_name)] + map(repr, args) + opts)
        control = "job.run_test(%s)\n" % cmd
        self.run(control, results_dir, host, timeout=timeout)

    def run_test(self, test_name, results_dir='.', host=None, *args, **dargs):
        self.run_timed_test(test_name, results_dir, host, timeout=None,
                            *args, **dargs)


class _BaseRun(object):

    """
    Represents a run of autotest control file.  This class maintains
    all the state necessary as an autotest control file is executed.

    It is not intended to be used directly, rather control files
    should be run using the run method in Autotest.
    """

    def __init__(self, host, results_dir, tag, parallel_flag, background):
        self.host = host
        self.results_dir = results_dir
        self.env = host.env
        self.tag = tag
        self.parallel_flag = parallel_flag
        self.background = background
        self.server_system_wide_install = _server_system_wide_install()

        self.autodir = Autotest.get_installed_autodir(self.host)

        tmpdir = os.path.join(self.autodir, 'tmp')
        state_dir = settings.get_value('COMMON', 'test_output_dir',
                                       default=tmpdir)

        if self.server_system_wide_install:
            control = os.path.join(state_dir, 'control')
        else:
            control = os.path.join(self.autodir, 'control')

        if tag:
            control += '.' + tag

        self.manual_control_file = control
        self.manual_control_init_state = os.path.join(state_dir,
                                                      os.path.basename(control) + ".init.state")
        self.manual_control_state = os.path.join(state_dir,
                                                 os.path.basename(control) + ".state")

        self.remote_control_file = control + '.autoserv'
        self.remote_control_init_state = os.path.join(state_dir,
                                                      os.path.basename(control) + ".autoserv.init.state")
        self.remote_control_state = os.path.join(state_dir,
                                                 os.path.basename(control) + ".autoserv.state")
        logging.debug("Remote control file: %s", self.remote_control_file)
        logging.debug("Remote control init state: %s", self.remote_control_init_state)
        logging.debug("Remote control state: %s", self.remote_control_state)

        self.config_file = os.path.join(self.autodir, 'global_config.ini')

    def _verify_machine_system_wide(self):
        if not _client_system_wide_install(self.host):
            raise error.AutoservInstallError("Autotest does not appear "
                                             "to be installed")

    def _verify_machine_local(self):
        binary = os.path.join(self.autodir, CLIENT_BINARY)
        try:
            self.host.run('test -x %s' % binary)
        except:
            raise error.AutoservInstallError("Autotest does not appear "
                                             "to be installed")

    def verify_machine(self):
        if self.server_system_wide_install:
            self._verify_machine_system_wide()
        else:
            self._verify_machine_local()
        if not self.parallel_flag:
            tmpdir = os.path.join(self.autodir, 'tmp')
            download = os.path.join(self.autodir, 'tests/download')
            self.host.run('umount %s' % tmpdir, ignore_status=True)
            self.host.run('umount %s' % download, ignore_status=True)

    def get_base_cmd_args(self, section):
        args = ['--verbose']
        if section > 0:
            args.append('-c')
        if self.tag:
            args.append('-t %s' % self.tag)
        if self.host.job.use_external_logging():
            args.append('-l')
        if self.host.hostname:
            args.append('--hostname=%s' % self.host.hostname)
        args.append('--user=%s' % self.host.job.user)

        args.append(self.remote_control_file)
        return args

    def get_background_cmd(self, section):
        system_wide_client_path = '/usr/bin/autotest-local-streamhandler'
        if self.server_system_wide_install:
            cmd = ['nohup', system_wide_client_path]
        else:
            cmd = ['nohup', os.path.join(self.autodir,
                                         'autotest-local-streamhandler')]
        cmd += self.get_base_cmd_args(section)
        cmd += ['>/dev/null', '2>/dev/null', '&']
        return ' '.join(cmd)

    def get_daemon_cmd(self, section, monitor_dir):
        system_wide_client_path = '/usr/bin/autotest-daemon'
        if self.server_system_wide_install:
            cmd = ['nohup', system_wide_client_path,
                   monitor_dir, '-H autoserv']
        else:
            cmd = ['nohup', os.path.join(self.autodir, 'autotest-daemon'),
                   monitor_dir, '-H autoserv']

        cmd += self.get_base_cmd_args(section)
        cmd += ['>/dev/null', '2>/dev/null', '&']
        return ' '.join(cmd)

    def get_monitor_cmd(self, monitor_dir, stdout_read, stderr_read):
        system_wide_client_path = '/usr/bin/autotest-daemon-monitor'
        if self.server_system_wide_install:
            cmd = [system_wide_client_path,
                   monitor_dir, str(stdout_read), str(stderr_read)]
        else:
            cmd = [os.path.join(self.autodir, 'autotest-daemon-monitor'),
                   monitor_dir, str(stdout_read), str(stderr_read)]
        return ' '.join(cmd)

    def get_client_log(self):
        """Find what the "next" client.* prefix should be

        :return: A string of the form client.INTEGER that should be prefixed
            to all client debug log files.
        """
        max_digit = -1
        debug_dir = os.path.join(self.results_dir, 'debug')
        client_logs = glob.glob(os.path.join(debug_dir, 'client.*.*'))
        for log in client_logs:
            _, number, _ = log.split('.', 2)
            if number.isdigit():
                max_digit = max(max_digit, int(number))
        return 'client.%d' % (max_digit + 1)

    def copy_client_config_file(self, client_log_prefix=None):
        """
        Create and copy the client config file based on the server config.

        :param client_log_prefix: Optional prefix to prepend to log files.
        """
        if not self.server_system_wide_install:
            client_config_file = self._create_client_config_file(client_log_prefix)
            self.host.send_file(client_config_file, self.config_file)
            os.remove(client_config_file)
        else:
            logging.info("System wide install, not overriding client config")

    def _create_client_config_file(self, client_log_prefix=None):
        """
        Create a temporary file with the [CLIENT] and [COMMON] section
        configuration values taken from the server global_config.ini.

        :param client_log_prefix: Optional prefix to prepend to log files.

        :return: Path of the temporary file generated.
        """
        config = settings.get_section_values(('CLIENT', 'COMMON'))
        if client_log_prefix:
            config.set('CLIENT', 'default_logging_name', client_log_prefix)
        return self._create_aux_file(config.write)

    def _create_aux_file(self, func, *args):
        """
        Creates a temporary file and writes content to it according to a
        content creation function. The file object is appended to *args, which
        is then passed to the content creation function

        :param func: Function that will be used to write content to the
                temporary file.
        :param *args: List of parameters that func takes.
        :return: Path to the temporary file that was created.
        """
        fd, path = tempfile.mkstemp(dir=self.host.job.tmpdir)
        aux_file = os.fdopen(fd, "w")
        try:
            list_args = list(args)
            list_args.append(aux_file)
            func(*list_args)
        finally:
            aux_file.close()
        return path

    @staticmethod
    def is_client_job_finished(last_line):
        return bool(re.match(r'^END .*\t----\t----\t.*$', last_line))

    @staticmethod
    def is_client_job_rebooting(last_line):
        return bool(re.match(r'^\t*GOOD\t----\treboot\.start.*$', last_line))

    def log_unexpected_abort(self, stderr_redirector):
        stderr_redirector.flush_all_buffers()
        msg = "Autotest client terminated unexpectedly"
        self.host.job.record("END ABORT", None, None, msg)

    def _execute_in_background(self, section, timeout):
        full_cmd = self.get_background_cmd(section)
        devnull = open(os.devnull, "w")

        self.copy_client_config_file(self.get_client_log())

        self.host.job.push_execution_context(self.results_dir)
        try:
            result = self.host.run(full_cmd, ignore_status=True,
                                   timeout=timeout,
                                   stdout_tee=devnull,
                                   stderr_tee=devnull)
        finally:
            self.host.job.pop_execution_context()

        return result

    @staticmethod
    def _strip_stderr_prologue(stderr):
        """Strips the 'standard' prologue that get pre-pended to every
        remote command and returns the text that was actually written to
        stderr by the remote command."""
        stderr_lines = stderr.split("\n")[1:]
        if not stderr_lines:
            return ""
        elif stderr_lines[0].startswith("NOTE: autotest-daemon-monitor"):
            del stderr_lines[0]
        return "\n".join(stderr_lines)

    def _execute_daemon(self, section, timeout, stderr_redirector,
                        client_disconnect_timeout):
        monitor_dir = self.host.get_tmp_dir()
        daemon_cmd = self.get_daemon_cmd(section, monitor_dir)

        # grab the location for the server-side client log file
        client_log_prefix = self.get_client_log()
        client_log_path = os.path.join(self.results_dir, 'debug',
                                       client_log_prefix + '.log')
        client_log = open(client_log_path, 'w', 0)
        self.copy_client_config_file(client_log_prefix)

        stdout_read = stderr_read = 0
        self.host.job.push_execution_context(self.results_dir)
        try:
            self.host.run(daemon_cmd, ignore_status=True, timeout=timeout)
            disconnect_warnings = []
            while True:
                monitor_cmd = self.get_monitor_cmd(monitor_dir, stdout_read,
                                                   stderr_read)
                try:
                    result = self.host.run(monitor_cmd, ignore_status=True,
                                           timeout=timeout,
                                           stdout_tee=client_log,
                                           stderr_tee=stderr_redirector)
                except error.AutoservRunError, e:
                    result = e.result_obj
                    result.exit_status = None
                    disconnect_warnings.append(e.description)

                    stderr_redirector.log_warning(
                        "Autotest client was disconnected: %s" % e.description,
                        "NETWORK")
                except error.AutoservSSHTimeout:
                    result = utils.CmdResult(monitor_cmd, "", "", None, 0)
                    stderr_redirector.log_warning(
                        "Attempt to connect to Autotest client timed out",
                        "NETWORK")

                stdout_read += len(result.stdout)
                stderr_read += len(self._strip_stderr_prologue(result.stderr))

                if result.exit_status is not None:
                    return result
                elif not self.host.wait_up(client_disconnect_timeout):
                    raise error.AutoservSSHTimeout(
                        "client was disconnected, reconnect timed out")
        finally:
            client_log.close()
            self.host.job.pop_execution_context()

    def execute_section(self, section, timeout, stderr_redirector,
                        client_disconnect_timeout):
        if self.server_system_wide_install:
            autotest_local_bin = "/usr/bin/autotest-local"
        else:
            autotest_local_bin = os.path.join(self.autodir, "autotest")

        logging.info("Executing %s %s phase %d",
                     autotest_local_bin, self.remote_control_file, section)

        if self.background:
            result = self._execute_in_background(section, timeout)
        else:
            result = self._execute_daemon(section, timeout, stderr_redirector,
                                          client_disconnect_timeout)

        last_line = stderr_redirector.last_line

        # check if we failed hard enough to warrant an exception
        if result.exit_status == 1:
            err = error.AutotestRunError("client job was aborted")
        elif not self.background and not result.stderr:
            err = error.AutotestRunError(
                "execute_section %s failed to return anything\n"
                "stdout:%s\n" % (section, result.stdout))
        else:
            err = None

        # log something if the client failed AND never finished logging
        if err and not self.is_client_job_finished(last_line):
            self.log_unexpected_abort(stderr_redirector)

        if err:
            raise err
        else:
            return stderr_redirector.last_line

    def _wait_for_reboot(self, old_boot_id):
        logging.info("Client is rebooting")
        logging.info("Waiting for client to halt")
        if not self.host.wait_down(self.host.WAIT_DOWN_REBOOT_TIMEOUT,
                                   old_boot_id=old_boot_id):
            err = "%s failed to shutdown after %d"
            err %= (self.host.hostname, self.host.WAIT_DOWN_REBOOT_TIMEOUT)
            raise error.AutotestRunError(err)
        logging.info("Client down, waiting for restart")
        if not self.host.wait_up(self.host.DEFAULT_REBOOT_TIMEOUT):
            # since reboot failed
            # hardreset the machine once if possible
            # before failing this control file
            warning = "%s did not come back up, hard resetting"
            warning %= self.host.hostname
            logging.warning(warning)
            try:
                self.host.hardreset(wait=False)
            except (AttributeError, error.AutoservUnsupportedError), detail:
                warning = ("Hard reset unsupported on %s: %s" %
                           (self.hostname, detail))
                logging.warning(warning)
            raise error.AutotestRunError("%s failed to boot after %ds" %
                                         (self.host.hostname,
                                          self.host.DEFAULT_REBOOT_TIMEOUT))
        self.host.reboot_followup()

    def execute_control(self, timeout=None, client_disconnect_timeout=None):
        if not self.background:
            collector = log_collector(self.host, self.tag, self.results_dir)
            hostname = self.host.hostname
            remote_results = collector.client_results_dir
            local_results = collector.server_results_dir
            self.host.job.add_client_log(hostname, remote_results,
                                         local_results)
            job_record_context = self.host.job.get_record_context()

        section = 0
        start_time = time.time()

        logger = client_logger(self.host, self.tag, self.results_dir)
        try:
            while not timeout or time.time() < start_time + timeout:
                if timeout:
                    section_timeout = start_time + timeout - time.time()
                else:
                    section_timeout = None
                boot_id = self.host.get_boot_id()
                last = self.execute_section(section, section_timeout,
                                            logger, client_disconnect_timeout)
                if self.background:
                    return
                section += 1
                if self.is_client_job_finished(last):
                    logging.info("Client complete")
                    return
                elif self.is_client_job_rebooting(last):
                    try:
                        self._wait_for_reboot(boot_id)
                    except error.AutotestRunError, e:
                        self.host.job.record("ABORT", None, "reboot", str(e))
                        self.host.job.record("END ABORT", None, None, str(e))
                        raise
                    continue

                # if we reach here, something unexpected happened
                self.log_unexpected_abort(logger)

                # give the client machine a chance to recover from a crash
                self.host.wait_up(self.host.HOURS_TO_WAIT_FOR_RECOVERY * 3600)
                msg = ("Aborting - unexpected final status message from "
                       "client on %s: %s\n") % (self.host.hostname, last)
                raise error.AutotestRunError(msg)
        finally:
            logger.close()
            if not self.background:
                collector.collect_client_job_results()
                collector.remove_redundant_client_logs()
                state_file = os.path.basename(self.remote_control_state)
                state_path = os.path.join(self.results_dir, state_file)
                self.host.job.postprocess_client_state(state_path)
                self.host.job.remove_client_log(hostname, remote_results,
                                                local_results)
                job_record_context.restore()

        # should only get here if we timed out
        assert timeout
        raise error.AutotestTimeoutError()


class log_collector(object):

    def __init__(self, host, client_tag, results_dir):
        self.host = host
        if not client_tag:
            client_tag = "default"
        if _server_system_wide_install():
            output_dir = settings.get_value("CLIENT", "output_dir")
        else:
            output_dir = host.get_autodir()

        self.client_results_dir = os.path.join(output_dir,
                                               "results", client_tag)

        self.server_results_dir = results_dir
        logging.debug("Log collector initialized")
        logging.debug("Client results dir: %s", self.client_results_dir)
        logging.debug("Server results dir: %s", self.server_results_dir)

    def collect_client_job_results(self):
        """ A method that collects all the current results of a running
        client job into the results dir. By default does nothing as no
        client job is running, but when running a client job you can override
        this with something that will actually do something. """

        # make an effort to wait for the machine to come up
        try:
            self.host.wait_up(timeout=30)
        except error.AutoservError:
            # don't worry about any errors, we'll try and
            # get the results anyway
            pass

        # Copy all dirs in default to results_dir
        try:
            self.host.get_file(self.client_results_dir + "/",
                               self.server_results_dir, preserve_symlinks=True)
        except Exception:
            # well, don't stop running just because we couldn't get logs
            e_msg = "Unexpected error copying test result logs, continuing ..."
            logging.error(e_msg)
            traceback.print_exc(file=sys.stdout)

    def remove_redundant_client_logs(self):
        """Remove client.*.log files in favour of client.*.DEBUG files."""
        debug_dir = os.path.join(self.server_results_dir, 'debug')
        debug_files = [f for f in os.listdir(debug_dir)
                       if re.search(r'^client\.\d+\.DEBUG$', f)]
        for debug_file in debug_files:
            log_file = debug_file.replace('DEBUG', 'log')
            log_file = os.path.join(debug_dir, log_file)
            if os.path.exists(log_file):
                os.remove(log_file)


# a file-like object for catching stderr from an autotest client and
# extracting status logs from it
class client_logger(object):

    """Partial file object to write to both stdout and
    the status log file.  We only implement those methods
    utils.run() actually calls.
    """
    status_parser = re.compile(r"^AUTOTEST_STATUS:([^:]*):(.*)$")
    test_complete_parser = re.compile(r"^AUTOTEST_TEST_COMPLETE:(.*)$")
    fetch_package_parser = re.compile(
        r"^AUTOTEST_FETCH_PACKAGE:([^:]*):([^:]*):(.*)$")
    extract_indent = re.compile(r"^(\t*).*$")
    extract_timestamp = re.compile(r".*\ttimestamp=(\d+)\t.*$")

    def __init__(self, host, tag, server_results_dir):
        self.host = host
        self.job = host.job
        self.log_collector = log_collector(host, tag, server_results_dir)
        self.leftover = ""
        self.last_line = ""
        self.logs = {}

    def _process_log_dict(self, log_dict):
        log_list = log_dict.pop("logs", [])
        for key in sorted(log_dict.iterkeys()):
            log_list += self._process_log_dict(log_dict.pop(key))
        return log_list

    def _process_logs(self):
        """Go through the accumulated logs in self.log and print them
        out to stdout and the status log. Note that this processes
        logs in an ordering where:

        1) logs to different tags are never interleaved
        2) logs to x.y come before logs to x.y.z for all z
        3) logs to x.y come before x.z whenever y < z

        Note that this will in general not be the same as the
        chronological ordering of the logs. However, if a chronological
        ordering is desired that one can be reconstructed from the
        status log by looking at timestamp lines."""
        log_list = self._process_log_dict(self.logs)
        for entry in log_list:
            self.job.record_entry(entry, log_in_subdir=False)
        if log_list:
            self.last_line = log_list[-1].render()

    def _process_quoted_line(self, tag, line):
        """Process a line quoted with an AUTOTEST_STATUS flag. If the
        tag is blank then we want to push out all the data we've been
        building up in self.logs, and then the newest line. If the
        tag is not blank, then push the line into the logs for handling
        later."""
        entry = base_job.status_log_entry.parse(line)
        if entry is None:
            return  # the line contains no status lines
        if tag == "":
            self._process_logs()
            self.job.record_entry(entry, log_in_subdir=False)
            self.last_line = line
        else:
            tag_parts = [int(x) for x in tag.split(".")]
            log_dict = self.logs
            for part in tag_parts:
                log_dict = log_dict.setdefault(part, {})
            log_list = log_dict.setdefault("logs", [])
            log_list.append(entry)

    def _process_info_line(self, line):
        """Check if line is an INFO line, and if it is, interpret any control
        messages (e.g. enabling/disabling warnings) that it may contain."""
        match = re.search(r"^\t*INFO\t----\t----(.*)\t[^\t]*$", line)
        if not match:
            return   # not an INFO line
        for field in match.group(1).split('\t'):
            if field.startswith("warnings.enable="):
                func = self.job.warning_manager.enable_warnings
            elif field.startswith("warnings.disable="):
                func = self.job.warning_manager.disable_warnings
            else:
                continue
            warning_type = field.split("=", 1)[1]
            func(warning_type)

    def _process_line(self, line):
        """Write out a line of data to the appropriate stream. Status
        lines sent by autotest will be prepended with
        "AUTOTEST_STATUS", and all other lines are ssh error
        messages."""
        status_match = self.status_parser.search(line)
        test_complete_match = self.test_complete_parser.search(line)
        fetch_package_match = self.fetch_package_parser.search(line)
        if status_match:
            tag, line = status_match.groups()
            self._process_info_line(line)
            self._process_quoted_line(tag, line)
        elif test_complete_match:
            self._process_logs()
            fifo_path, = test_complete_match.groups()
            try:
                self.log_collector.collect_client_job_results()
                self.host.run("echo A > %s" % fifo_path)
            except Exception:
                msg = "Post-test log collection failed, continuing anyway"
                logging.exception(msg)
        elif fetch_package_match:
            pkg_name, dest_path, fifo_path = fetch_package_match.groups()
            serve_packages = settings.get_value("PACKAGES",
                                                "serve_packages_from_autoserv",
                                                type=bool)
            if serve_packages and pkg_name.endswith(".tar.bz2"):
                try:
                    self._send_tarball(pkg_name, dest_path)
                except Exception:
                    msg = "Package tarball creation failed, continuing anyway"
                    logging.exception(msg)
            try:
                self.host.run("echo B > %s" % fifo_path)
            except Exception:
                msg = "Package tarball installation failed, continuing anyway"
                logging.exception(msg)
        else:
            logging.info(line)

    def _send_tarball(self, pkg_name, remote_dest):
        name, pkg_type = self.job.pkgmgr.parse_tarball_name(pkg_name)
        src_dirs = []
        if pkg_type == 'test':
            test_dirs = ['site_tests', 'tests']
            # if test_dir is defined in global config
            # package the tests from there (if exists)
            settings_test_dirs = settings.get_value('COMMON', 'test_dir',
                                                    default="")
            if settings_test_dirs:
                test_dirs = settings_test_dirs.strip().split(',') + test_dirs
            for test_dir in test_dirs:
                src_dir = os.path.join(self.job.clientdir, test_dir, name)
                if os.path.exists(src_dir):
                    src_dirs += [src_dir]
                    if autoserv_prebuild:
                        prebuild.setup(self.job.clientdir, src_dir)
                    break
        elif pkg_type == 'profiler':
            src_dirs += [os.path.join(self.job.clientdir, 'profilers', name)]
            if autoserv_prebuild:
                prebuild.setup(self.job.clientdir, src_dir)
        elif pkg_type == 'dep':
            src_dirs += [os.path.join(self.job.clientdir, 'deps', name)]
        elif pkg_type == 'client':
            return  # you must already have a client to hit this anyway
        else:
            return  # no other types are supported

        # iterate over src_dirs until we find one that exists, then tar it
        for src_dir in src_dirs:
            if os.path.exists(src_dir):
                try:
                    logging.info('Bundling %s into %s', src_dir, pkg_name)
                    temp_dir = autotemp.tempdir(unique_id='autoserv-packager',
                                                dir=self.job.tmpdir)

                    exclude_paths = None
                    exclude_file_path = os.path.join(src_dir, ".pack_exclude")
                    if os.path.exists(exclude_file_path):
                        exclude_file = open(exclude_file_path)
                        exclude_paths = exclude_file.read().splitlines()
                        exclude_file.close()

                    tarball_path = self.job.pkgmgr.tar_package(
                        pkg_name, src_dir, temp_dir.name,
                        " .", exclude_paths)
                    self.host.send_file(tarball_path, remote_dest)
                finally:
                    temp_dir.clean()
                return

    def log_warning(self, msg, warning_type):
        """Injects a WARN message into the current status logging stream."""
        timestamp = int(time.time())
        if self.job.warning_manager.is_valid(timestamp, warning_type):
            self.job.record('WARN', None, None, msg)

    def write(self, data):
        # now start processing the existing buffer and the new data
        data = self.leftover + data
        lines = data.split('\n')
        processed_lines = 0
        try:
            # process all the buffered data except the last line
            # ignore the last line since we may not have all of it yet
            for line in lines[:-1]:
                self._process_line(line)
                processed_lines += 1
        finally:
            # save any unprocessed lines for future processing
            self.leftover = '\n'.join(lines[processed_lines:])

    def flush(self):
        sys.stdout.flush()

    def flush_all_buffers(self):
        if self.leftover:
            self._process_line(self.leftover)
            self.leftover = ""
        self._process_logs()
        self.flush()

    def close(self):
        self.flush_all_buffers()


SiteAutotest = client_utils.import_site_class(
    __file__, "autotest.server.site_autotest", "SiteAutotest",
    BaseAutotest)


_SiteRun = client_utils.import_site_class(
    __file__, "autotest.server.site_autotest", "_SiteRun", _BaseRun)


class Autotest(SiteAutotest):
    pass


class _Run(_SiteRun):
    pass


class AutotestHostMixin(object):

    """A generic mixin to add a run_test method to classes, which will allow
    you to run an autotest client test on a machine directly."""

    # for testing purposes
    _Autotest = Autotest

    def run_test(self, test_name, **dargs):
        """Run an autotest client test on the host.

        :param test_name: The name of the client test.
        :param dargs: Keyword arguments to pass to the test.

        :return: True if the test passes, False otherwise."""
        at = self._Autotest()
        control_file = ('result = job.run_test(%s)\n'
                        'job.set_state("test_result", result)\n')
        test_args = [repr(test_name)]
        test_args += ['%s=%r' % (k, v) for k, v in dargs.iteritems()]
        control_file %= ', '.join(test_args)
        at.run(control_file, host=self)
        return at.job.get_state('test_result', default=False)
