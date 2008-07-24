#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the Autotest class

        Autotest: software to run tests automatically
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)
"""

import re, os, sys, traceback, subprocess, tempfile, shutil, time

from autotest_lib.server import installable_object, utils, server_job
from autotest_lib.client.common_lib import logging
from autotest_lib.client.common_lib import error



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
    job = None


    def __init__(self, host = None):
        self.host = host
        self.got = False
        self.installed = False
        self.serverdir = utils.get_server_dir()
        super(BaseAutotest, self).__init__()


    @logging.record
    def install(self, host = None):
        """
        Install autotest.  If get() was not called previously, an
        attempt will be made to install from the autotest svn
        repository.

        Args:
                host: a Host instance on which autotest will be
                        installed

        Raises:
                AutoservError: if a tarball was not specified and
                        the target host does not have svn installed in its path

        TODO(poirier): check dependencies
        autotest needs:
        bzcat
        liboptdev (oprofile)
        binutils-dev (oprofile)
        make
        psutils (netperf)
        """
        if not host:
            host = self.host
        if not self.got:
            self.get()
        host.wait_up(timeout=30)
        host.setup()
        print "Installing autotest on %s" % host.hostname

        # Let's try to figure out where autotest is installed. If we can't,
        # (autotest not installed) just assume '/usr/local/autotest' and
        # proceed.
        try:
            autodir = _get_autodir(host)
        except error.AutotestRunError:
            autodir = '/usr/local/autotest'

        host.run('mkdir -p "%s"' % utils.sh_escape(autodir))

        if getattr(host, 'site_install_autotest', None):
            if host.site_install_autotest():
                self.installed = True
                return

        # try to install from file or directory
        if self.source_material:
            if os.path.isdir(self.source_material):
                # Copy autotest recursively
                host.send_file(self.source_material, autodir)
            else:
                # Copy autotest via tarball
                e_msg = 'Installation method not yet implemented!'
                raise NotImplementedError(e_msg)
            print "Installation of autotest completed"
            self.installed = True
            return

        # if that fails try to install using svn
        if utils.run('which svn').exit_status:
            raise error.AutoservError('svn not found on target machine: %s'
                                                                   % host.name)
        try:
            host.run('svn checkout %s %s' % (AUTOTEST_SVN, autodir))
        except error.AutoservRunError, e:
            host.run('svn checkout %s %s' % (AUTOTEST_HTTP, autodir))
        print "Installation of autotest completed"
        self.installed = True


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


    def run(self, control_file, results_dir = '.', host = None,
            timeout=None, tag=None, parallel_flag=False):
        """
        Run an autotest job on the remote machine.

        Args:
                control_file: an open file-like-obj of the control file
                results_dir: a str path where the results should be stored
                        on the local filesystem
                host: a Host instance on which the control file should
                        be run
                tag: tag name for the client side instance of autotest
                parallel_flag: flag set when multiple jobs are run at the
                          same time
        Raises:
                AutotestRunError: if there is a problem executing
                        the control file
        """
        host = self._get_host_and_setup(host)
        results_dir = os.path.abspath(results_dir)

        if tag:
            results_dir = os.path.join(results_dir, tag)

        atrun = _Run(host, results_dir, tag, parallel_flag)
        self._do_run(control_file, results_dir, host, atrun, timeout)


    def _get_host_and_setup(self, host):
        if not host:
            host = self.host
        if not self.installed:
            self.install(host)

        host.wait_up(timeout=30)
        return host


    def prepare_for_copying_logs(self, src, dest, host):
        keyval_path = ''
        if not os.path.exists(os.path.join(dest, 'keyval')):
            # Client-side keyval file can be copied directly
            return keyval_path
        # Copy client-side keyval to temporary location
        try:
            try:
                # Create temp file
                fd, keyval_path = tempfile.mkstemp('.keyval_%s' % host.hostname)
                host.get_file(os.path.join(src, 'keyval'), keyval_path)
            finally:
                # We will squirrel away the client side keyval
                # away and move it back when we are done
                self.temp_keyval_path = tempfile.mktemp()
                host.run('mv %s %s' %
                         (os.path.join(src, 'keyval'), self.temp_keyval_path))
        except (error.AutoservRunError, error.AutoservSSHTimeout):
            print "Prepare for copying logs failed"
        return keyval_path


    def process_copied_logs(self, dest, host, keyval_path):
        if not os.path.exists(os.path.join(dest, 'keyval')):
            # Client-side keyval file was copied directly
            return
        # Append contents of keyval_<host> file to keyval file
        try:
            # Read in new and old keyval files
            new_keyval = utils.read_keyval(keyval_path)
            old_keyval = utils.read_keyval(dest)
            # 'Delete' from new keyval entries that are in both
            tmp_keyval = {}
            for key, val in new_keyval.iteritems():
                if key not in old_keyval:
                    tmp_keyval[key] = val
            # Append new info to keyval file
            utils.write_keyval(dest, tmp_keyval)
            # Delete keyval_<host> file
            os.remove(keyval_path)
        except IOError:
            print "Process copied logs failed"


    def postprocess_copied_logs(self, src, host):
        # we can now put our keyval file back
        try:
            host.run('mv %s %s' % (self.temp_keyval_path,
                     os.path.join(src, 'keyval')))
        except:
            pass


    def _do_run(self, control_file, results_dir, host, atrun, timeout):
        try:
            atrun.verify_machine()
        except:
            print "Verify machine failed on %s. Reinstalling" % host.hostname
            self.install(host)
        atrun.verify_machine()
        debug = os.path.join(results_dir, 'debug')
        try:
            os.makedirs(debug)
        except:
            pass

        # Ready .... Aim ....
        for control in [atrun.remote_control_file,
                        atrun.remote_control_file + '.state',
                        atrun.manual_control_file,
                        atrun.manual_control_file + '.state']:
            host.run('rm -f ' + control)

        # Copy control_file to remote_control_file on the host
        tmppath = utils.get(control_file)
        host.send_file(tmppath, atrun.remote_control_file)
        if os.path.abspath(tmppath) != os.path.abspath(control_file):
            os.remove(tmppath)

        try:
            atrun.execute_control(timeout=timeout)
        finally:
            # make an effort to wait for the machine to come up
            try:
                host.wait_up(timeout=30)
            except error.AutoservError:
                # don't worry about any errors, we'll try and
                # get the results anyway
                pass

            # get the results
            if not atrun.tag:
                results = os.path.join(atrun.autodir, 'results', 'default')
            else:
                results = os.path.join(atrun.autodir, 'results', atrun.tag)

            # Copy all dirs in default to results_dir
            keyval_path = self.prepare_for_copying_logs(results, results_dir,
                                                        host)
            host.get_file(results + '/', results_dir)
            self.process_copied_logs(results_dir, host, keyval_path)
            self.postprocess_copied_logs(results, host)


    def run_timed_test(self, test_name, results_dir='.', host=None,
                       timeout=None, tag=None, *args, **dargs):
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
        self.run(control, results_dir, host, timeout=timeout, tag=tag)


    def run_test(self, test_name, results_dir='.', host=None,
                                                      tag=None, *args, **dargs):
        self.run_timed_test(test_name, results_dir, host, timeout=None,
                            tag=tag, *args, **dargs)


class _Run(object):
    """
    Represents a run of autotest control file.  This class maintains
    all the state necessary as an autotest control file is executed.

    It is not intended to be used directly, rather control files
    should be run using the run method in Autotest.
    """
    def __init__(self, host, results_dir, tag, parallel_flag):
        self.host = host
        self.results_dir = results_dir
        self.env = host.env
        self.tag = tag
        self.parallel_flag = parallel_flag
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

    def get_full_cmd(self, section):
        # build up the full command we want to run over the host
        cmd = [os.path.join(self.autodir, 'bin/autotest_client')]
        if section > 0:
            cmd.append('-c')
        if self.tag:
            cmd.append('-t %s' % self.tag)
        if self.host.job.use_external_logging():
            cmd.append('-l')
        cmd.append(self.remote_control_file)
        return ' '.join(cmd)


    def get_client_log(self, section):
        # open up the files we need for our logging
        client_log_file = os.path.join(self.results_dir, 'debug',
                                       'client.log.%d' % section)
        return open(client_log_file, 'w', 0)


    def execute_section(self, section, timeout):
        print "Executing %s/bin/autotest %s/control phase %d" % \
                                (self.autodir, self.autodir, section)

        full_cmd = self.get_full_cmd(section)
        client_log = self.get_client_log(section)
        redirector = server_job.client_logger(self.host.job)

        try:
            old_resultdir = self.host.job.resultdir
            self.host.job.resultdir = self.results_dir
            result = self.host.run(full_cmd, ignore_status=True,
                                   timeout=timeout,
                                   stdout_tee=client_log,
                                   stderr_tee=redirector)
        finally:
            redirector.close()
            self.host.job.resultdir = old_resultdir

        if result.exit_status == 1:
            self.host.job.aborted = True
            raise error.AutotestRunError("client job was aborted")
        if not result.stderr:
            raise error.AutotestRunError(
                "execute_section: %s failed to return anything\n"
                "stdout:%s\n" % (full_cmd, result.stdout))

        return redirector.last_line


    def execute_control(self, timeout=None):
        section = 0
        time_left = None
        if timeout:
            end_time = time.time() + timeout
            time_left = end_time - time.time()
        while not timeout or time_left > 0:
            last = self.execute_section(section, time_left)
            if timeout:
                time_left = end_time - time.time()
                if time_left <= 0:
                    break
            section += 1
            if re.match(r'^END .*\t----\t----\t.*$', last):
                print "Client complete"
                return
            elif re.match('^\t*GOOD\t----\treboot\.start.*$', last):
                print "Client is rebooting"
                print "Waiting for client to halt"
                if not self.host.wait_down(HALT_TIME):
                    err = "%s failed to shutdown after %d" % \
                                                (self.host.hostname, HALT_TIME)
                    raise error.AutotestRunError(err)
                print "Client down, waiting for restart"
                if not self.host.wait_up(BOOT_TIME):
                    # since reboot failed
                    # hardreset the machine once if possible
                    # before failing this control file
                    print "Hardresetting %s" % self.host.hostname
                    try:
                        self.host.hardreset(wait=False)
                    except error.AutoservUnsupportedError:
                        print "Hardreset unsupported on %s" % self.host.hostname
                    raise error.AutotestRunError("%s failed to boot after %ds" %
                                                (self.host.hostname, BOOT_TIME))
                self.host.reboot_followup()
                continue
            self.host.job.record("ABORT", None, None,
                                 "Autotest client terminated unexpectedly")
            # give the client machine a chance to recover from
            # possible crash
            self.host.wait_up(CRASH_RECOVERY_TIME)
            raise error.AutotestRunError("Aborting - unexpected final status "
                                         "message from client: %s\n" % last)

        # should only get here if we timed out
        assert timeout
        raise error.AutotestTimeoutError()


def _get_autodir(host):
    autodir = host.get_autodir()
    if autodir:
        return autodir
    try:
        # There's no clean way to do this. readlink may not exist
        cmd = "python -c 'import os,sys; print os.readlink(sys.argv[1])' /etc/autotest.conf 2> /dev/null"
        autodir = os.path.dirname(host.run(cmd).stdout)
        if autodir:
            return autodir
    except error.AutoservRunError:
        pass
    for path in ['/usr/local/autotest', '/home/autotest']:
        try:
            host.run('ls %s > /dev/null 2>&1' % \
                                             os.path.join(path, 'bin/autotest'))
            return path
        except error.AutoservRunError:
            pass
    raise error.AutotestRunError("Cannot figure out autotest directory")


# site_autotest.py may be non-existant or empty, make sure that an appropriate
# SiteAutotest class is created nevertheless
try:
    from site_autotest import SiteAutotest
except ImportError:
    class SiteAutotest(BaseAutotest):
        pass


class Autotest(SiteAutotest):
    pass
