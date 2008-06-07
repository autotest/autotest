# This requires aio headers to build.
# Should work automagically out of deps now.

# NOTE - this should also have the ability to mount a filesystem,
# run the tests, unmount it, then fsck the filesystem
import os
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils


class aiostress(test.test):
    version = 2

    def initialize(self):
        self.job.setup_dep(['libaio'])
        ldflags = '-L ' + self.autodir + '/deps/libaio/lib'
        cflags = '-I ' + self.autodir + '/deps/libaio/include'
        self.gcc_flags = ldflags + ' ' + cflags


    # ftp://ftp.suse.com/pub/people/mason/utils/aio-stress.c
    def setup(self, tarball = None):
        print self.srcdir, self.bindir, self.tmpdir
        os.mkdir(self.srcdir)
        os.chdir(self.srcdir)
        utils.system('cp ' + self.bindir+'/aio-stress.c .')
        os.chdir(self.srcdir)
        self.gcc_flags += ' -Wall -lpthread -laio'
        cmd = 'gcc ' + self.gcc_flags + ' aio-stress.c -o aio-stress'
        utils.system(cmd)


    def execute(self, args = ''):
        os.chdir(self.tmpdir)
        libs = self.autodir+'/deps/libaio/lib/'
        ld_path = autotest_utils.prepend_path(libs,
                                      autotest_utils.environ('LD_LIBRARY_PATH'))
        var_ld_path = 'LD_LIBRARY_PATH=' + ld_path
        cmd = self.srcdir + '/aio-stress ' + args + ' poo'
        profilers = self.job.profilers

        if not profilers.only():
            utils.system(var_ld_path + ' ' + cmd)
            report = open(self.debugdir + '/stderr')
            keyval = open(self.resultsdir + '/keyval', 'w')
            _format_results(report, keyval)

        # Do a profiling run if necessary
        if profilers.present():
            profilers.start(self)
            utils.system(var_ld_path + ' ' + cmd)
            profilers.stop(self)
            profilers.report(self)
            if profilers.only():
                report = open(self.debugdir + '/stderr')
                keyval = open(self.resultsdir + '/keyval', 'w')
                _format_results(report, keyval)



def _format_results(report, keyval):
    for line in report:
        if 'threads' in line:
            if 'files' in line:
                if 'contexts' in line:
                    break

    for line in report:
        line = line.split(')')[0]
        key, value = line.split('(')
        key = key.strip().replace(' ', '_')
        value = value.split()[0]
        print >> keyval, '%s=%s' % (key, value)


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
