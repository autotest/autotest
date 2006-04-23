# This will need more work on the configuration stuff before it will function
import test
from autotest_utils import *

class lmbench(test.test):
	version = 1

	def setup(self):
		self.tarball = self.bindir + 'lmbench3.tar.gz'
		# http://www.bitmover.com/lm/lmbench/lmbench3.tar.gz
		# + lmbench3.diff (removes Makefile references to bitkeeper)
		extract_tarball_to_dir(self.tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('make')
		
	def execute(self, iterations = 1, mem = None, fastmem = 'NO', 
			slowfs = 'NO', disks = None, disks_desc = None, 
			mhz = None, remote = None, 
			enough = '5000', sync_max = '1',
			fsdir = self.tmpdir, file = self.tmpdir+'XXX')
		config = open(self.srcdir + 'scripts/config-run', 'w')
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
