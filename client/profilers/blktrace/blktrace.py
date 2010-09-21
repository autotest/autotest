"""
Autotest profiler for blktrace
blktrace - generate traces of the i/o traffic on block devices
"""
import os
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import profiler, utils


class blktrace(profiler.profiler):
    version = 2

    def initialize(self, **dargs):
        self.mountpoint = '/sys/kernel/debug'
        self.blktrace = os.path.join(self.srcdir, 'blktrace')
        self.blkparse = os.path.join(self.srcdir, 'blkparse')
        self.blktrace_job = None

        self.job.require_gcc()
        self.job.setup_dep(['libaio'])
        ldflags = '-L ' + self.job.autodir + '/deps/libaio/lib'
        cflags = '-I ' + self.job.autodir + '/deps/libaio/include'
        self.gcc_flags = ldflags + ' ' + cflags
        self.device = dargs.get('device', None)


    def setup(self, tarball='blktrace.tar.bz2', **dargs):
        # v1.0.1, pulled from git, 2009/06/10
        # commit 1e09f6e9012826fca69fa07222b7bc53c3e629ee
        self.tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(self.tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.make('"CFLAGS=' + self.gcc_flags + '"')


    def get_device(self, test):
        if getattr(test, 'device', None):
            device = test.device
        else:
            if self.device:
                device=self.device
            else:
                raise error.TestWarn('No device specified for blktrace')
        return device


    def start(self, test):
        result = utils.system("mount | grep '%s'" % self.mountpoint,
                              ignore_status=True)
        if result:
            utils.system('mount -t debugfs debugfs /sys/kernel/debug')
        device = self.get_device(test)
        self.blktrace_job = utils.BgJob('%s /dev/%s' % (self.blktrace, device))


    def stop(self, test):
        if self.blktrace_job is not None:
            utils.nuke_subprocess(self.blktrace_job.sp)
        self.blktrace_job = None


    def report(self, test):
        output_file = os.path.join(test.profdir, 'blktrace')
        if getattr(test, 'profile_tag', None):
            output_file += '.' + test.profile_tag
        device = self.get_device(test)
        utils.system('%s %s > %s' % (self.blkparse, device, output_file))
