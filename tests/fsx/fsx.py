# This requires aio headers to build.
# On ubuntu: "apt-get install libaio libaio-dev"

# NOTE - this should also have the ability to mount a filesystem, 
# run the tests, unmount it, then fsck the filesystem

import test
from autotest_utils import *

class fsx(test.test):
	version = 1

	# http://www.zip.com.au/~akpm/linux/patches/stuff/ext3-tools.tar.gz
	def setup(self, tarball = self.bindir + 'ext3-tools.tar.gz'):
		self.tarball = unmap_potential_url(tarball, self.tmpdir)
		extract_tarball_to_dir(self.tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('make fsx-linux')


	def execute(self, repeat = '100000'):
		args = '-N ' + repeat
		system(self.srcdir + '/fsx-linux ' + args)
