# This will need more work on the configuration stuff before it will function
import test
from autotest_utils import *

class lmbench(test.test):
	version = 1

	def setup(self, tarball = 'lmbench3.tar.gz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		# http://www.bitmover.com/lm/lmbench/lmbench3.tar.gz
		# + lmbench3.diff (removes Makefile references to bitkeeper)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('make')
		
	def execute(self, iterations = 1, mem = '', fastmem = 'NO', 
			slowfs = 'NO', disks = '', disks_desc = '', 
			mhz = '', remote = '', enough = '5000', sync_max = '1',
			fsdir = None, file = None):
		if not fsdir:
			fsdir = self.tmpdir
		if not file:
			file = self.tmpdir+'XXX'
		config = open(self.srcdir + '/scripts/config-run', 'w')
		config.write('MEM="' + mem + '"\n')
		config.write('FASTMEM="' + fastmem + '"\n')
		config.write('SLOWFS="' + slowfs + '"\n')
		config.write('DISKS="' + disks + '"\n')
		config.write('DISK_DESC="' + disks_desc + '"\n')
		config.write('MHZ="' + mhz + '"\n')
		config.write('REMOTE="' + remote + '"\n')
		config.write('ENOUGH="' + enough + '"\n')
		config.write('SYNC_MAX="' + sync_max + '"\n')
		config.write('FILE="' + file + '"\n')
		config.write('FSDIR="' + fsdir + '"\n')
		config.write('MAIL=no\n')
		config.close
		for i in range(1, iterations+1):
			system(self.srcdir + 'scripts/results')

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			system(self.srcdir + 'scripts/results')
			profilers.stop(self)
			profilers.report(self)
