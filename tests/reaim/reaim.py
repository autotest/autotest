# Needs autoconf & automake & libtool to be installed. Ewwwwwwwwwwwwwwwwwwwwww
import test
from autotest_utils import *

class reaim(test.test):
	version = 1

	# http://prdownloads.sourceforge.net/re-aim-7/osdl-aim-7.0.1.13.tar.gz
	def setup(self, tarball = 'osdl-aim-7.0.1.13.tar.gz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('./bootstrap')
		system('./configure')
		system('make')
		
	def execute(self, iterations = 1, workfile = 'workfile.short', 
			start = '1', end = '10', increment = '2',
			tmpdir = None):
		if not tmpdir:
			tmpdir = self.tmpdir
		args = '-f ' + ' '.join((workfile,start,end,increment))
		for i in range(1, iterations+1):
			system(self.srcdir + '/reaim ' + args)

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			system(self.srcdir + '/reaim ' + args)
			profilers.stop(self)
			profilers.report(self)
