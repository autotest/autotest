# Will need some libaries to compile. Do 'apt-get build-dep oprofile' 
import profiler, shutil
from autotest_utils import *

class oprofile(profiler.profiler):
	version = 5

# http://prdownloads.sourceforge.net/oprofile/oprofile-0.9.3.tar.gz
	def setup(self, tarball = 'oprofile-0.9.3.tar.bz2', local = False, *args, **dargs):
		if local:
			return
		self.tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(self.tarball, self.srcdir)
		os.chdir(self.srcdir)
		
		system('patch -p1 < %s' % (os.path.join(self.bindir, "oprofile-69455.patch"),))
		system('./configure --with-kernel-support --prefix=' + self.srcdir)
		system('make')
		system('make install')


	def initialize(self, vmlinux = None, events = [], others = None, local = False):
		if not vmlinux:
			self.vmlinux = get_vmlinux()
		else:
			self.vmlinux = vmlinux
		if not len(events):
			self.events = ['default']
		else:
			self.events = events
		self.others = others

		# If there is existing setup file, oprofile may fail to start with default parameters.
		if os.path.isfile('/root/.oprofile/daemonrc'):
			os.rename('/root/.oprofile/daemonrc', '/root/.oprofile/daemonrc.org')

		setup = ' --setup'
		if not self.vmlinux:
			setup += ' --no-vmlinux'
		else:
			setup += ' --vmlinux=%s' % self.vmlinux
		for e in self.events:
			setup += ' --event=%s' % e
		if self.others:
			setup += ' ' + self.others

		if local:
			self.opreport = '/usr/bin/opreport'
			self.opcontrol = '/usr/bin/opcontrol'
		else:
			self.opreport = self.srcdir + '/bin/opreport'
			self.opcontrol = self.srcdir + '/bin/opcontrol'
		
		system(self.opcontrol + setup)


	def start(self, test):
		system(self.opcontrol + ' --shutdown')
		system(self.opcontrol + ' --reset')
		system(self.opcontrol + ' --start')


	def stop(self, test):
		system(self.opcontrol + ' --stop')
		system(self.opcontrol + ' --dump')


	def report(self, test):
		# Output kernel per-symbol profile report
		reportfile = test.profdir + '/oprofile.kernel'
		if self.vmlinux:
			report = self.opreport + ' -l ' + self.vmlinux
			if os.path.exists(get_modules_dir()):
				report += ' -p ' + get_modules_dir()
			system(report + ' > ' + reportfile)
		else:
			system("echo 'no vmlinux found.' > %s" %reportfile)
		
		# output profile summary report
		reportfile = test.profdir + '/oprofile.user'
		system(self.opreport + ' --long-filenames ' + ' > ' + reportfile)

		system(self.opcontrol + ' --shutdown')


