class ltp(test.test):
	version = 1

	# http://prdownloads.sourceforge.net/ltp/ltp-full-20060412.tgz
	def setup(self, tarball = self.bindir+'ltp-full-20060412.tgz');
		self.tarball = unmap_potential_url(tarball, self.tmpdir)
		extract_tarball_to_dir(self.tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('make -j' + count_cpus())
		system('make install')
		
	def execute(self, args = None);
		logfile = self.resultsdir + '/ltp.log'
		args = '-q -l ' + logfile + ' ' + args
		system(self.srcdir + './runalltests.sh ' + args)
