import test, time
from autotest_utils import *

class cpu_hotplug(test.test):
	version = 1

	# http://developer.osdl.org/dev/hotplug/tests/lhcs_regression-1.4.tgz
	def setup(self, tarball = 'lhcs_regression-1.4.tgz'):
		tarball = unmap_url(self.bindir, tarball, self.tmpdir)
		extract_tarball_to_dir(tarball, self.srcdir)
		
	def execute(self):
		# Check if kernel support cpu hotplug
		if os.path.isfile('/proc/config.gz'):
			hotplug = system_output('zcat /proc/config.gz | grep CONFIG_HOTPLUG_CPU=y')
			if not len(hotplug):
				print 'Kernel does not support cpu hotplug, quiting...'
				sys.exit()
		else:
			kernel_version = system_output('uname -r')
			config = '/boot/config-%s' %kernel_version
			if os.path.isfile(config):
				if not file_contains_pattern(config, 'CONFIG_HOTPLUG_CPU=y'):
					print 'Kernel does not support cpu hotplug, quiting...'
                                	sys.exit()
		
		# Check cpu nums, if equals 1, quit.
		if count_cpus() == 1:
			print 'Just only single cpu online, quiting...'
			sys.exit()
		
		# Check out the available cpu online map
		cpus = system_output("cat /proc/cpuinfo | grep processor | awk -F' ' '{print $3}'")
		cpu_online_map = cpus.splitlines()

		# Have a simple and quick check first, FIX me please.
		system('dmesg -c > /dev/null')
		for c in cpu_online_map:
			if os.path.isfile('/sys/devices/system/cpu/cpu%s/online' %c):
				system('echo 0 > /sys/devices/system/cpu/cpu%s/online' %c, 1)
				system('dmesg -c')
				time.sleep(3)
				system('echo 1 > /sys/devices/system/cpu/cpu%s/online' %c, 1)
				system('dmesg -c')
				time.sleep(3)
		
		# Begin this cpu hotplug test big guru.
		os.chdir(self.srcdir)
		system('./runtests.sh')

		# Do a profiling run if necessary
		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
			system('./runtests.sh')
			profilers.stop(self)
			profilers.report(self)
