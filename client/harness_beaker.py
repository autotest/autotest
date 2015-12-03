# harness_beaker.py
#
# Copyright (C) 2011 Jan Stancek <jstancek@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# started by Jan Stancek <jstancek@redhat.com> 2011
"""
The harness interface
The interface between the client and beaker lab controller.
"""
__author__ = """Don Zickus 2013"""

import logging
import os
import re
import sys
import time

from autotest.client.bkr_proxy import BkrProxy
from autotest.client.bkr_xml import BeakerXMLParser
from autotest.client.shared import utils, error

import harness

'''Use 5 minutes for console heartbeat'''
BEAKER_CONSOLE_HEARTBEAT = 60 * 5


class HarnessException(Exception):

    def __init__(self, text):
        Exception.__init__(self, text)


class harness_beaker(harness.harness):

    def __init__(self, job, harness_args):
        logging.debug('harness_beaker __init__')
        super(harness_beaker, self).__init__(job)

        # temporary hack until BEAKER_RECIPE_ID and BEAKER_LAB_CONTROLLER_URL is setup in beaker
        os.environ['BEAKER_RECIPE_ID'] = open('/root/RECIPE.TXT', 'r').read().strip()
        os.environ['BEAKER_LAB_CONTROLLER_URL'] = re.sub("/bkr/", ":8000", os.environ['BEAKER'])

        # control whether bootstrap environment remotely connects or stays offline
        # cheap hack to support flexible debug environment
        # the bootstrap job object is just a stub and won't have the '_state' attribute
        if hasattr(job, '_state'):
            is_bootstrap = False
            recipe_id = os.environ.get('RECIPE_ID') or '0'
        else:
            is_bootstrap = True
            recipe_id = os.environ.get('BEAKER_RECIPE_ID')
            os.environ['RECIPE_ID'] = recipe_id

        self.state_file = os.path.join(os.path.dirname(__file__), 'harness_beaker.state')
        self.recipe_id = recipe_id
        self.labc_url = os.environ.get('BEAKER_LAB_CONTROLLER_URL')
        self.hostname = os.environ.get('HOSTNAME')
        self.tests = self.get_processed_tests()
        self.watchdog_pid = None
        self.offline = False
        self.cmd = None

        # handle legacy rhts scripts called from inside tests
        os.environ['PATH'] = "%s:%s" % ('/var/cache/autotest', os.environ['PATH'])

        if harness_args:
            logging.info('harness_args: %s' % harness_args)
            os.environ['AUTOTEST_HARNESS_ARGS'] = harness_args
        self.args = self.parse_args(harness_args, is_bootstrap)

        logging.debug('harness_beaker: state_file: <%s>', self.state_file)
        logging.debug('harness_beaker: hostname: <%s>', self.hostname)
        logging.debug('harness_beaker: labc_url: <%s>', self.labc_url)

        if not self.hostname:
            raise error.HarnessError('Need valid hostname')

        # hack for flexible debug environment
        labc = not self.offline and self.labc_url or None

        self.bkr_proxy = BkrProxy(self.recipe_id, labc)

        self.setupInitSymlink()

    def parse_args(self, args, is_bootstrap):
        if not args:
            return

        for a in args.split(','):
            if a == 'offline':
                # use cached recipe and stay offline whole time
                self.offline = True

            elif a[:5] == 'cache':
                if len(a) > 5 and a[5] == '=':
                    # cache a different recipe instead
                    self.recipe_id = a[6:]

                # remotely retrieve recipe, but stay offline during run
                if not is_bootstrap:
                    self.offline = True

            elif a[:8] == 'quickcmd':
                if len(a) < 8 or a[8] != '=':
                    raise error.HarnessError("Bad use of 'quickcmd'")
                self.cmd = a[9:]

            else:
                raise error.HarnessError("Unknown beaker harness arg: %s" % a)

    def parse_quickcmd(self, args):
        # hack allow tests to quickly submit feedback through harness

        if not args:
            return

        if 'BEAKER_TASK_ID' not in os.environ:
            raise error.HarnessError("No BEAKER_TASK_ID set")
        task_id = os.environ['BEAKER_TASK_ID']

        # Commands are from tests and should be reported as results
        cmd, q_args = args.split(':')
        if cmd == 'submit_log':
            try:
                # rhts_submit_log has as args: -S -T -l
                # we just care about -l
                f = None
                arg_list = q_args.split(' ')
                while arg_list:
                    arg = arg_list.pop(0)
                    if arg == '-l':
                        f = arg_list.pop(0)
                        break
                if not f:
                    raise HarnessException("Argument -l not found in q_args "
                                           "'%s'" % q_args)
                self.bkr_proxy.task_upload_file(task_id, f)
            except Exception:
                logging.critical('ERROR: Failed to process quick cmd %s' % cmd)

        elif cmd == 'submit_result':
            def init_args(testname='Need/a/testname/here', status="None", logfile=None, score="0"):
                return testname, status, logfile, score

            try:
                # report_result has TESTNAME STATUS LOGFILE SCORE
                arg_list = q_args.split(' ')
                testname, status, logfile, score = init_args(*arg_list)

                resultid = self.bkr_proxy.task_result(task_id, status,
                                                      testname, score, '')

                if (logfile and os.path.isfile(logfile) and
                        os.path.getsize(logfile) != 0):
                    self.bkr_proxy.result_upload_file(task_id, resultid, logfile)

                # save the dmesg file
                dfile = '/tmp/beaker.dmesg'
                utils.system('dmesg -c > %s' % dfile)
                if os.path.getsize(dfile) != 0:
                    self.bkr_proxy.result_upload_file(task_id, resultid, dfile)
                # os.remove(dfile)

            except Exception:
                logging.critical('ERROR: Failed to process quick cmd %s' % cmd)

        elif cmd == 'reboot':
            # we are in a stub job.  Can't use self.job.reboot() :-(
            utils.system("sync; sync; reboot")
            self.run_pause()
            raise error.JobContinue("more to come")

        else:
            raise error.HarnessError("Bad sub-quickcmd: %s" % cmd)

    def bootstrap(self, fetchdir):
        '''How to kickstart autotest when you have no control file?
           You download the beaker XML, convert it to a control file
           and pass it back to autotest. Much like bootstrapping.. :-)
        '''

        # hack to sneakily pass results back to beaker without running
        # autotest.  Need to avoid calling get_recipe below
        if self.cmd:
            self.parse_quickcmd(self.cmd)
            return None

        recipe = self.init_recipe_from_beaker()

        # remove stale file
        if os.path.isfile(self.state_file):
            os.remove(self.state_file)
            self.tests = {}

        # sanity check
        if self.recipe_id != recipe.id:
            raise error.HarnessError('Recipe mismatch: machine %s.. != XML %s..' %
                                     (self.recipe_id, recipe.id))

        # create unique name
        control_file_name = recipe.job_id + '_' + recipe.id + '.control'
        control_file_path = fetchdir + '/' + control_file_name

        logging.debug('setting up control file - %s' % control_file_path)
        control_file = open(control_file_path, 'w')
        try:
            # convert recipe xml into control file
            for task in recipe.tasks:
                self.convert_task_to_control(fetchdir, control_file, task)

                # getting the task id later, will be hard, store it in file/memory
                self.write_processed_tests(self.get_test_name(task), task.id)

            control_file.close()
        except HarnessException:
            # hook to bail out on reservesys systems and not run autotest
            return None
        except Exception, ex:
            os.remove(control_file_path)
            raise error.HarnessError('beaker_harness: convert failed with -> %s' % ex)

        # autotest should find this under FETCHDIRTEST because it is unique
        return control_file_path

    def init_recipe_from_beaker(self):
        logging.debug('Contacting beaker to get task details')
        bxp = BeakerXMLParser()
        recipe_xml = self.get_recipe_from_LC()
        recipes_dict = bxp.parse_xml(recipe_xml)

        return self.find_recipe(recipes_dict)

    def init_task_params(self, task):
        logging.debug('PrepareTaskParams')
        if task is None:
            raise error.HarnessError('No valid task')

        for (name, value) in task.params.items():
            logging.debug('adding to os.environ: <%s=%s>', name, value)
            os.environ[name] = value

    def get_recipe_from_LC(self):
        logging.debug('trying to get recipe from LC:')
        try:
            recipe = self.bkr_proxy.get_recipe()
        except Exception, exc:
            raise error.HarnessError('Failed to retrieve xml: %s' % exc)
        return recipe

    def find_recipe(self, recipes_dict):
        if self.hostname in recipes_dict:
            return recipes_dict[self.hostname]
        for h in recipes_dict:
            if self.recipe_id == recipes_dict[h].id:
                return recipes_dict[h]
        raise error.HarnessError('No valid recipe for host %s' % self.hostname)

    # the block below was taken from standalone harness
    def setupInitSymlink(self):
        logging.debug('Symlinking init scripts')
        autodir = os.environ.get('AUTODIR')
        rc = os.path.join(autodir, 'tools/autotest')
        if os.path.isfile(rc) and os.path.islink(rc):
            # nothing to do
            return

        # see if system supports event.d versus inittab
        if os.path.exists('/etc/event.d'):
            # NB: assuming current runlevel is default
            initdefault = utils.system_output('/sbin/runlevel').split()[1]
        elif os.path.exists('/etc/inittab'):
            initdefault = utils.system_output('grep :initdefault: /etc/inittab')
            initdefault = initdefault.split(':')[1]
        else:
            initdefault = '2'
        try:
            utils.system('ln -sf %s /etc/init.d/autotest' % rc)
            utils.system('ln -sf %s /etc/rc%s.d/S99autotest' % (rc, initdefault))

            logging.debug('Labeling init scripts with unconfined_exec_t')
            utils.system('chcon -h system_u:object_r:unconfined_exec_t:s0 /etc/init.d/autotest')
            utils.system('chcon -h system_u:object_r:unconfined_exec_t:s0 /etc/rc%s.d/S99autotest' % initdefault)

            autotest_init = os.path.join(autodir, 'tools/autotest')
            ret = os.system('chcon system_u:object_r:unconfined_exec_t:s0 %s' % autotest_init)
            logging.debug('chcon returned <%s>', ret)
        except:
            logging.warning('Linking init scripts failed')

    def get_test_name(self, task):
        name = re.sub('-', '_', task.rpmName)
        return re.sub('\.', '_', name)

    def convert_task_to_control(self, fetchdir, control, task):
        """Tasks are really just:
           # yum install $TEST
           # cd /mnt/tests/$TEST
           # make run

           Convert that into a test module with a control file
        """
        timeout = ''
        if task.timeout:
            timeout = ", timeout=%s" % task.timeout

        # python doesn't like '-' in its class names
        rpm_name = self.get_test_name(task)
        rpm_dir = fetchdir + '/' + rpm_name
        rpm_file = rpm_dir + '/' + rpm_name + '.py'

        if task.status == 'Completed' and not self.offline:
            logging.debug("SKIP Completed test %s" % rpm_name)
            return

        if task.status == 'Running' and not self.offline:
            if re.search('reservesys', task.rpmName):
                logging.debug("Found reservesys, skipping execution")
                raise HarnessException('executing under a reservesys')
            else:
                logging.warning("Found Running test %s that isn't reservesys" % task.rpmName)

        # append test name to control file
        logging.debug('adding test %s to control file' % rpm_name)

        # Trick to avoid downloading XML all the time
        # statically update each TASK_ID
        control.write("os.environ['BEAKER_TASK_ID']='%s'\n" % task.id)
        control.write("job.run_test('%s'%s)\n" % (rpm_name, timeout))

        # TODO check for git commands in task.params

        # create the test itself
        logging.debug('setting up test %s' % (rpm_file))
        if not os.path.exists(rpm_dir):
            os.mkdir(rpm_dir)
        test = open(rpm_file, 'w')
        test.write("import os\n")
        test.write("from autotest.client import test, utils\n\n")
        test.write("class %s(test.test):\n" % rpm_name)
        test.write("    version=1\n\n")
        test.write("    def initialize(self):\n")
        test.write("        utils.system('yum install -y %s')\n" % task.rpmName)
        for param in task.params:
            test.write("        os.environ['%s']='%s'\n" % (param, task.params[param]))
        test.write("    def run_once(self):\n")
        test.write("        os.chdir('%s')\n" % task.rpmPath)
        test.write("        raw_output = utils.system_output('make run', retain_output=True)\n")
        test.write("        self.results = raw_output\n")
        test.close()

    def run_start(self):
        """A run within this job is starting"""
        logging.debug('run_start')
        try:
            self.start_watchdog(BEAKER_CONSOLE_HEARTBEAT)
        except Exception:
            logging.critical('ERROR: Failed to start watchdog')

    def run_pause(self):
        """A run within this job is completing (expect continue)"""
        logging.debug('run_pause')

    def run_reboot(self):
        """A run within this job is performing a reboot
           (expect continue following reboot)
        """
        logging.debug('run_reboot')

    def run_abort(self):
        """A run within this job is aborting. It all went wrong"""
        logging.debug('run_abort')
        self.bkr_proxy.recipe_abort()
        self.tear_down()

    def run_complete(self):
        """A run within this job is completing (all done)"""
        logging.debug('run_complete')
        self.tear_down()

    def run_test_complete(self):
        """A test run by this job is complete. Note that if multiple
        tests are run in parallel, this will only be called when all
        of the parallel runs complete."""
        logging.debug('run_test_complete')

    def test_status(self, status, tag):
        """A test within this job is completing"""
        logging.debug('test_status ' + status + ' / ' + tag)

    def test_status_detail(self, code, subdir, operation, status, tag,
                           optional_fields):
        """A test within this job is completing (detail)"""

        logging.debug('test_status_detail %s / %s / %s / %s / %s / %s',
                      code, subdir, operation, status, tag, str(optional_fields))

        if not subdir:
            # recipes - covered by run_start/complete/abort
            return

        """The mapping between beaker tasks and non-beaker tasks is not easy to
           separate.  Therefore we use the START and END markers along with the
           environment variable BEAKER_TASK_ID to help us.

           We keep an on-disk-file that stores the tests we have seen (or will run
           [add by the conversion function above]).  If the test is expected, it
           will have a task id associated with it and we can communicate with beaker
           about it.  Otherwise if no 'id' is found, assume this is a sub-task that
           beaker doesn't care about and keep all the results contained to the
           beaker results directory.
        """
        if code.startswith('START'):
            if subdir in self.tests and self.tests[subdir] != '0':
                # predefined beaker task
                self.bkr_proxy.task_start(self.tests[subdir])
            else:
                # some random sub-task, save for cleanup purposes
                self.write_processed_tests(subdir)
            return

        elif code.startswith('END'):
            if subdir in self.tests and self.tests[subdir] != '0':
                # predefined beaker task
                self.upload_task_files(self.tests[subdir], subdir)
                self.bkr_proxy.task_stop(self.tests[subdir])
            return

        else:
            if subdir in self.tests and self.tests[subdir] != '0':
                # predefine beaker tasks, will upload on END
                task_id = self.tests[subdir]
                task_upload = False
            else:
                # some random sub-task, save upload as task result
                # because there is no beaker task to add them too
                # task id was not saved in dictionary, get it from env
                if 'BEAKER_TASK_ID' not in os.environ:
                    raise error.HarnessError("No BEAKER_TASK_ID set")
                task_id = os.environ['BEAKER_TASK_ID']
                task_upload = True

            bkr_status = get_beaker_code(code)
            try:
                resultid = self.bkr_proxy.task_result(task_id, bkr_status,
                                                      subdir, 1, '')
                if task_upload:
                    self.upload_result_files(task_id, resultid, subdir)
            except Exception:
                logging.critical('ERROR: Failed to process test results')

    def tear_down(self):
        '''called from complete and abort.  clean up and shutdown'''
        self.kill_watchdog()
        if self.recipe_id != '0':
            self.upload_recipe_files()
            self.bkr_proxy.recipe_stop()
        os.remove(self.state_file)

    def start_watchdog(self, heartbeat):
        logging.debug('harness: Starting watchdog process, heartbeat: %d' % heartbeat)
        try:
            pid = os.fork()
            if pid == 0:
                self.watchdog_loop(heartbeat)
            else:
                self.watchdog_pid = pid
                logging.debug('harness: Watchdog process started, pid: %d', self.watchdog_pid)
        except OSError, e:
            logging.error('harness: fork in start_watchdog failed: %d (%s)\n' % (e.errno, e.strerror))

    def kill_watchdog(self):
        logging.debug('harness: Killing watchdog, pid: %d', self.watchdog_pid)
        utils.nuke_pid(self.watchdog_pid)
        self.watchdog_pid = None

    def watchdog_loop(self, heartbeat):
        while True:
            time.sleep(heartbeat)
            logging.info('[-- MARK -- %s]' % time.asctime(time.localtime(time.time())))
        sys.exit()

    def get_processed_tests(self):
        tests = {}

        if not os.path.isfile(self.state_file):
            return tests

        f = open(self.state_file, 'r')
        lines = f.readlines()
        f.close()

        for line in lines:
            subdir, t_id = line.strip().split()

            # duplicates result from multiple writers
            # once during the conversion and then again
            # during an update of a test run
            # former has task ids, latter will not
            if subdir not in tests:
                tests[subdir] = t_id
        return tests

    def write_processed_tests(self, subdir, t_id='0'):
        f = open(self.state_file, 'a')
        f.write(subdir + ' ' + t_id + '\n')
        f.close()

    def upload_recipe_files(self):
        path = self.job.resultdir

        # refresh latest executed tests
        tests = self.get_processed_tests()
        logging.debug("Recipe filtering following tests: %s" % tests)

        for root, dirnames, files in os.walk(path):
            '''do not upload previously uploaded results files'''
            for d in dirnames:
                if d in tests:
                    dirnames.remove(d)

            for name in files:
                # strip full path
                remotepath = re.sub(path, "", root)
                # The localfile has the full path
                localfile = os.path.join(root, name)
                if os.path.getsize(localfile) == 0:
                    continue  # skip empty files

                # Upload the file
                self.bkr_proxy.recipe_upload_file(localfile, remotepath)

    def upload_task_files(self, task_id, subdir):
        path = os.path.join(self.job.resultdir, subdir)

        for root, _, files in os.walk(path):
            for name in files:
                # strip full path
                remotepath = re.sub(path, "", root)
                # The localfile has the full path
                localfile = os.path.join(root, name)
                if os.path.getsize(localfile) == 0:
                    continue  # skip empty files

                # Upload the file
                self.bkr_proxy.task_upload_file(task_id, localfile,
                                                remotepath)

    def upload_result_files(self, task_id, resultid, subdir):
        path = os.path.join(self.job.resultdir, subdir)

        for root, _, files in os.walk(path):
            for name in files:
                # strip full path
                remotepath = re.sub(path, "", root)
                # The localfile has the full path
                localfile = os.path.join(root, name)
                if os.path.getsize(localfile) == 0:
                    continue  # skip empty files

                # Upload the file
                self.bkr_proxy.result_upload_file(task_id, resultid, localfile,
                                                  remotepath)


def get_beaker_code(at_code):
    bkr_status = 'Warn'
    if at_code == 'GOOD':
        bkr_status = 'Pass'
    if at_code in ['WARN', 'FAIL', 'ERROR', 'ABORT', 'TEST_NA']:
        bkr_status = 'Fail'
    return bkr_status


if __name__ == '__main__':
    pass
