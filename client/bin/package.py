"""
Functions to handle software packages. The functions covered here aim to be 
generic, with implementations that deal with different package managers, such
as dpkg and rpm.
"""

__author__ = 'lucasmr@br.ibm.com (Lucas Meneghel Rodrigues)'

import os, os_dep, re
from common.error import *
from autotest_utils import *

def type(package):
	"""\
	Returns the package type (if any) of a given file.
	Implemented package types:
	- 'dpkg' - dpkg (debian, ubuntu) package files
	- 'rpm' - rpm (red hat, suse) package files
	Raises an exception if the package type is not one of the implemented
	package types.
	"""
	if not os.path.isfile(package):
		raise ValueError, 'invalid file %s to verify' % package
	# Use file and libmagic to determine the actual package file type.
	file_result = system_output('file ' + package)
	known_package_managers = ['rpm', 'dpkg']
	for package_manager in known_package_managers:
		if package_manager == 'rpm':
			package_pattern = 'RPM'
		elif package_manager == 'dpkg':
			package_pattern = 'Debian'

		result = re.search(package_pattern, file_result, re.IGNORECASE)
		if result:
			return package_manager
	# If it's not one of the implemented package manager methods, there's
	# not much that can be done, hence we throw an exception.
	raise PackageError, 'Unknown package type %s' % file_result


def version(package):
	"""Returns the version string for a package file."""
	my_package_type = package_type(package)

	if my_package_type == 'rpm' and os_dep.command('rpm'):
		return system_output('rpm -qp ' + package)
	elif my_package_type == 'dpkg' and os_dep.command('dpkg'):
		return system_output('dpkg -f %s Package' % package)


def installed(package):
	"""Returns whether a given package is installed in the system"""
	my_package_type = package_type(package)

	if my_package_type == 'rpm' and os_dep.command('rpm'):
		try:
			my_package_version = package_version(package)
			system('rpm -q ' + my_package_version)
		except:
			return False
		return True
	elif my_package_type == 'dpkg' and os_dep.command('dpkg'):
		my_package_version = package_version(package)
		status = \
		system_output('dpkg -s %s | grep Status' % my_package_version)
		result = re.search('not-installed', status, re.IGNORECASE)
		if result:
			return False
		return True

	return False


def install(package):
	"""\
	Tries to install a package file. If the package is already installed,
	it prints a message to the user and ends gracefully.
	"""
	my_package_type = package_type(package)

	if my_package_type == 'rpm' and os_dep.command('rpm'):
		install_command = 'rpm -Uvh ' + package
	elif my_package_type == 'dpkg' and os_dep.command('dpkg'):
		install_command = 'dpkg -i ' + package

	if package_installed(package):
		return 'Package %s is already installed' % package

	# At this point, the most likely thing to go wrong is that there are 
	# unmet dependencies for the package. We won't cover this case, at 
	# least for now.
	system(install_command)
	return 'Package %s was installed successfuly' % package
