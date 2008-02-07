# Wrapper to LSB testsuite
# Copyright 2008, IBM Corp.
import test
import os
import package
from autotest_utils import *
from test_config import config_loader

__author__ = '''
pnaregun@in.ibm.com (Pavan Naregundi)
lucasmr@br.ibm.com (Lucas Meneghel Rodrigues)
'''

class lsb_dtk(test.test):
	version = 1
	def get_lsb_arch(self):
		self.arch = get_current_kernel_arch()
		if self.arch in ['i386', 'i486', 'i586', 'i686', 'athlon']:
			return 'ia32'
		elif self.arch == 'ppc':
			return 'ppc32'
		elif self.arch in ['s390', 's390x', 'ia64', 'x86_64', 'ppc64']:
			return self.arch
		else:
			e_msg = 'Architecture %s not supported by lsb' % self.arch
			raise TestError(e_msg)


	def link_lsb_libraries(self, config):
		self.libdir_key = 'libdir-%s' % self.arch
		self.os_libdir = config.get('lsb', self.libdir_key)
		if not self.os_libdir:
			raise TypeError('Could not find OS lib dir from conf file')
		self.lib_key = 'lib-%s' % self.arch
		self.lib_list_raw = config.get('lsb', self.lib_key)
		if not self.lib_list_raw:
			raise TypeError('Could not find library list from conf file')
		self.lib_list = eval(self.lib_list_raw)
		print self.lib_list

		system_output('rm -f %s/ld-lsb*.so.* | tail -1' % self.os_libdir)
		self.baselib_path = system_output('ls %s/ld-2*.so | tail -1' % self.os_libdir)

		for self.lib in self.lib_list:
			self.lib_path = os.path.join(self.os_libdir, self.lib)
			os.symlink(self.baselib_path, self.lib_path)


	def install_lsb_packages(self, lsb_pkg_path):
		if not os.path.isdir(lsb_pkg_path):
			raise IOError('Invalid lsb packages path %s' % lsb_pkg_path)
		# Try to find the inst_config, that contains LSB rpm name info.
		os.chdir(lsb_pkg_path)
		if not os.path.isfile('inst-config'):
			raise IOError('Could not find file with package info, inst-config')
		# Let's assemble the rpm list
		self.rpm_file_list = open('inst-config', 'r')
		self.pkg_pattern = re.compile('[A-Za-z0-9_.-]*[.][r][p][m]')
		self.lsb_pkg_list = []
		for self.line in self.rpm_file_list.readlines():
			try:
				self.line = re.findall(self.pkg_pattern, self.line)[0]
				print self.line
				self.lsb_pkg_list.append(self.line)
			except:
				# If we don't get a mach, no problem...
				pass

		os_pkg_support = package.os_support()
		if os.path.isfile('/etc/debian_version') and os_pkg_support['dpkg']:
			print 'Debian based distro detected'
			if os_pkg_support['conversion']:
				print 'Package conversion supported'
				self.os_type = 'debian-based'
			else:
				raise EnvironmentError('Package conversion not supported')
		elif os_pkg_support['rpm']:
			print 'Red Hat based distro detected'
			self.os_type = 'redhat-based'
		else:
			print 'OS does not seem to be red hat or debian based'
			e_msg = 'Cannot handle lsb package installation'
			raise EnvironmentError(e_msg)

		for self.lsb_rpm in self.lsb_pkg_list:
			if self.os_type == 'redhat-based':
				package.install(self.lsb_rpm, nodeps = True)
			elif self.os_type == 'debian-based':
				self.lsb_dpkg = package.convert(self.lsb_rpm, 'dpkg')
				package.install(self.lsb_dpkg, nodeps = True)


	def execute(self, args = '', cfg = 'lsb31.cfg'):
		# Load the test configuration file
		config_file = os.path.join(self.bindir, cfg)
		my_config = config_loader(filename = config_file)
		# Directory where we will cache the lsb-dtk tarball
		self.cachedir = os.path.join(self.bindir, 'cache')
		system('mkdir -p ' + self.cachedir)

		# Get lsb-dtk URL
		# The conf file stores an URL that is assembled depending on the
		# host architecture at runtime
		self.arch = self.get_lsb_arch()
		print self.arch
		if my_config.get('lsb', 'override_default_url') == 'no':
			self.lsb_url = my_config.get('lsb', 'tarball_url') % self.arch
		else:
			self.lsb_url = my_config.get('lsb', 'tarball_url_alt') % self.arch
		# The LSB tarball is HUGE (~100MB). It's better to cache it.
		# Compose the md5 key name
		self.md5_key = 'md5-%s' % self.arch
		# Try to retrieve info using this key
		self.lsb_md5 = my_config.get('lsb', self.md5_key)
		# If we don't have an md5, we can't safely cache the tarball
		if self.lsb_md5:
			self.lsb_pkg = \
			unmap_url_cache(self.cachedir, self.lsb_url, self.lsb_md5)
		else:
			self.lsb_pkg = unmap_url(self.bindir, self.lsb_url, self.tmpdir)

		extract_tarball_to_dir(self.lsb_pkg, self.srcdir)
		self.install_lsb_packages(self.srcdir)
		self.link_lsb_libraries(my_config)

		self.main_script_path = my_config.get('lsb', 'main_script_path')
		logfile = os.path.join(self.resultsdir, 'lsb.log')
		args2 = '-r %s' % (logfile)
		args = args + ' ' + args2
		cmd = os.path.join(self.srcdir, self.main_script_path) + ' ' + args

		profilers = self.job.profilers
		if profilers.present():
			profilers.start(self)
		system(cmd)
		if profilers.present():
			profilers.stop(self)
			profilers.report(self)
