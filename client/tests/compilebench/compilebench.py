import os
import re
from autotest_lib.client.bin import test, utils

test_name = 'compilebench'

class compilebench(test.test):
    version = 1

    def setup(self, tarball = 'compilebench-0.6.tar.gz'):
        self.tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(self.tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.system('patch -p1 < ../compilebench.patch')


    def run_once(self, dir=None, num_kernel_trees=10, num_random_runs=30):
        if not dir:
            dir = self.tmpdir

        cmd = "%s -D %s -s %s -i %d -r %d" % (
                         os.path.join(self.srcdir, test_name),
                         dir,
                         self.srcdir,
                         num_kernel_trees,
                         num_random_runs)

        output = utils.system_output(cmd)

        self.__format_results(output)


    def __format_results(self, output):
        keylist = {}

        THROUGHPUT = "MB_s"
        TIME       = "secs"

        run_type_list = (
            ('intial create', THROUGHPUT, 6, 'initial_create'),
            ('create', THROUGHPUT, 5, 'new_create'),
            ('patch', THROUGHPUT, 5, 'patch'),
            ('compile', THROUGHPUT, 5, 'compile'),
            ('clean', THROUGHPUT, 5, 'clean'),
            ('read tree', THROUGHPUT, 6, 'read_tree'),
            ('read compiled tree', THROUGHPUT, 7, 'read_compiled_tree'),
            ('delete tree', TIME, 6, 'delete_tree'),
            ('delete compiled tree', TIME, 6, 'delete_compiled_tree'),
            ('stat tree', TIME, 6, 'stat_tree'),
            ('stat compiled tree', TIME, 7, 'stat_compiled_tree'),
        )

# intial create total runs 10 avg 149.82 MB/s (user 0.63s sys 0.85s)
# create total runs 5 avg 27.50 MB/s (user 0.62s sys 0.83s)
# patch total runs 4 avg 15.01 MB/s (user 0.33s sys 0.63s)
# compile total runs 7 avg 41.47 MB/s (user 0.14s sys 0.75s)
# clean total runs 4 avg 697.77 MB/s (user 0.02s sys 0.08s)
# read tree total runs 2 avg 23.68 MB/s (user 0.85s sys 1.59s)
# read compiled tree total runs 1 avg 25.27 MB/s (user 0.98s sys 2.84s)
# delete tree total runs 2 avg 1.48 seconds (user 0.35s sys 0.45s)
# no runs for delete compiled tree
# stat tree total runs 4 avg 1.46 seconds (user 0.35s sys 0.26s)
# stat compiled tree total runs 1 avg 1.49 seconds (user 0.37s sys 0.29s)

        for line in output.splitlines():
            for pattern, result_type, position, tag in run_type_list:
                if re.search('^%s' % pattern, line):
                    l = line.split()
                    value = l[position]

                    s = "%s_%s" % (tag, result_type)

                    keylist[s] = value
                    break

        self.write_perf_keyval(keylist)
