# This requires aio headers to build.
# Should work automagically out of deps now.
import os
from autotest_lib.client.bin import test, utils


class aiostress(test.test):
    version = 3

    def initialize(self):
        self.job.require_gcc()
        self.job.setup_dep(['libaio'])
        ldflags = '-L ' + self.autodir + '/deps/libaio/lib'
        cflags = '-I ' + self.autodir + '/deps/libaio/include'
        self.gcc_flags = ldflags + ' ' + cflags


    # ftp://ftp.suse.com/pub/people/mason/utils/aio-stress.c
    def setup(self, tarball = None):
        os.mkdir(self.srcdir)
        os.chdir(self.srcdir)
        utils.system('cp ' + self.bindir+'/aio-stress.c .')
        os.chdir(self.srcdir)
        self.gcc_flags += ' -Wall -lpthread -laio'
        cmd = 'gcc ' + self.gcc_flags + ' aio-stress.c -o aio-stress'
        utils.system(cmd)


    def run_once(self, args = ''):
        os.chdir(self.tmpdir)
        libs = self.autodir+'/deps/libaio/lib/'
        ld_path = utils.prepend_path(libs,
                                      utils.environ('LD_LIBRARY_PATH'))
        var_ld_path = 'LD_LIBRARY_PATH=' + ld_path
        cmd = self.srcdir + '/aio-stress ' + args + ' poo'

        stderr = os.path.join(self.debugdir, 'stderr')
        utils.system('%s %s 2> %s' % (var_ld_path, cmd, stderr))
        report = open(stderr)
        self.format_results(report)


    def format_results(self, report):
        for line in report:
            if 'threads' in line:
                if 'files' in line:
                    if 'contexts' in line:
                        break

        keyval = {}
        for line in report:
            line = line.split(')')[0]
            key, value = line.split('(')
            key = key.strip().replace(' ', '_')
            value = value.split()[0]
            keyval[key] = value

        self.write_perf_keyval(keyval)

"""
file size 1024MB, record size 64KB, depth 64, ios per iteration 8
max io_submit 8, buffer alignment set to 4KB
threads 1 files 1 contexts 1 context offset 2MB verification off
write on poo (245.77 MB/s) 1024.00 MB in 4.17s
thread 0 write totals (55.86 MB/s) 1024.00 MB in 18.33s
read on poo (1311.54 MB/s) 1024.00 MB in 0.78s
thread 0 read totals (1307.66 MB/s) 1024.00 MB in 0.78s
random write on poo (895.47 MB/s) 1024.00 MB in 1.14s
thread 0 random write totals (18.42 MB/s) 1024.00 MB in 55.59s
random read on poo (1502.89 MB/s) 1024.00 MB in 0.68s
thread 0 random read totals (1474.36 MB/s) 1024.00 MB in 0.69s
"""
