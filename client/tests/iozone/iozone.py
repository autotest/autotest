#!/usr/bin/python

import test
from autotest_utils import *

class iozone(test.test):
	version = 1

	# http://www.iozone.org/src/current/iozone3_283.tar
	def setup(self, tarball = 'iozone3_283.tar'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		os.chdir(os.path.join(self.srcdir, 'src/current'))

		arch = get_current_kernel_arch()
		if (arch == 'ppc'):
			system('make linux-powerpc')
		elif (arch == 'ppc64'):
			system('make linux-powerpc64')
		elif (arch == 'x86_64'):
			system('make linux-AMD64')
		else: 
			system('make linux')

	def execute(self, dir, args = None):
		os.chdir(dir)
		if not args:
			args = '-a'
		profilers = self.job.profilers
		if not profilers.only():
			system('%s/src/current/iozone %s' % (self.srcdir, args))

		# Do a profiling run if necessary
		if profilers.present():
			profilers.start(self)
			system('%s/src/current/iozone %s' % (self.srcdir, args))
			profilers.stop(self)
			profilers.report(self)
