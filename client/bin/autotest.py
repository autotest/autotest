import os, sys

class system:
	def __init__(self):
		self.autodir = os.environ['AUTODIR']
		self.resultdir = self.autodir + '/results'
		self.tmpdir = self.autodir + '/tmp'

		if not os.path.isdir(self.resultdir):
			os.mkdir(self.resultdir)
		if not os.path.isdir(self.tmpdir):
			os.mkdir(self.tmpdir)
		return None


	def boot(self, tag=None):
		print "I OUGHT TO REBOOT NOW!"
