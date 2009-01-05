# This requires aio headers to build.
# Should work automagically out of deps now.

# NOTE - this should also have the ability to mount a filesystem,
# run the tests, unmount it, then fsck the filesystem
import os
from autotest_lib.client.bin import test, utils


class fsx(test.test):
    version = 3

    def initialize(self):
        self.job.require_gcc()


    # http://www.zip.com.au/~akpm/linux/patches/stuff/ext3-tools.tar.gz
    def setup(self, tarball = 'ext3-tools.tar.gz'):
        self.tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(self.tarball, self.srcdir)

        self.job.setup_dep(['libaio'])
        ldflags = '-L' + self.autodir + '/deps/libaio/lib'
        cflags = '-I' + self.autodir + '/deps/libaio/include'
        var_ldflags = 'LDFLAGS="' + ldflags + '"'
        var_cflags  = 'CFLAGS="' + cflags + '"'
        self.make_flags = var_ldflags + ' ' + var_cflags

        os.chdir(self.srcdir)
        utils.system('patch -p1 < ../fsx-linux.diff')
        utils.system(self.make_flags + ' make fsx-linux')


    def run_once(self, dir=None, repeat=100000):
        args = '-N %s' % repeat
        if not dir:
            dir = self.tmpdir
        os.chdir(dir)
        libs = self.autodir+'/deps/libaio/lib/'
        ld_path = utils.prepend_path(libs,
                           utils.environ('LD_LIBRARY_PATH'))
        var_ld_path = 'LD_LIBRARY_PATH=' + ld_path
        cmd = self.srcdir + '/fsx-linux ' + args + ' poo'
        utils.system(var_ld_path + ' ' + cmd)
