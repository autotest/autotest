import test, os_dep
from autotest_utils import *

class isic(test.test):
	version = 1

	# http://www.packetfactory.net/Projects/ISIC/isic-0.06.tgz
	# + http://www.stardust.webpages.pl/files/crap/isic-gcc41-fix.patch

	def setup(self, tarball = 'isic-0.06.tar.bz2'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		os_dep.library('libnet.so')
		system('./configure')
		system('make')

	def execute(self, args = '-s rand -d 127.0.0.1 -p 10000000'):
		system(self.srcdir + '/isic ' + args)
