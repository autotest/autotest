import os
from autotest_lib.client.bin import test, utils


class fio(test.test):
    """
    fio is an I/O tool mean for benchmark and stress/hardware verification.

    @see: http://freecode.com/projects/fio
    """
    version = 3

    def initialize(self):
        self.job.require_gcc()


    def setup(self, tarball = 'fio-2.0.5.tar.bz2'):
        """
        Compiles and installs fio.

        @see: http://brick.kernel.dk/snaps/fio-2.0.5.tar.bz2
        """
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)

        self.job.setup_dep(['libaio'])
        ldflags = '-L' + self.autodir + '/deps/libaio/lib'
        cflags = '-I' + self.autodir + '/deps/libaio/include'
        var_ldflags = 'LDFLAGS="' + ldflags + '"'
        var_cflags  = 'CFLAGS="' + cflags + '"'

        os.chdir(self.srcdir)
        utils.system('patch -p1 < ../Makefile.patch')
        utils.system('%s %s make' % (var_ldflags, var_cflags))


    def run_once(self, args = '', user = 'root'):
        os.chdir(self.srcdir)
        ##vars = 'TMPDIR=\"%s\" RESULTDIR=\"%s\"' % (self.tmpdir, self.resultsdir)
        vars = 'LD_LIBRARY_PATH="' + self.autodir + '/deps/libaio/lib"'
        ##args = '-m -o ' + self.resultsdir + '/fio-tio.log ' + self.srcdir + '/examples/tiobench-example'
        log = os.path.join(self.resultsdir, 'fio-mixed.log')
        job = os.path.join(self.bindir, 'fio-mixed.job')
        args = '--output %s %s' % (log, job)
        utils.system(vars + ' ./fio ' + args)
