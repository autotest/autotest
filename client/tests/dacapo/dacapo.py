# Dacapo test suite wrapper
#
# This benchmark suite is intended as a tool for Java benchmarking by the 
# programming language, memory management and computer architecture communities.
# It consists of a set of open source, real world applications with non-trivial 
# memory loads. The suite is the culmination of over five years work at eight 
# institutions, as part of the DaCapo research project, which was funded by a 
# National Science Foundation ITR Grant, CCR-0085792.
#
import test
import os
import package
from autotest_utils import *
from test_config import config_loader

class dacapo(test.test):
	version = 1

	def set_java_environment(self, jvm, java_root):
		'''\
		Setup java environment variables (path and classpath in order to
		execute a specific jvm specified by the java_root variable. 
		java_root - Base of the java vm installation
		'''
		# Sun has changed the directory layout for java 6
		# (now there's no jre directory). Let's work around this...
		if jvm == 'sun16':
			self.java_home = java_root
		else:
			self.java_home = os.path.join(java_root, 'jre')
		self.java_bin = os.path.join(self.java_home, 'bin')
		self.java_lib =  os.path.join(self.java_home, 'lib')
		os.environ['JAVA_ROOT'] = java_root
		os.environ['JAVA_HOME'] = self.java_home
		os.environ['JRE_HOME'] = self.java_home
		os.environ['CLASSPATH'] = self.java_lib
		os.environ['JAVA_BINDIR'] = self.java_bin
		os.environ['PATH'] = self.java_bin + ':' + os.environ['PATH']


	def execute(self, test = 'antlr', cfg = 'dacapo.cfg', jvm = 'sun14'):
		# Load the test configuration file
		config_file = os.path.join(self.bindir, cfg)
		my_config = config_loader(filename = config_file)
		# Directory where we will cache the dacapo jar file
		# and the jvm package files
		self.cachedir = os.path.join(self.bindir, 'cache')
		system('mkdir -p ' + self.cachedir)

		# Get dacapo jar URL
		# (It's possible to override the default URL that points to the 
		# sourceforge repository)
		if my_config.get('dacapo', 'override_default_url') == 'no':
			self.dacapo_url = my_config.get('dacapo', 'tarball_url')
		else:
			self.dacapo_url = my_config.get('dacapo', 'tarball_url_alt')
		# We can cache the dacapo package file if we take some
		# precautions (checking md5 sum of the downloaded file)
		self.dacapo_md5 = my_config.get('dacapo', 'package_md5')
		self.dacapo_pkg = \
		unmap_url_cache(self.cachedir, self.dacapo_url, self.dacapo_md5)

		# Get jvm package URL
		self.jvm_pkg_url = my_config.get(jvm, 'jvm_pkg_url')
		# Let's cache the jvm package as well
		self.jvm_pkg_md5 = my_config.get(jvm, 'package_md5')
		self.jvm_pkg = \
		unmap_url_cache(self.cachedir, self.jvm_pkg_url, self.jvm_pkg_md5)

		# Install the jvm pakage
		package.install(self.jvm_pkg)

		# Basic Java environment variables setup
		self.java_root = my_config.get(jvm, 'java_root')
		self.set_java_environment(jvm, self.java_root)

		# If use_global is set to 'yes', then we want to use the global
		# setting instead of per test settings
		if my_config.get('global', 'use_global') == 'yes':
			self.iterations = my_config.get('global', 'iterations')
			self.workload = my_config.get('global', 'workload')
		else:
			self.iterations = my_config.get(test, 'iterations')
			self.workload = my_config.get(test, 'workload')

		self.verbose = '-v '
		self.workload = '-s %s ' % self.workload
		self.iterations = '-n %s ' % self.iterations
		self.scratch = '-scratch %s ' % os.path.join(self.resultsdir, test)
		# Compose the arguments string
		self.args = self.verbose + self.workload + self.scratch \
		+ self.iterations + test
		# Execute the actual test
		try:
			system('java -jar %s %s' % (self.dacapo_pkg, self.args))
		except:
			raise TestError, \
			'Test %s has failed, command line options "%s"' % (test, self.args)
