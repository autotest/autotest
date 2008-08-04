# This requires aio headers to build.
# Should work automagically out of deps now.

# NOTE - this should also have the ability to mount a filesystem,
# run the tests, unmount it, then fsck the filesystem
import os
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils


class fsx(test.test):
    version = 3

    def initialize(self):
        self.job.require_gcc()


    # http://www.zip.com.au/~akpm/linux/patches/stuff/ext3-tools.tar.gz
    def setup(self, tarball = 'ext3-tools.tar.gz'):
        self.tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        autotest_utils.extract_tarball_to_dir(self.tarball, self.srcdir)

        self.job.setup_dep(['libaio'])
        ldflags = '-L' + self.autodir + '/deps/libaio/lib'
        cflags = '-I' + self.autodir + '/deps/libaio/include'
        var_ldflags = 'LDFLAGS="' + ldflags + '"'
        var_cflags  = 'CFLAGS="' + cflags + '"'
        self.make_flags = var_ldflags + ' ' + var_cflags

        os.chdir(self.srcdir)
        utils.system('patch -p1 < ../fsx-linux.diff')
        utils.system(self.make_flags + ' make fsx-linux')


    def execute(self, testdir = None, repeat = '100000'):
        args = '-N ' + repeat
        if not testdir:
            testdir = self.tmpdir
        os.chdir(testdir)
        libs = self.autodir+'/deps/libaio/lib/'
        ld_path = autotest_utils.prepend_path(libs,
                           autotest_utils.environ('LD_LIBRARY_PATH'))
        var_ld_path = 'LD_LIBRARY_PATH=' + ld_path
        cmd = self.srcdir + '/fsx-linux ' + args + ' poo'
        profilers = self.job.profilers
        if not profilers.only():
            utils.system(var_ld_path + ' ' + cmd)

        # Do a profiling run if necessary
        if profilers.present():
            profilers.start(self)
            utils.system(var_ld_path + ' ' + cmd)
            profilers.stop(self)
            profilers.report(self)
