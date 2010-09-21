import os
from autotest_lib.client.bin import test, utils


# tests is a simple array of "cmd" "arguments"
tests = [["aio-dio-invalidate-failure", "poo"],
         ["aio-dio-subblock-eof-read", "eoftest"],
         ["aio-free-ring-with-bogus-nr-pages", ""],
         ["aio-io-setup-with-nonwritable-context-pointer", ""],
         ["aio-dio-extend-stat", "file"],
        ]
name = 0
arglist = 1

class aio_dio_bugs(test.test):
    version = 5
    preserve_srcdir = True

    def initialize(self):
        self.job.require_gcc()
        self.job.setup_dep(['libaio'])
        ldflags = '-L ' + self.autodir + '/deps/libaio/lib'
        cflags = '-I ' + self.autodir + '/deps/libaio/include'
        self.gcc_flags = ldflags + ' ' + cflags


    def setup(self):
        os.chdir(self.srcdir)
        utils.make('"CFLAGS=' + self.gcc_flags + '"')


    def execute(self, args = ''):
        os.chdir(self.tmpdir)
        libs = self.autodir + '/deps/libaio/lib/'
        ld_path = utils.prepend_path(libs,
                              utils.environ('LD_LIBRARY_PATH'))
        var_ld_path = 'LD_LIBRARY_PATH=' + ld_path
        for test in tests:
            cmd = self.srcdir + '/' + test[name] + ' ' + args + ' ' \
                                                               + test[arglist]
            utils.system(var_ld_path + ' ' + cmd)
