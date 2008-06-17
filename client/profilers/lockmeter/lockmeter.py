# NOTE: if you get compile errors from config.h, referring you to a FAQ,
# you might need to do 'cat < /dev/null > /usr/include/linux/config.h'.
# But read the FAQ first.
import os
from autotest_lib.client.bin import autotest_utils, profiler
from autotest_lib.client.common_lib import utils

class lockmeter(profiler.profiler):
    version = 1

# ftp://oss.sgi.com/projects/lockmeter/download/lockstat-1.4.11.tar.gz
# patched with lockstat.diff
# ftp://oss.sgi.com/projects/lockmeter/download/v2.6/patch.2.6.14-lockmeter-1.gz
# is the kernel patch

    def setup(self, tarball = 'lockstat-1.4.11.tar.bz2'):
        self.tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        autotest_utils.extract_tarball_to_dir(self.tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('make')
        self.cmd = self.srcdir + '/lockstat'


    def initialize(self):
        if not os.path.exists('/proc/lockmeter'):
            msg = ('Lockmeter is not compiled into your kernel'
                   'Please fix and try again')
            print msg
            raise AssertionError(msg)


    def start(self, test):
        utils.system(self.cmd + ' off')
        utils.system(self.cmd + ' reset')
        utils.system(self.cmd + ' on')


    def stop(self, test):
        utils.system(self.cmd + ' off')


    def report(self, test):
        args = ' -m ' + autotest_utils.get_systemmap()
        self.output = self.profdir + '/results/lockstat'
        utils.system(self.cmd + args + ' print > ' + self.output)
