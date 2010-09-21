import os
from autotest_lib.client.bin import test, utils


class spew(test.test):
    version = 1

    def initialize(self):
        self.job.require_gcc()


    # ftp://ftp.berlios.de/pub/spew/1.0.5/spew-1.0.5.tgz
    def setup(self, tarball = 'spew-1.0.5.tgz'):
        self.tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(self.tarball, self.srcdir)

        os.chdir(self.srcdir)
        utils.configure()
        utils.make()


    def run_once(self, testdir = None, filesize='100M', type='write',
                 pattern='random'):
        cmd = os.path.join(self.srcdir, 'src/spew')
        if not testdir:
            testdir = self.tmpdir
        tmpfile = os.path.join(testdir, 'spew-test.%d' % os.getpid())
        results = os.path.join(self.resultsdir, 'stdout.%d' % self.iteration)
        args = '--%s -p %s -b 2k -B 2M %s %s' % \
                        (type, pattern, filesize, tmpfile)
        cmd += ' ' + args

        open(self.resultsdir + '/command', 'w').write(cmd + '\n')
        self.job.logging.redirect(results)
        try:
            utils.system(cmd)
        finally:
            self.job.logging.restore()
