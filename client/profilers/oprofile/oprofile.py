# Will need some libaries to compile. Do 'apt-get build-dep oprofile' 
import profiler, shutil
from autotest_utils import *

class oprofile(profiler.profiler):
	version = 5

# Notes on whether to use the local copy or the builtin from source:
# local = None
#      Try to use source copy if it works, else use local
# local = False
#	Force use of the source copy
# local = True
#	Force use of the local copy

# http://prdownloads.sourceforge.net/oprofile/oprofile-0.9.3.tar.gz
	def setup(self, tarball = 'oprofile-0.9.3.tar.bz2', local = None,
								*args, **dargs):
		if local == True:
			return

		try:
			self.tarball = unmap_url(self.bindir, tarball,
								self.tmpdir)
			extract_tarball_to_dir(self.tarball, self.srcdir)
			os.chdir(self.srcdir)
		
			patch = os.path.join(self.bindir,"oprofile-69455.patch")
			system('patch -p1 < %s' % patch)
			system('./configure --with-kernel-support --prefix=' + \
								self.srcdir)
			system('make')
			system('make install')
		except:
			# Build from source failed.
			# But maybe can still use the local copy
			if local == False or \
				not os.path.exists('/usr/bin/opcontrol') or \
				not os.path.exists('/usr/bin/opreport'):
				raise


	def initialize(self, vmlinux = None, events = [], others = None,
								local = None):
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

		src_opreport  = os.path.join(self.srcdir, '/bin/opreport')
		src_opcontrol = os.path.join(self.srcdir, '/bin/opcontrol')
		if local == False or (local == None and 
					os.path.exists(src_opreport) and 
					os.path.exists(src_opcontrol)):
			print "Using source-built copy of oprofile"
			self.opreport = src_opreport
			self.opcontrol = src_opcontrol
		else:
			print "Using machine local copy of oprofile"
			self.opreport = '/usr/bin/opreport'
			self.opcontrol = '/usr/bin/opcontrol'
		
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


