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


	def execute(self, dir = None, iterations=1, args = None):
		self.keyval = open(os.path.join(self.resultsdir, 'keyval'),
		                   'w')
		if not dir:
			dir = self.tmpdir
		os.chdir(dir)
		if not args:
			args = '-a'
		profilers = self.job.profilers
		if not profilers.only():
			for i in range(iterations):
				output = system_output('%s/src/current/iozone %s' %
				                       (self.srcdir, args))
				self.__format_results(output)

		# Do a profiling run if necessary
		if profilers.present():
			profilers.start(self)
			output = system_output('%s/src/current/iozone %s' %
			                       (self.srcdir, args))
			self.__format_results(output)
			profilers.stop(self)
			profilers.report(self)

		self.keyval.close()


	def __format_results(self, results):
		labels = ('write', 'rewrite', 'read', 'reread', 'randread',
			  'randwrite', 'bkwdread', 'recordrewrite',
			  'strideread', 'fwrite', 'frewrite',
			  'fread', 'freread')
		for line in results.splitlines():
			fields = line.split()
			if len(fields) != 15:
				continue
			try:
				fields = tuple([int(i) for i in fields])
			except ValueError:
				continue
			for l, v in zip(labels, fields[2:]):
				print >> self.keyval, "%d-%d-%s=%d" % (fields[0], fields[1], l, v)
		print >> self.keyval
