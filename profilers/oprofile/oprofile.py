# Will need some libaries to compile. Do 'apt-get build-dep oprofile' 
import profiler, shutil
from autotest_utils import *

class oprofile(profiler.profiler):
	version = 2

# http://prdownloads.sourceforge.net/oprofile/oprofile-0.9.1.tar.gz
# http://free.linux.hp.com/~ahs3/autotest/cvs-update-20060901.patch.gz
	def setup(self, tarball = 'oprofile-0.9.1.tar.bz2'):
		self.tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(self.tarball, self.srcdir)
		os.chdir(self.srcdir)

		system('bzcat ../cvs-update-20060901.patch.bz2 | patch -p1')
		system('./configure --with-kernel-support --prefix=' + self.srcdir)
		system('make')
		system('make install')


	def initialize(self):
		# for now, we're just going to use the default event

#		arch = get_cpu_arch()
#		if (arch == 'i386'):
#			self.setup_i386()
#		else:
#			raise UnknownError, 'Architecture %s not supported by oprofile wrapper' % arch

		self.opreport = self.srcdir + '/bin/opreport'
		self.opcontrol = self.srcdir + '/bin/opcontrol'
		self.vmlinux = get_vmlinux()
		system(self.opcontrol + ' --setup --vmlinux=' + self.vmlinux)


	def start(self, test):
		# system(self.opcontrol + ' --shutdown')
		# system('rm -rf /var/lib/oprofile/samples/current')
		system(self.opcontrol + ' --reset')
		# if the lapic is not enabled, events won't work, so fall
		# back to timer mode if necessary. If that blows up too,
		# we'll still throw an exception
		try:
			system(self.opcontrol + ' --start ' + self.event)
		except:
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


	def setup_i386(self):
		self.event = '--event CPU_CLK_UNHALTED:100000'

