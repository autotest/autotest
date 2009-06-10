import os
from autotest_lib.client.bin import profiler, utils


class blktrace(profiler.profiler):
    version = 1

    def initialize(self, disk):
        self.mountpoint = '/sys/kernel/debug'
        self.disk = disk
        self.blktrace = os.path.join(self.srcdir, 'blktrace')
        self.blkparse = os.path.join(self.srcdir, 'blkparse')
        self.blktrace_job = None

        self.job.require_gcc()
        self.job.setup_dep(['libaio'])
        ldflags = '-L ' + self.job.autodir + '/deps/libaio/lib'
        cflags = '-I ' + self.job.autodir + '/deps/libaio/include'
        self.gcc_flags = ldflags + ' ' + cflags


    def setup(self, tarball='blktrace.tar.bz2', **dargs):
        self.tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(self.tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.system('make ' + '"CFLAGS=' + self.gcc_flags + '"')


    def start(self, test):
        result = utils.system("mount | grep '%s'" % self.mountpoint,
                              ignore_status=True)
        if result:
            utils.system('mount -t debugfs debugfs /sys/kernel/debug')
        if getattr(test, 'disk', None):
            disk = test.disk
        else:
            disk = self.disk
        self.blktrace_job = utils.BgJob('%s /dev/%s' % (self.blktrace, disk))


    def stop(self, test):
        if self.blktrace_job is not None:
            utils.nuke_subprocess(self.blktrace.sp)
        self.blktrace_job = None


    def report(self, test):
        output_file = os.path.join(test.profdir, 'blktrace')
        if getattr(test, 'profile_tag', None):
            output_file += '.' + test.profile_tag
        utils.system('%s %s > %s' % (self.blkparse, self.disk, output_file))
