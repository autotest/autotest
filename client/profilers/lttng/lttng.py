"""
lttng - a kernel tracing tool
"""
import os, shutil
from autotest_lib.client.bin import autotest_utils, profiler
from autotest_lib.client.common_lib import utils, error

class lttng(profiler.profiler):
    version = 1

    # http://ltt.polymtl.ca/lttng/ltt-control-0.51-12082008.tar.gz
    def setup(self, tarball='ltt-control-0.51-12082008.tar.gz'):
        self.tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        autotest_utils.extract_tarball_to_dir(self.tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('./configure')
        utils.system('make')


    def initialize(self):
        self.job.require_gcc()

        self.ltt_bindir = os.path.join(self.srcdir, 'lttctl')
        self.lttctl = os.path.join(self.ltt_bindir, 'lttctl')
        self.lttd = os.path.join(self.srcdir, 'lttd/lttd')
        self.armall = os.path.join(self.ltt_bindir, 'ltt-armall')
        self.mountpoint = '/mnt/debugfs'

        os.putenv('LTT_DAEMON', self.lttd)

        if not os.path.exists(self.mountpoint):
            os.mkdir(self.mountpoint)

        utils.system('mount -t debugfs debugfs ' + self.mountpoint,
                                                            ignore_status=True)
        utils.system('modprobe ltt-control')
        utils.system('modprobe ltt-statedump')
        # clean up from any tracing we left running
        utils.system(self.lttctl + ' -n test -R', ignore_status=True)

        utils.system(self.armall, ignore_status=True)


    def start(self, test):
        output = os.path.join(test.profdir, 'lttng')
        utils.system('%s -n test -d -l %s/ltt -t %s' % 
                                      (self.lttctl, self.mountpoint, output))


    def stop(self, test):
        utils.system(self.lttctl + ' -n test -R')
