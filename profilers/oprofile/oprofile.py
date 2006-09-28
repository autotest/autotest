# Will need some libaries to compile. Do 'apt-get build-dep oprofile' 
import profiler, shutil
from autotest_utils import *

class oprofile(profiler.profiler):
	version = 3

# http://prdownloads.sourceforge.net/oprofile/oprofile-0.9.2.tar.gz
	def setup(self, tarball = 'oprofile-0.9.2.tar.bz2'):
		self.tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(self.tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('./configure --with-kernel-support --prefix=' + self.srcdir)
		system('make')
		system('make install')


	def initialize(self, event = None):
		self.event = event
		self.opreport = self.srcdir + '/bin/opreport'
		self.opcontrol = self.srcdir + '/bin/opcontrol'
		self.vmlinux = get_vmlinux()
		system(self.opcontrol + ' --setup --vmlinux=' + self.vmlinux)


	def start(self, test):
		system(self.opcontrol + ' --reset')
		if (self.event):
			system(self.opcontrol + ' --start --event ' +self.event)
		else:
			system(self.opcontrol + ' --start')


	def stop(self, test):
		system(self.opcontrol + ' --stop')
		system(self.opcontrol + ' --dump')


	def report(self, test):
		reportfile = test.profdir + '/oprofile.kernel'
		report = self.opreport + ' -l ' + self.vmlinux
		if os.path.exists(get_modules_dir()):
			report += ' -p ' + get_modules_dir()
		system(report + ' > ' + reportfile)

		reportfile = test.profdir + '/oprofile.user'
		system(self.opreport + ' > ' + reportfile)

		system(self.opcontrol + ' --shutdown')


