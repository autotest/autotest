import shutil
from autotest_utils import *

class readprofile:
	version = 1

	def __init__(self, job):
		self.job = job

# http://www.kernel.org/pub/linux/utils/util-linux/util-linux-2.12r.tar.bz2
	def setup(self, tarball = 'util-linux-2.12r.tar.bz2'):
		try:
			system('grep -iq " profile=" /proc/cmdline')
		except:
			raise CmdError, 'readprofile not enabled'

		self.tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(self.tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('./configure')
		os.chdir('sys-utils')
		system('make readprofile')
		self.cmd = os.getcwd() + '/readprofile'


	def start(self):
		system(self.cmd + ' -r')


	def stop(self):
		# There's no real way to stop readprofile, so we stash the
		# raw data at this point instead. BAD EXAMPLE TO COPY! ;-)
		self.rawprofile = self.resultsdir + '/results/profile.raw'
		shutil.copyfile('/proc/profile', rawprofile)
		system('bzip2 ' + rawprofile)


	def report(self):
		args = ' -n'
		args = args + ' -m ' + get_systemmap()
		args = args + ' -r ' + self.rawprofile
		self.txtprofile = self.resultsdir + '/results/profile.text'
		system(self.cmd + args + ' | sort -nr > ' + self.txtprofile)

