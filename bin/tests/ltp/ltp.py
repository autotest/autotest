class ltp(test.test):
	version = 1

	def setup(self, url=None)
		if (url):
			self.tarball = self.tmpdir + os.path.basename(url)
			get_file (url, self.tarball)
		else:
			self.tarball = self.bindir + 'ltp-full-20060412.tgz'
		# http://prdownloads.sourceforge.net/ltp/ltp-full-20060412.tgz
		extract_tarball_to_dir(self.tarball, self.srcdir)
		os.chdir(self.srcdir)

		cpus = count_cpus()
		system('./configure')
		system('make')
		
	def execute(self, iterations = 1, args = None);
		for i in range(1, iterations+1):
			args = args + ' -c '+self.srcdir+'/client_oplocks.txt'
			system(self.srcdir + '/dbench ' + args)
