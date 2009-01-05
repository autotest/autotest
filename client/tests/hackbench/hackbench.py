import os
from autotest_lib.client.bin import test, utils


class hackbench(test.test):
    version = 1
    preserve_srcdir = True


    def setup(self):
        os.chdir(self.srcdir)
        utils.system('cc -lpthread hackbench.c -o hackbench')


    def initialize(self):
        self.job.require_gcc()
        self.results = []


    def run_once(self, num_groups=90):
        hackbench_bin = os.path.join(self.srcdir, 'hackbench')
        cmd = '%s %s' % (hackbench_bin, num_groups)
        self.results.append(utils.system_output(cmd, retain_output=True))


    def postprocess(self):
        for line in self.results:
            if line.startswith('Time:'):
                time_val = line.split()[1]
                self.write_perf_keyval({'time': time_val})
