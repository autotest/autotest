import os
from autotest_utils import *
from error import *

class profilers:
	preserve_srcdir = False

	def __init__(self, job):
		self.job = job
		self.list = []
		self.profdir = job.autodir + '/profilers'
		self.tmpdir = job.tmpdir

	# add a profiler
	def add(self, profiler, *args):
		try:
			sys.path.insert(0, self.job.profdir + '/' + profiler)
			exec 'import ' + profiler
			exec 'newprofiler = %s.%s(self)' % (profiler, profiler)
		finally:
			sys.path.pop(0)
		newprofiler.name = profiler
		newprofiler.bindir = self.profdir + '/' + profiler
		newprofiler.srcdir = newprofiler.bindir + '/src'
		newprofiler.tmpdir = self.tmpdir + '/' + profiler
		update_version(newprofiler.srcdir, newprofiler.preserve_srcdir, newprofiler.version, newprofiler.setup)
		newprofiler.initialize(*args)
		self.list.append(newprofiler)


	# remove a profiler
	def delete(self, profiler):
		nukeme = None
		for p in self.list:
			if (p.name == profiler):
				nukeme = p
		self.list.remove(p)


	# are any profilers enabled ?
	def present(self):
		if self.list:
			return 1
		else:
			return 0


	# Start all enabled profilers
	def start(self, test):
		for p in self.list:
			p.start(test)


	# Stop all enabled profilers
	def stop(self, test):
		for p in self.list:
			p.stop(test)


	# Report on all enabled profilers
	def report(self, test):
		for p in self.list:
			p.report(test)

