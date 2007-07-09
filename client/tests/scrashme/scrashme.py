import test
from autotest_utils import *

class scrashme(test.test):
	version = 1

	# http://www.codemonkey.org.uk/projects/git-snapshots/scrashme/scrashme-2007-07-08.tar.gz
	def setup(self, tarball = 'scrashme-2007-07-08.tar.gz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('make')
		
	def execute(self, iterations = 1, args_list = ''):
		if len(args_list) != 0:
			args = '' + args_list
		else:
			args = '-c100 -z'

		profilers = self.job.profilers
		if not profilers.only():
			for i in range(iterations):
				system(self.srcdir + '/scrashme ' + args)

		# Do a profiling run if necessary
		if profilers.present():
			profilers.start(self)
			system(self.srcdir + '/scrashme ' + args)
			profilers.stop(self)
			profilers.report(self)
