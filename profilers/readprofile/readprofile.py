import shutil

class readprofile(profiler.profiler):
	version = 1

# http://www.kernel.org/pub/linux/utils/util-linux/util-linux-2.12r.tar.bz2
	def setup(self, tarball = self.bindir + 'util-linux-2.12r.tar.bz2'):
		system('grep -iq " profile=" /proc/cmdline')

		self.tarball = unmap_potential_url(tarball, self.tmpdir)
		extract_tarball_to_dir(self.tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('./configure')
		os.chdir('sys-utils')
		system('make readprofile')
		self.cmd = os.getcwd() + '/readprofile'


	def start(self):
		system(self.cmd + ' -r')


	def stop(self):
		self.rawprofile = self.resultsdir + '/results/profile.raw'
		shutil.copyfile('/proc/profile', rawprofile)
		system('bzip2 ' + rawprofile)


	def report(self):
		args = ' -n'
		args = args + ' -m /boot/System.map'
		args = args + ' -r ' + self.rawprofile
		self.txtprofile = self.resultsdir + '/results/profile.text'
		system(self.cmd + args + ' | sort -nr > ' + self.txtprofile)

