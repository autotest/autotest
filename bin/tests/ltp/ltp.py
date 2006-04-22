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
		system('make -j' + cpus)
		system('make install')
		
	def execute(self, args = None);
		logfile = self.resultsdir + '/ltp.log'
		args = '-q -l ' + logfile + ' ' + args
		system(self.srcdir + './runalltests.sh ' + args)
