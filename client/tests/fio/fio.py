import os
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils


class fio(test.test):
    version = 2

    def initialize(self):
        self.job.require_gcc()


    # http://brick.kernel.dk/snaps/fio-1.16.5.tar.bz2
    def setup(self, tarball = 'fio-1.16.5.tar.bz2'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)

        self.job.setup_dep(['libaio'])
        ldflags = '-L' + self.autodir + '/deps/libaio/lib'
        cflags = '-I' + self.autodir + '/deps/libaio/include'
        var_ldflags = 'LDFLAGS="' + ldflags + '"'
        var_cflags  = 'CFLAGS="' + cflags + '"'

        os.chdir(self.srcdir)
        utils.system('patch -p1 < ../Makefile.patch')
        utils.system('%s %s make' % (var_ldflags, var_cflags))


    def execute(self, args = '', user = 'root'):
        os.chdir(self.srcdir)
        ##vars = 'TMPDIR=\"%s\" RESULTDIR=\"%s\"' % (self.tmpdir, self.resultsdir)
        vars = 'LD_LIBRARY_PATH="' + self.autodir + '/deps/libaio/lib"'
        ##args = '-m -o ' + self.resultsdir + '/fio-tio.log ' + self.srcdir + '/examples/tiobench-example';
        args = '--output ' + self.resultsdir + '/fio-mixed.log ' + self.bindir + '/fio-mixed.job';
        utils.system(vars + ' ./fio ' + args)

        # Do a profiling run if necessary
        profilers = self.job.profilers
        if profilers.present():
            profilers.start(self)
            utils.system(vars + ' ./fio ' + args)
            profilers.stop(self)
            profilers.report(self)
