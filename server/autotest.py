# Copyright 2007 Google Inc. Released under the GPL v2

import re, os, sys, traceback, subprocess, tempfile, time, pickle, glob, logging
from autotest_lib.server import installable_object, utils
from autotest_lib.client.common_lib import log, error
from autotest_lib.client.common_lib import global_config, packages
from autotest_lib.client.common_lib import utils as client_utils

AUTOTEST_SVN  = 'svn://test.kernel.org/autotest/trunk/client'
AUTOTEST_HTTP = 'http://test.kernel.org/svn/autotest/trunk/client'

# Timeouts for powering down and up respectively
HALT_TIME = 300
BOOT_TIME = 1800
CRASH_RECOVERY_TIME = 9000


class BaseAutotest(installable_object.InstallableObject):
    """
    This class represents the Autotest program.

    Autotest is used to run tests automatically and collect the results.
    It also supports profilers.

    Implementation details:
    This is a leaf class in an abstract class hierarchy, it must
    implement the unimplemented methods in parent classes.
    """

    def __init__(self, host = None):
        self.host = host
        self.got = False
        self.installed = False
        self.lightweight = False
        self.serverdir = utils.get_server_dir()
        super(BaseAutotest, self).__init__()


    install_in_tmpdir = False
    @classmethod
    def set_install_in_tmpdir(cls, flag):
        """ Sets a flag that controls whether or not Autotest should by
        default be installed in a "standard" directory (e.g.
        /home/autotest, /usr/local/autotest) or a temporary directory. """
        cls.install_in_tmpdir = flag


    def _get_install_dir(self, host):
        """ Determines the location where autotest should be installed on
        host. If self.install_in_tmpdir is set, it will return a unique
        temporary directory that autotest can be installed in. """
        try:
            autodir = _get_autodir(host)
        except error.AutotestRunError:
            autodir = '/usr/local/autotest'
        if self.install_in_tmpdir:
            autodir = host.get_tmp_dir(parent=autodir)
        return autodir


    @log.record
    def install(self, host=None, autodir=None):
        self._install(host=host, autodir=autodir)


    def install_base(self, host=None, autodir=None):
        """ Performs a lightweight autotest install. Useful for when you
        want to run some client-side code but don't want to pay the cost
        of a full installation. """
        self._install(host=host, autodir=autodir, lightweight=True)


    def _install(self, host=None, autodir=None, lightweight=False):
        """
        Install autotest.  If get() was not called previously, an
        attempt will be made to install from the autotest svn
        repository.

        Args:
            host: a Host instance on which autotest will be installed
            autodir: location on the remote host to install to
            lightweight: exclude tests, deps and profilers, if possible

        Raises:
            AutoservError: if a tarball was not specified and
                the target host does not have svn installed in its path"""
        if not host:
            host = self.host
        if not self.got:
            self.get()
        host.wait_up(timeout=30)
        host.setup()
        logging.info("Installing autotest on %s", host.hostname)

        # set up the autotest directory on the remote machine
        if not autodir:
            autodir = self._get_install_dir(host)
        host.set_autodir(autodir)
        host.run('mkdir -p %s' % utils.sh_escape(autodir))

        # make sure there are no files in $AUTODIR/results
        results_path = os.path.join(autodir, 'results')
        host.run('rm -rf %s/*' % utils.sh_escape(results_path),
                 ignore_status=True)

        # Fetch the autotest client from the nearest repository
        try:
            c = global_config.global_config
            repos = c.get_config_value("PACKAGES", 'fetch_location', type=list)
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
            self.installed = True
            self.lightweight = lightweight
            return
        except global_config.ConfigError, e:
            logging.error("Could not install autotest using the packaging"
                          "system: %s",  e)
        except (packages.PackageInstallError, error.AutoservRunError), e:
            logging.error("Could not install autotest from %s", repos)

        # try to install from file or directory
        if self.source_material:
            if os.path.isdir(self.source_material):
                # Copy autotest recursively
                if lightweight:
                    dirs_to_exclude = set(["tests", "site_tests", "deps",
                                           "tools", "profilers"])
                    light_files = [os.path.join(self.source_material, f)
                                   for f in os.listdir(self.source_material)
                                   if f not in dirs_to_exclude]
                    host.send_file(light_files, autodir, delete_dest=True)

                    # create empty dirs for all the stuff we excluded
                    commands = []
                    for path in dirs_to_exclude:
                        abs_path = os.path.join(autodir, path)
                        abs_path = utils.sh_escape(abs_path)
                        commands.append("mkdir -p '%s'" % abs_path)
                    host.run(';'.join(commands))
                else:
                    host.send_file(self.source_material, autodir,
                                   delete_dest=True)
            else:
                # Copy autotest via tarball
                e_msg = 'Installation method not yet implemented!'
                raise NotImplementedError(e_msg)
            logging.info("Installation of autotest completed")
            self.installed = True
            self.lightweight = lightweight
            return

        # if that fails try to install using svn
        if utils.run('which svn').exit_status:
            raise error.AutoservError('svn not found on target machine: %s'
                                                                   % host.name)
        try:
            host.run('svn checkout %s %s' % (AUTOTEST_SVN, autodir))
        except error.AutoservRunError, e:
            host.run('svn checkout %s %s' % (AUTOTEST_HTTP, autodir))
        logging.info("Installation of autotest completed")
        self.installed = True
        self.lightweight = lightweight


    def uninstall(self, host=None):
        """
        Uninstall (i.e. delete) autotest. Removes the autotest client install
        from the specified host.

        @params host a Host instance from which the client will be removed
        """
        if not self.installed:
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


    def get(self, location = None):
        if not location:
            location = os.path.join(self.serverdir, '../client')
            location = os.path.abspath(location)
        # If there's stuff run on our client directory already, it
        # can cause problems. Try giving it a quick clean first.
        cwd = os.getcwd()
        os.chdir(location)
        os.system('tools/make_clean')
        os.chdir(cwd)
        super(BaseAutotest, self).get(location)
        self.got = True


    def run(self, control_file, results_dir='.', host=None, timeout=None,
            tag=None, parallel_flag=False, background=False,
            client_disconnect_timeout=1800, job_tag=''):
        """
        Run an autotest job on the remote machine.

        @param control_file: An open file-like-obj of the control file.
        @param results_dir: A str path where the results should be stored
                on the local filesystem.
        @param host: A Host instance on which the control file should
                be run.
        @param timeout: Maximum number of seconds to wait for the run or None.
        @param tag: Tag name for the client side instance of autotest.
        @param parallel_flag: Flag set when multiple jobs are run at the
                same time.
        @param background: Indicates that the client should be launched as
                a background job; the code calling run will be responsible
                for monitoring the client and collecting the results.
        @param client_disconnect_timeout: Seconds to wait for the remote host
                to come back after a reboot.  [default: 30 minutes]
        @param job_tag: The scheduler's execution tag for this particular job
                to pass on to the clients.  'job#-owner/hostgroupname'

        @raises AutotestRunError: If there is a problem executing
                the control file.
        """
        host = self._get_host_and_setup(host)
        results_dir = os.path.abspath(results_dir)

        if tag:
            results_dir = os.path.join(results_dir, tag)

        atrun = _Run(host, results_dir, tag, parallel_flag, background)
        self._do_run(control_file, results_dir, host, atrun, timeout,
                     client_disconnect_timeout, job_tag)


    def _get_host_and_setup(self, host):
        if not host:
            host = self.host
        if not self.installed:
            self.install(host)

        host.wait_up(timeout=30)
        return host


    def _do_run(self, control_file, results_dir, host, atrun, timeout,
                client_disconnect_timeout, job_tag):
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
                            atrun.remote_control_file + '.state',
                            atrun.manual_control_file,
                            atrun.manual_control_file + '.state']
        cmd = ';'.join('rm -f ' + control for control in delete_file_list)
        host.run(cmd, ignore_status=True)

        tmppath = utils.get(control_file)

        # build up the initialization prologue for the control file
        prologue_lines = []
        prologue_lines.append("job.default_boot_tag(%r)\n"
                              % host.job.last_boot_tag)
        prologue_lines.append("job.default_test_cleanup(%r)\n"
                              % host.job.run_test_cleanup)
        if job_tag:
            prologue_lines.append("job.default_tag(%r)\n" % job_tag)

        # If the packaging system is being used, add the repository list.
        try:
            c = global_config.global_config
            repos = c.get_config_value("PACKAGES", 'fetch_location', type=list)
            pkgmgr = packages.PackageManager('autotest', hostname=host.hostname,
                                             repo_urls=repos)
            prologue_lines.append('job.add_repository(%s)\n'
                                  % pkgmgr.repo_urls)
        except global_config.ConfigError, e:
            pass

        # on full-size installs, turn on any profilers the server is using
        if not self.lightweight and not atrun.background:
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
        sysinfo_state = {"__sysinfo": host.job.sysinfo.serialize()}
        state_file = self._create_state_file(host.job, sysinfo_state)
        host.send_file(state_file, atrun.remote_control_file + '.state')
        os.remove(state_file)

        # Copy control_file to remote_control_file on the host
        host.send_file(tmppath, atrun.remote_control_file)
        if os.path.abspath(tmppath) != os.path.abspath(control_file):
            os.remove(tmppath)

        atrun.execute_control(
                timeout=timeout,
                client_disconnect_timeout=client_disconnect_timeout)


    def _create_state_file(self, job, state_dict):
        """ Create a state file from a dictionary. Returns the path of the
        state file. """
        fd, path = tempfile.mkstemp(dir=job.tmpdir)
        state_file = os.fdopen(fd, "w")
        pickle.dump(state_dict, state_file)
        state_file.close()
        return path


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


class _Run(object):
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
        self.autodir = _get_autodir(self.host)
        control = os.path.join(self.autodir, 'control')
        if tag:
            control += '.' + tag
        self.manual_control_file = control
        self.remote_control_file = control + '.autoserv'


    def verify_machine(self):
        binary = os.path.join(self.autodir, 'bin/autotest')
        try:
            self.host.run('ls %s > /dev/null 2>&1' % binary)
        except:
            raise "Autotest does not appear to be installed"

        if not self.parallel_flag:
            tmpdir = os.path.join(self.autodir, 'tmp')
            download = os.path.join(self.autodir, 'tests/download')
            self.host.run('umount %s' % tmpdir, ignore_status=True)
            self.host.run('umount %s' % download, ignore_status=True)


    def get_base_cmd_args(self, section):
        args = []
        if section > 0:
            args.append('-c')
        if self.tag:
            args.append('-t %s' % self.tag)
        if self.host.job.use_external_logging():
            args.append('-l')
        args.append(self.remote_control_file)
        return args


    def get_background_cmd(self, section):
        cmd = ['nohup', os.path.join(self.autodir, 'bin/autotest_client')]
        cmd += self.get_base_cmd_args(section)
        cmd.append('>/dev/null 2>/dev/null &')
        return ' '.join(cmd)


    def get_daemon_cmd(self, section, monitor_dir):
        cmd = ['nohup', os.path.join(self.autodir, 'bin/autotestd'),
               monitor_dir, '-H autoserv']
        cmd += self.get_base_cmd_args(section)
        cmd.append('>/dev/null 2>/dev/null </dev/null &')
        return ' '.join(cmd)


    def get_monitor_cmd(self, monitor_dir, stdout_read, stderr_read):
        cmd = [os.path.join(self.autodir, 'bin', 'autotestd_monitor'),
               monitor_dir, str(stdout_read), str(stderr_read)]
        return ' '.join(cmd)


    def get_client_log(self, section):
        """ Find what the "next" client.log.* file should be and open it. """
        debug_dir = os.path.join(self.results_dir, "debug")
        client_logs = glob.glob(os.path.join(debug_dir, "client.log.*"))
        next_log = os.path.join(debug_dir, "client.log.%d" % len(client_logs))
        return open(next_log, "w", 0)


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

        old_resultdir = self.host.job.resultdir
        try:
            self.host.job.resultdir = self.results_dir
            result = self.host.run(full_cmd, ignore_status=True,
                                   timeout=timeout,
                                   stdout_tee=devnull,
                                   stderr_tee=devnull)
        finally:
            self.host.job.resultdir = old_resultdir

        return result


    @staticmethod
    def _strip_stderr_prologue(stderr):
        """Strips the 'standard' prologue that get pre-pended to every
        remote command and returns the text that was actually written to
        stderr by the remote command."""
        stderr_lines = stderr.split("\n")[1:]
        if not stderr_lines:
            return ""
        elif stderr_lines[0].startswith("NOTE: autotestd_monitor"):
            del stderr_lines[0]
        return "\n".join(stderr_lines)


    def _execute_daemon(self, section, timeout, stderr_redirector,
                        client_disconnect_timeout):
        monitor_dir = self.host.get_tmp_dir()
        daemon_cmd = self.get_daemon_cmd(section, monitor_dir)
        client_log = self.get_client_log(section)

        stdout_read = stderr_read = 0
        old_resultdir = self.host.job.resultdir
        try:
            self.host.job.resultdir = self.results_dir
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
            self.host.job.resultdir = old_resultdir


    def execute_section(self, section, timeout, stderr_redirector,
                        client_disconnect_timeout):
        logging.info("Executing %s/bin/autotest %s/control phase %d",
                     self.autodir, self.autodir, section)

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


    def _wait_for_reboot(self):
        logging.info("Client is rebooting")
        logging.info("Waiting for client to halt")
        if not self.host.wait_down(HALT_TIME):
            err = "%s failed to shutdown after %d"
            err %= (self.host.hostname, HALT_TIME)
            raise error.AutotestRunError(err)
        logging.info("Client down, waiting for restart")
        if not self.host.wait_up(BOOT_TIME):
            # since reboot failed
            # hardreset the machine once if possible
            # before failing this control file
            warning = "%s did not come back up, hard resetting"
            warning %= self.host.hostname
            logging.warning(warning)
            try:
                self.host.hardreset(wait=False)
            except (AttributeError, error.AutoservUnsupportedError):
                warning = "Hard reset unsupported on %s"
                warning %= self.host.hostname
                logging.warning(warning)
            raise error.AutotestRunError("%s failed to boot after %ds" %
                                         (self.host.hostname, BOOT_TIME))
        self.host.reboot_followup()


    def _process_client_state_file(self):
        state_file = os.path.basename(self.remote_control_file) + ".state"
        state_path = os.path.join(self.results_dir, state_file)
        try:
            state_dict = pickle.load(open(state_path))
        except Exception, e:
            msg = "Ignoring error while loading client job state file: %s" % e
            logging.warning(msg)
            state_dict = {}

        # clear out the state file
        # TODO: stash the file away somewhere useful instead
        try:
            os.remove(state_path)
        except Exception:
            pass

        logging.debug("Persistent state variables pulled back from %s: %s",
                      self.host.hostname, state_dict)

        if "__run_test_cleanup" in state_dict:
            if state_dict["__run_test_cleanup"]:
                self.host.job.enable_test_cleanup()
            else:
                self.host.job.disable_test_cleanup()

        if "__last_boot_tag" in state_dict:
            self.host.job.last_boot_tag = state_dict["__last_boot_tag"]

        if "__sysinfo" in state_dict:
            self.host.job.sysinfo.deserialize(state_dict["__sysinfo"])


    def execute_control(self, timeout=None, client_disconnect_timeout=None):
        if not self.background:
            collector = log_collector(self.host, self.tag, self.results_dir)
            hostname = self.host.hostname
            remote_results = collector.client_results_dir
            local_results = collector.server_results_dir
            self.host.job.add_client_log(hostname, remote_results,
                                         local_results)

        section = 0
        start_time = time.time()

        logger = client_logger(self.host, self.tag, self.results_dir)
        try:
            while not timeout or time.time() < start_time + timeout:
                if timeout:
                    section_timeout = start_time + timeout - time.time()
                else:
                    section_timeout = None
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
                        self._wait_for_reboot()
                    except error.AutotestRunError, e:
                        self.host.job.record("ABORT", None, "reboot", str(e))
                        self.host.job.record("END ABORT", None, None, str(e))
                        raise
                    continue

                # if we reach here, something unexpected happened
                self.log_unexpected_abort(logger)

                # give the client machine a chance to recover from a crash
                self.host.wait_up(CRASH_RECOVERY_TIME)
                msg = ("Aborting - unexpected final status message from "
                       "client: %s\n") % last
                raise error.AutotestRunError(msg)
        finally:
            logger.close()
            if not self.background:
                collector.collect_client_job_results()
                self._process_client_state_file()
                self.host.job.remove_client_log(hostname, remote_results,
                                                local_results)

        # should only get here if we timed out
        assert timeout
        raise error.AutotestTimeoutError()


def _get_autodir(host):
    autodir = host.get_autodir()
    if autodir:
        logging.debug('Using existing host autodir: %s', autodir)
        return autodir
    try:
        # There's no clean way to do this. readlink may not exist
        cmd = ("python -c '%s' /etc/autotest.conf 2> /dev/null"
               % "import os,sys; print os.readlink(sys.argv[1])")
        autodir = os.path.dirname(host.run(cmd).stdout)
        if autodir:
            logging.debug('Using autodir from /etc/autotest.conf: %s', autodir)
            return autodir
    except error.AutoservRunError:
        pass
    for path in ['/usr/local/autotest', '/home/autotest']:
        try:
            host.run('ls %s > /dev/null 2>&1' % path)
            logging.debug('Found autodir at %s', path)
            return path
        except error.AutoservRunError:
            logging.debug('%s does not exist', path)
    raise error.AutotestRunError('Cannot figure out autotest directory')


class log_collector(object):
    def __init__(self, host, client_tag, results_dir):
        self.host = host
        if not client_tag:
            client_tag = "default"
        self.client_results_dir = os.path.join(host.get_autodir(), "results",
                                               client_tag)
        self.server_results_dir = results_dir


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
            self.host.get_file(self.client_results_dir + '/',
                               self.server_results_dir, preserve_symlinks=True)
        except Exception:
            # well, don't stop running just because we couldn't get logs
            e_msg = "Unexpected error copying test result logs, continuing ..."
            logging.error(e_msg)
            traceback.print_exc(file=sys.stdout)


# a file-like object for catching stderr from an autotest client and
# extracting status logs from it
class client_logger(object):
    """Partial file object to write to both stdout and
    the status log file.  We only implement those methods
    utils.run() actually calls.

    Note that this class is fairly closely coupled with server_job, as it
    uses special job._ methods to actually carry out the loggging.
    """
    status_parser = re.compile(r"^AUTOTEST_STATUS:([^:]*):(.*)$")
    test_complete_parser = re.compile(r"^AUTOTEST_TEST_COMPLETE:(.*)$")
    extract_indent = re.compile(r"^(\t*).*$")
    extract_timestamp = re.compile(r".*\ttimestamp=(\d+)\t.*$")

    def __init__(self, host, tag, server_results_dir):
        self.host = host
        self.job = host.job
        self.log_collector = log_collector(host, tag, server_results_dir)
        self.leftover = ""
        self.last_line = ""
        self.newest_timestamp = float("-inf")
        self.logs = {}
        self.server_warnings = []


    def _update_timestamp(self, line):
        match = self.extract_timestamp.search(line)
        if match:
            self.newest_timestamp = max(self.newest_timestamp,
                                        int(match.group(1)))


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
        for line in log_list:
            self.job._record_prerendered(line + '\n')
        if log_list:
            self.last_line = log_list[-1]


    def _process_quoted_line(self, tag, line):
        """Process a line quoted with an AUTOTEST_STATUS flag. If the
        tag is blank then we want to push out all the data we've been
        building up in self.logs, and then the newest line. If the
        tag is not blank, then push the line into the logs for handling
        later."""
        logging.info(line)
        if tag == "":
            self._process_logs()
            self.job._record_prerendered(line + '\n')
            self.last_line = line
        else:
            tag_parts = [int(x) for x in tag.split(".")]
            log_dict = self.logs
            for part in tag_parts:
                log_dict = log_dict.setdefault(part, {})
            log_list = log_dict.setdefault("logs", [])
            log_list.append(line)


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
        if status_match:
            tag, line = status_match.groups()
            self._process_info_line(line)
            self._process_quoted_line(tag, line)
        elif test_complete_match:
            self._process_logs()
            fifo_path, = test_complete_match.groups()
            self.log_collector.collect_client_job_results()
            self.host.run("echo A > %s" % fifo_path)
        else:
            logging.info(line)


    def _format_warnings(self, last_line, warnings):
        # use the indentation of whatever the last log line was
        indent = self.extract_indent.match(last_line).group(1)
        # if the last line starts a new group, add an extra indent
        if last_line.lstrip('\t').startswith("START\t"):
            indent += '\t'
        return [self.job._render_record("WARN", None, None, msg,
                                        timestamp, indent).rstrip('\n')
                for timestamp, msg in warnings]


    def _process_warnings(self, last_line, log_dict, warnings):
        if log_dict.keys() in ([], ["logs"]):
            # there are no sub-jobs, just append the warnings here
            warnings = self._format_warnings(last_line, warnings)
            log_list = log_dict.setdefault("logs", [])
            log_list += warnings
            for warning in warnings:
                sys.stdout.write(warning + '\n')
        else:
            # there are sub-jobs, so put the warnings in there
            log_list = log_dict.get("logs", [])
            if log_list:
                last_line = log_list[-1]
            for key in sorted(log_dict.iterkeys()):
                if key != "logs":
                    self._process_warnings(last_line,
                                           log_dict[key],
                                           warnings)


    def log_warning(self, msg, warning_type):
        """Injects a WARN message into the current status logging stream."""
        timestamp = int(time.time())
        if self.job.warning_manager.is_valid(timestamp, warning_type):
            self.server_warnings.append((timestamp, msg))


    def write(self, data):
        # first check for any new console warnings
        warnings = self.job._read_warnings() + self.server_warnings
        warnings.sort()  # sort into timestamp order
        # now process the newest data written out
        data = self.leftover + data
        lines = data.split("\n")
        # process every line but the last one
        for line in lines[:-1]:
            self._update_timestamp(line)
            # output any warnings between now and the next status line
            old_warnings = [(timestamp, msg) for timestamp, msg in warnings
                            if timestamp < self.newest_timestamp]
            self._process_warnings(self.last_line, self.logs, warnings)
            del warnings[:len(old_warnings)]
            self._process_line(line)
        # save off any warnings not yet logged for later processing
        self.server_warnings = warnings
        # save the last line for later processing
        # since we may not have the whole line yet
        self.leftover = lines[-1]


    def flush(self):
        sys.stdout.flush()


    def flush_all_buffers(self):
        if self.leftover:
            self._process_line(self.leftover)
            self.leftover = ""
        self._process_warnings(self.last_line, self.logs, self.server_warnings)
        self._process_logs()
        self.flush()


    def close(self):
        self.flush_all_buffers()


SiteAutotest = client_utils.import_site_class(
    __file__, "autotest_lib.server.site_autotest", "SiteAutotest",
    BaseAutotest)

class Autotest(SiteAutotest):
    pass
