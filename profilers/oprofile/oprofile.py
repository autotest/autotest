# Will need some libaries to compile. Do 'apt-get build-dep oprofile' 
import profiler, shutil
from autotest_utils import *

class oprofile(profiler.profiler):
	version = 1

	def __init__(self, job):
		self.job = job

# http://prdownloads.sourceforge.net/oprofile/oprofile-0.9.1.tar.gz
	def setup(self, tarball = 'oprofile-0.9.1.tar.bz2'):
		self.tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(self.tarball, self.srcdir)
		os.chdir(self.srcdir)

		pwd = os.getcwd()
		system('./configure --with-kernel-support --prefix=' + pwd)
		system('make')
		system('make install')


	def initialize():
		arch = get_arch()
		if (arch == 'i386'):
			self.setup_i386()
		else:
			raise UnknownError, 'Architecture %s not supported by oprofile wrapper' % arch

		self.opreport = self.srcdir + '/pp/opcontrol'
		self.opcontrol = self.srcdir + '/utils/opcontrol'


	def start(self, test):
		vmlinux = '--vmlinux=' + get_vmlinux()
		system(self.opcontrol + ' --shutdown')
		system('rm -rf /var/lib/oprofile/samples/current')
		system(''.join(self.opcontrol, vmlinux, self.args, '--start'))
		system(self.opcontrol + ' --reset')


	def stop(self, test):
		system(self.opcontrol + ' --dump')


	def report(self, test):
		reportfile = self.resultsdir + '/results/oprofile.txt'
		modules = ' -p ' + get_modules_dir()
		system(self.opreport + ' -l ' + modules + ' > ' + reportfile)
		system(self.opcontrol + ' --shutdown')


	def setup_i386(self):
		self.args = '-e CPU_CLK_UNHALTED:100000'

