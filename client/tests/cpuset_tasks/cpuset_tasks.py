import os, time
import subprocess
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import utils, error


class cpuset_tasks(test.test):
    version = 1
    preserve_srcdir = True

    def initialize(self):
        self.job.require_gcc()


    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make')


    def execute(self):
        os.chdir(self.tmpdir)
        tasks_bin = os.path.join(self.srcdir, 'tasks')
        p = subprocess.Popen([tasks_bin, ' 25000'])
        time.sleep(5)
        try:
            result = utils.run('cat /dev/cpuset/autotest_container/tasks',
                               ignore_status=True)
        except IOError:
            utils.nuke_subprocess(p)
            raise error.TestFail('cat cpuset/tasks failed with IOError')
        utils.nuke_subprocess(p)
        if result and result.exit_status:
            raise error.TestFail('cat cpuset/tasks failed')
