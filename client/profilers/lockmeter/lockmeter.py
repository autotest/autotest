# NOTE: if you get compile errors from config.h, referring you to a FAQ,
# you might need to do 'cat < /dev/null > /usr/include/linux/config.h'. 
# But read the FAQ first.
import profiler
from autotest_utils import *

class lockmeter(profiler.profiler):
	version = 1

# ftp://oss.sgi.com/projects/lockmeter/download/lockstat-1.4.11.tar.gz
# patched with lockstat.diff
# ftp://oss.sgi.com/projects/lockmeter/download/v2.6/patch.2.6.14-lockmeter-1.gz
# is the kernel patch

	def setup(self, tarball = 'lockstat-1.4.11.tar.bz2'):
		self.tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(self.tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('make')
		self.cmd = self.srcdir + '/lockstat'


	def initialize(self):
		try:
			assert os.path.exists('/proc/lockmeter')
		except:
			print 'Lockmeter is not compiled into your kernel'
			print 'Please fix and try again'
			raise AssertionError


	def start(self, test):
		system(self.cmd + ' off')
		system(self.cmd + ' reset')
		system(self.cmd + ' on')


	def stop(self, test):
		system(self.cmd + ' off')


	def report(self, test):
		args = ' -m ' + get_systemmap()
		self.output = self.resultsdir + '/results/lockstat'
		system(self.cmd + args + ' print > ' + self.output)

