# This is rough pseudocode. IT WILL NOT WORK. BE NOT SUPRISED!

import os
from autotest_utils import *
from error import *

class profiler:
	def __init__(self, job):
		self.job = job
		self.list = []
		self.profdir = job.autodir + '/profilers'
		self.tmpdir = job.tmpdir

	def add(self, profiler):
		sys.path.insert(0, self.job.profdir + '/' + profiler)
		exec 'import ' + profiler
		exec 'newprofiler = %s.%s(self)' % (profiler, profiler)
		newprofiler.name = profiler
		newprofiler.bindir = self.profdir + '/' + profiler
		newprofiler.srcdir = newprofiler.bindir + '/src'
		newprofiler.tmpdir = self.tmpdir + '/' + profiler
		newprofiler.setup()
		self.list.append(newprofiler)


	def delete(self, profiler):
		nukeme = None
		for p in self.list:
			if (p.name == profiler):
				nukeme = i
		self.list.remove(i)


	def start(self):
		for p in self.list:
			p.start()


	def stop(self):
		for p in self.list:
			p.start()


	def report(self):
		for p in self.list:
			p.report()


