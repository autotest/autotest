"""
readprofile - a tool to read kernel profiling information

The readprofile command uses the /proc/profile information to print ascii data
on standard output. The output is organized in three columns: the first is the
number of clock ticks, the second is the name of the C function in the kernel
where those many ticks occurred, and the third is the normalized `load' of the
procedure, calculated as a ratio between the number of ticks and the length of
the procedure. The output is filled with blanks to ease readability.
"""
import os, shutil
from autotest_lib.client.bin import utils, profiler
from autotest_lib.client.common_lib import error

class readprofile(profiler.profiler):
    version = 1

# http://www.kernel.org/pub/linux/utils/util-linux/util-linux-2.12r.tar.bz2
    def setup(self, tarball = 'util-linux-2.12r.tar.bz2'):
        self.tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(self.tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('./configure')
        os.chdir('sys-utils')
        utils.system('make readprofile')


    def initialize(self):
        self.job.require_gcc()

        try:
            utils.system('grep -iq " profile=" /proc/cmdline')
        except error.CmdError:
            raise error.AutotestError('readprofile not enabled')

        self.cmd = self.srcdir + '/sys-utils/readprofile'


    def start(self, test):
        utils.system(self.cmd + ' -r')


    def stop(self, test):
        # There's no real way to stop readprofile, so we stash the
        # raw data at this point instead. BAD EXAMPLE TO COPY! ;-)
        self.rawprofile = test.profdir + '/profile.raw'
        print "STOP"
        shutil.copyfile('/proc/profile', self.rawprofile)


    def report(self, test):
        args  = ' -n'
        args += ' -m ' + utils.get_systemmap()
        args += ' -p ' + self.rawprofile
        cmd = self.cmd + ' ' + args
        txtprofile = test.profdir + '/profile.text'
        utils.system(cmd + ' | sort -nr > ' + txtprofile)
        utils.system('bzip2 ' + self.rawprofile)
