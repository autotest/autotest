"""
Functions to handle software packages. The functions covered here aim to be 
generic, with implementations that deal with different package managers, such
as dpkg and rpm.
"""

__author__ = 'lucasmr@br.ibm.com (Lucas Meneghel Rodrigues)'

import os, os_dep, re
from common.error import *
from autotest_utils import *

def rpm_info(rpm_package):
	"""\
	Returns a dictionary with information about an RPM package file
	- type: Package management program that handles the file
	- system_support: If the package management program is installed on the
	system or not
	- source: If it is a source (True) our binary (False) package
	- version: The package version (or name), that is used to check against the
	package manager if the package is installed
	- arch: The architecture for which a binary package was built
	- installed: Whether the package is installed (True) on the system or not
	(False)
	
	Raises an exception if the package file is not an rpm file
	"""
	file_result = system_output('file ' + rpm_package)
	package_pattern = re.compile('RPM', re.IGNORECASE)
	result = re.search(package_pattern, file_result)
	if result:
		package_info = {}
		package_info['type'] = 'rpm'
		try:
			os_dep.command('rpm')
			# Build the command strings that will be used to get package info
			# s_cmd - Command to determine if package is a source package
			# a_cmd - Command to determine package architecture
			# v_cmd - Command to determine package version
			# i_cmd - Command to determiine if package is installed
			s_cmd = 'rpm -qp --qf %{SOURCE} ' + rpm_package + ' 2>/dev/null'
			a_cmd = 'rpm -qp --qf %{ARCH} ' + rpm_package + ' 2>/dev/null'
			v_cmd = 'rpm -qp ' + rpm_package + ' 2>/dev/null' 
			i_cmd = 'rpm -q ' + system_output(v_cmd) + ' 2>&1 >/dev/null' 

			package_info['system_support'] = True
			# Checking whether this is a source or src package
			source = system_output(s_cmd)
			if source == '(none)':
				package_info['source'] = False
			else:
				package_info['source'] = True
			package_info['version'] = system_output(v_cmd)
			package_info['arch'] = system_output(a_cmd)
			# Checking if package is installed
			try:
				system(i_cmd)
				package_info['installed'] = True
			except:
				package_info['installed'] = False

		except:
			package_info['system_support'] = False
			package_info['installed'] = False
			# File gives a wealth of information about rpm packages.
			# However, we can't trust all this info, as incorrectly
			# packaged rpms can report some wrong values.
			# It's better than nothing though :)
			if len(file_result.split(' ')) == 6:
				# Figure if package is a source package
				if file_result.split(' ')[3] == 'src':
					package_info['source'] = True
				elif file_result.split(' ')[3] == 'bin':
					package_info['source'] = False
				else:
					package_info['source'] = False
				# Get architecture
				package_info['arch'] = file_result.split(' ')[4]
				# Get version
				package_info['version'] = file_result.split(' ')[5]
			elif len(file_result.split(' ')) == 5:
				# Figure if package is a source package
				if file_result.split(' ')[3] == 'src':
					package_info['source'] = True
				elif file_result.split(' ')[3] == 'bin':
					package_info['source'] = False
				else:
					package_info['source'] = False
				# When the arch param is missing on file, we assume noarch
				package_info['arch'] = 'noarch'
				# Get version
				package_info['version'] = file_result.split(' ')[4]
			else:
				# If everything else fails...
				package_info['source'] =  False
				package_info['arch'] = 'Not Available'
				package_info['version'] = 'Not Available'
		return package_info

	else:
		raise PackageError('Package %s is not an RPM package.' % rpm_package)


def dpkg_info(dpkg_package):
	"""\
	Returns a dictionary with information about a dpkg package file
	- type: Package management program that handles the file
	- system_support: If the package management program is installed on the
	system or not
	- source: If it is a source (True) our binary (False) package
	- version: The package version (or name), that is used to check against the
	package manager if the package is installed
	- arch: The architecture for which a binary package was built
	- installed: Whether the package is installed (True) on the system or not
	(False)
	
	Raises an exception if the package file is not an dpkg file
	"""
	file_result = system_output('file ' + dpkg_package)
	package_pattern = re.compile('Debian', re.IGNORECASE)
	result = re.search(package_pattern, file_result)

	if result:
		package_info = {}
		package_info['type'] = 'dpkg'
		# There's no single debian source package as is the case
		# with RPM
		package_info['source'] = False
		try:
			os_dep.command('dpkg')
			# Build the command strings that will be used to get package info
			# a_cmd - Command to determine package architecture
			# v_cmd - Command to determine package version
			# i_cmd - Command to determiine if package is installed
			a_cmd = 'dpkg -f ' + dpkg_package + ' Architecture 2>/dev/null'
			v_cmd = 'dpkg -f ' + dpkg_package + ' Package 2>/dev/null'
			i_cmd = 'dpkg -s ' + system_output(v_cmd) + ' 2>/dev/null'

			package_info['system_support'] = True
			package_info['version'] = system_output(v_cmd)
			package_info['arch'] = system_output(a_cmd)
			# Checking if package is installed
			package_status = system_output(i_cmd)
			not_inst_pattern = re.compile('not-installed', re.IGNORECASE)
			dpkg_not_installed = re.search(not_inst_pattern, package_status)
			if dpkg_not_installed:
				package_info['installed'] = False
			else:
				package_info['installed'] = True

		except:
			package_info['system_support'] = False
			package_info['installed'] = False
			# The output of file is not as generous for dpkg files as
			# it is with rpm files
			package_info['arch'] = 'Not Available'
			package_info['version'] = 'Not Available'

		return package_info
	else:
		raise PackageError('Package %s is not a dpkg package.' % dpkg_package)


def info(package):
	"""\
	Returns a dictionary with package information about a given package file:
	- type: Package management program that handles the file
	- system_support: If the package management program is installed on the
	system or not
	- source: If it is a source (True) our binary (False) package
	- version: The package version (or name), that is used to check against the
	package manager if the package is installed
	- arch: The architecture for which a binary package was built
	- installed: Whether the package is installed (True) on the system or not
	(False)

	Implemented package types:
	- 'dpkg' - dpkg (debian, ubuntu) package files
	- 'rpm' - rpm (red hat, suse) package files
	Raises an exception if the package type is not one of the implemented
	package types.
	"""
	if not os.path.isfile(package):
		raise ValueError('invalid file %s to verify' % package)
	# Use file and libmagic to determine the actual package file type.
	file_result = system_output('file ' + package)
	known_package_managers = ['rpm', 'dpkg']
	for package_manager in known_package_managers:
		if package_manager == 'rpm':
			package_pattern = re.compile('RPM', re.IGNORECASE)
		elif package_manager == 'dpkg':
			package_pattern = re.compile('Debian', re.IGNORECASE)

		result = re.search(package_pattern, file_result)

		if result and package_manager == 'rpm':
			return rpm_info(package)
		elif result and package_manager == 'dpkg':
			return dpkg_info(package)

	# If it's not one of the implemented package manager methods, there's
	# not much that can be done, hence we throw an exception.
	raise PackageError('Unknown package type %s' % file_result)


def install(package):
	"""\
	Tries to install a package file. If the package is already installed,
	it prints a message to the user and ends gracefully.
	"""
	my_package_info = info(package)
	type = my_package_info['type']
	system_support = my_package_info['system_support']
	source = my_package_info['source']
	installed = my_package_info['installed']

	if type == 'rpm' and system_support:
		install_command = 'rpm -U ' + package
	if type == 'dpkg' and system_support:
		install_command = 'dpkg -i ' + package

	# RPM source packages can be installed along with the binary versions
	# with this check
	if installed and not source:
		return 'Package %s is already installed' % package

	# At this point, the most likely thing to go wrong is that there are 
	# unmet dependencies for the package. We won't cover this case, at 
	# least for now.
	system(install_command)
	return 'Package %s was installed successfuly' % package
