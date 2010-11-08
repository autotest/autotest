import os
from autotest_lib.client.bin import test, utils


class hackbench(test.test):
    """
    This module will run the hackbench benchmark. Hackbench is a benchmark for
    measuring the performance, overhead and scalability of the Linux scheduler.
    The C program was pick from Ingo Molnar's page.

    @author: Nikhil Rao (ncrao@google.com)
    @see: http://people.redhat.com/~mingo/cfs-scheduler/tools/hackbench.c
    """
    version = 1
    preserve_srcdir = True


    def setup(self):
        os.chdir(self.srcdir)
        if 'CC' in os.environ:
            cc = '$CC'
        else:
            cc = 'cc'
        utils.system('%s -lpthread hackbench.c -o hackbench' % cc)


    def initialize(self):
        self.job.require_gcc()
        self.results = None


    def run_once(self, num_groups=90):
        """
        Run hackbench, store the output in raw output files per iteration and
        also in the results list attribute.

        @param num_groups: Number of children processes hackbench will spawn.
        """
        hackbench_bin = os.path.join(self.srcdir, 'hackbench')
        cmd = '%s %s' % (hackbench_bin, num_groups)
        raw_output = utils.system_output(cmd, retain_output=True)
        self.results = raw_output

        path = os.path.join(self.resultsdir, 'raw_output_%s' % self.iteration)
        utils.open_write_close(path, raw_output)


    def postprocess_iteration(self):
        """
        Pick up the results attribute and write it in the performance keyval.
        """
        lines = self.results.split('\n')
        for line in lines:
            if line.startswith('Time:'):
                time_val = line.split()[1]
                self.write_perf_keyval({'time': time_val})
