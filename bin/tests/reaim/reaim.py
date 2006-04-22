class reaim(test.test):
	version = 1

	# http://prdownloads.sourceforge.net/re-aim-7/osdl-aim-7.0.1.13.tar.gz
	def setup(self, tarball = self.bindir+'osdl-aim-7.0.1.13.tar.gz')
		self.tarball = unmap_potential_url(tarball, self.tmpdir)
		extract_tarball_to_dir(self.tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('./bootstrap')
		system('./configure')
		system('make')
		
	def execute(self, workfile = 'workfile.short', 
			start = '1', end = '10', increment = '2',
			testdir = self.tmpdir)
		args = '-f ' + ' '.join(workfile.short,start,end,increment)
		system(self.srcdir + './reaim ' + args)
