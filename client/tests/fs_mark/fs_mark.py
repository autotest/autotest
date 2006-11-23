import test
from autotest_utils import *

class fs_mark(test.test):
	version = 1

	# http://developer.osdl.org/dev/doubt/fs_mark/archive/fs_mark-3.2.tgz
	def setup(self, tarball = 'fs_mark-3.2.tgz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('make')
		
	def execute(self, dir, iterations = 2, args = None):
		os.chdir(self.srcdir)
		if not args:
			# Just provide a sample run parameters
			args = '-s 10240 -n 1000'
		for i in range(1, iterations+1):
			system('./fs_mark -d %s %s' %(dir, args))

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			system('./fs_mark -d %s %s' %(dir, args))
			profilers.stop(self)
			profilers.report(self)
