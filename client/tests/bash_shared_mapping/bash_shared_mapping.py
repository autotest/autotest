import signal, os
from autotest_lib.client.bin import utils, test

class bash_shared_mapping(test.test):
    version = 3

    # http://www.zip.com.au/~akpm/linux/patches/stuff/ext3-tools.tar.gz
    def setup(self, tarball = 'ext3-tools.tar.gz'):
        self.tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(self.tarball, self.srcdir)

        os.chdir(self.srcdir)
        utils.system('patch -p1 < ../makefile.patch')
        utils.make('bash-shared-mapping usemem')


    def initialize(self):
        self.job.require_gcc()


    def execute(self, testdir = None, iterations = 10000):
        if not testdir:
            testdir = self.tmpdir
        os.chdir(testdir)
        file = os.path.join(testdir, 'foo')
        # Want to use 3/4 of all memory for each of
        # bash-shared-mapping and usemem
        kilobytes = (3 * utils.memtotal()) / 4

        # Want two usemem -m megabytes in parallel in background.
        pid = [None, None]
        usemem = os.path.join(self.srcdir, 'usemem')
        args = ('usemem', '-N', '-m', '%d' % (kilobytes / 1024))
        # print_to_tty ('2 x ' + ' '.join(args))
        for i in (0,1):
            pid[i] = os.spawnv(os.P_NOWAIT, usemem, args)

        cmd = "%s/bash-shared-mapping %s %d -t %d -n %d" % \
                        (self.srcdir, file, kilobytes,
                         utils.count_cpus(), iterations)
        os.system(cmd)

        for i in (0, 1):
            os.kill(pid[i], signal.SIGKILL)
