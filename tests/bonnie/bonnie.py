class bonnie(test.test):
	version = 1

	def setup(self):
		self.tarball = self.bindir + 'bonnie++-1.03a.tgz'
		# http://www.coker.com.au/bonnie++/bonnie++-1.03a.tgz
		extract_tarball_to_dir(self.tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('./configure')
		system('make')
		
	def execute(self, iterations = 1, extra_args = None, user = 'root'):
		args = '-d ' + self.tmp_dir + ' -u ' + user + ' ' + extra_args

		for i in range(1, iterations+1):
			system(self.srcdir + '/bonnie++ ' + args)
