from autotest_utils import *
import os,sys,kernel,test

class job:
	def __init__(self, jobtag='default'):
		self.autodir = os.environ['AUTODIR']
		self.tmpdir = self.autodir + '/tmp'
		self.resultdir = self.autodir + '/results' + jobtag
		if os.path.exists(self.resultdir):
			os.system('rm -rf ' + self.resultdir)
		os.mkdir(self.resultdir)
		os.mkdir(self.resultdir + "/debug")
		os.mkdir(self.resultdir + "/analysis")
		
		self.jobtab = jobtag

		self.stdout = fd_stack(1, sys.stdout)
		self.stderr = fd_stack(2, sys.stderr)

	def kernel(self, topdir, base_tree):
		return kernel.kernel(self, topdir, base_tree)


	def runtest(self, tag, testname, test_args):
		mytest = test.test(self, testname + '.' + tag)
		mytest.run(testname, test_args)
