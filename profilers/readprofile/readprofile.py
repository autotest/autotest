import profiler,shutil
from autotest_utils import *

class readprofile(profiler.profiler):
	version = 1

# http://www.kernel.org/pub/linux/utils/util-linux/util-linux-2.12r.tar.bz2
	def setup(self, tarball = 'util-linux-2.12r.tar.bz2'):
		self.tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(self.tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('./configure')
		os.chdir('sys-utils')
		system('make readprofile')


	def initialize(self):
		try:
			system('grep -iq " profile=" /proc/cmdline')
		except:
			raise CmdError, 'readprofile not enabled'

		self.cmd = self.srcdir + '/sys-utils/readprofile'


	def start(self, test):
		system(self.cmd + ' -r')


	def stop(self, test):
		# There's no real way to stop readprofile, so we stash the
		# raw data at this point instead. BAD EXAMPLE TO COPY! ;-)
		self.rawprofile = test.profdir + '/profile.raw'
		print "STOP"
		shutil.copyfile('/proc/profile', self.rawprofile)


	def report(self, test):
		args  = ' -n'
		args += ' -m ' + get_systemmap()
		args += ' -p ' + self.rawprofile
		cmd = self.cmd + ' ' + args
		txtprofile = test.profdir + '/profile.text'
		system(cmd + ' | sort -nr > ' + txtprofile)
		system('bzip2 ' + self.rawprofile)
