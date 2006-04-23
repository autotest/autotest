# This is rough pseudocode. IT WILL NOT WORK. BE NOT SUPRISED!

import os
from autotest_utils import *
from error import *

class profiler:
	list = []            # err, I think i can do that. maybe

	def add(self, profiler):
		sys.path.insert(0, job.profdir + '/' + profiler)
		exec 'import ' + profiler
		exec 'myprofiler = %s.%s(self)' % (profiler, profiler)
		myprofiler.name = profiler
		list.append(myprofiler)


	def del(self, profiler):
		nukeme = None
		for p in list:
			if (p.name == profiler):
				nukeme = i
		list.remove(i)


	def start(self):
		for p in list:
			p.start()


	def stop(self):
		for p in list:
			p.start()


	def report(self):
		for p in list:
			p.report()


