# Copyright Martin J. Bligh, Andy Whitcroft, 2006
#
# Shell class for a test, inherited by all individual tests
#
# Methods:
#       __init__        initialise
#       initialize      run once for each job
#       setup           run once for each new version of the test installed
#       run             run the test (wrapped by job.run_test())
#
# Data:
#       job             backreference to the job this test instance is part of
#       outputdir       eg. results/<job>/<testname.tag>
#       resultsdir      eg. results/<job>/<testname.tag>/results
#       profdir         eg. results/<job>/<testname.tag>/profiling
#       debugdir        eg. results/<job>/<testname.tag>/debug
#       bindir          eg. tests/<test>
#       src             eg. tests/<test>/src
#       tmpdir          eg. tmp/<testname.tag>

import os, traceback, sys, shutil, logging, resource, glob

from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.common_lib import test as common_test
from autotest_lib.client.bin import sysinfo, os_dep


class test(common_test.base_test):
    # Segmentation fault handling is something that is desirable only for
    # client side tests.
    def configure_crash_handler(self):
        """
        Configure the crash handler by:
         * Setting up core size to unlimited
         * Putting an appropriate crash handler on /proc/sys/kernel/core_pattern
         * Create files that the crash handler will use to figure which tests
           are active at a given moment

        The crash handler will pick up the core file and write it to
        self.debugdir, and perform analysis on it to generate a report. The
        program also outputs some results to syslog.

        If multiple tests are running, an attempt to verify if we still have
        the old PID on the system process table to determine whether it is a
        parent of the current test execution. If we can't determine it, the
        core file and the report file will be copied to all test debug dirs.
        """
        self.crash_handling_enabled = False

        # make sure this script will run with a new enough python to work
        cmd = ("python -c 'import sys; "
               "print sys.version_info[0], sys.version_info[1]'")
        result = utils.run(cmd, ignore_status=True)
        if result.exit_status != 0:
            logging.warning('System python is too old, crash handling disabled')
            return
        major, minor = [int(x) for x in result.stdout.strip().split()]
        if (major, minor) < (2, 4):
            logging.warning('System python is too old, crash handling disabled')
            return

        self.pattern_file = '/proc/sys/kernel/core_pattern'
        try:
            # Enable core dumps
            resource.setrlimit(resource.RLIMIT_CORE, (-1, -1))
            # Trying to backup core pattern and register our script
            self.core_pattern_backup = open(self.pattern_file, 'r').read()
            pattern_file = open(self.pattern_file, 'w')
            tools_dir = os.path.join(self.autodir, 'tools')
            crash_handler_path = os.path.join(tools_dir, 'crash_handler.py')
            pattern_file.write('|' + crash_handler_path + ' %p %t %u %s %h %e')
            # Writing the files that the crash handler is going to use
            self.debugdir_tmp_file = ('/tmp/autotest_results_dir.%s' %
                                      os.getpid())
            utils.open_write_close(self.debugdir_tmp_file, self.debugdir + "\n")
        except Exception, e:
            logging.warning('Crash handling disabled: %s', e)
        else:
            self.crash_handling_enabled = True
            try:
                os_dep.command('gdb')
            except ValueError:
                logging.warning('Could not find GDB installed. Crash handling '
                                'will operate with limited functionality')
            logging.debug('Crash handling enabled')


    def crash_handler_report(self):
        """
        If core dumps are found on the debugdir after the execution of the
        test, let the user know.
        """
        if self.crash_handling_enabled:
            # Remove the debugdir info file
            os.unlink(self.debugdir_tmp_file)
            # Restore the core pattern backup
            try:
                utils.open_write_close(self.pattern_file,
                                       self.core_pattern_backup)
            except EnvironmentError:
                pass
            # Let the user know if core dumps were generated during the test
            core_dirs = glob.glob('%s/crash.*' % self.debugdir)
            if core_dirs:
                logging.warning('Programs crashed during test execution')
                for dir in core_dirs:
                    logging.warning('Please verify %s for more info', dir)


def runtest(job, url, tag, args, dargs):
    common_test.runtest(job, url, tag, args, dargs, locals(), globals(),
                        job.sysinfo.log_before_each_test,
                        job.sysinfo.log_after_each_test,
                        job.sysinfo.log_before_each_iteration,
                        job.sysinfo.log_after_each_iteration)
