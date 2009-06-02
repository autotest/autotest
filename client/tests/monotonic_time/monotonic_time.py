import os, re, logging
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class monotonic_time(test.test):
    version = 1

    preserve_srcdir = True

    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make')


    def initialize(self):
        self.job.require_gcc()


    def run_once(self, test_type = None, duration = 300, threshold = None):
        if not test_type:
            raise error.TestError('missing test type')

        cmd = self.srcdir + '/time_test'
        cmd += ' --duration ' + str(duration)
        if threshold:
            cmd += ' --threshold ' + str(threshold)
        cmd += ' ' + test_type

        self.results = utils.run(cmd, ignore_status=True)
        logging.info('Time test command exit status: %s',
                     self.results.exit_status)
        if self.results.exit_status != 0:
            for line in self.results.stdout.splitlines():
                if line.startswith('ERROR:'):
                    raise error.TestError(line)
                if line.startswith('FAIL:'):
                    raise error.TestFail(line)
            raise error.TestError('unknown test failure')
