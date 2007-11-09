"""
Functions to handle software packages. The functions covered here aim to be 
generic, with implementations that deal with different package managers, such
as dpkg and rpm.
"""

import os, os_dep, re
from error import *
from autotest_utils import *


def package_installed(package_version):
# Verify if package from a known package manager is intstalled given the package 
# version.
       known_package_managers = ['rpm', 'dpkg']
       for package_manager in known_package_managers:
               if package_manager == 'dpkg' and os_dep.command('dpkg'):
                       status = \
                       system_output('dpkg -s %s | grep Status' % package)
                       result = \
                       re.search('not-installed', status, re.IGNORECASE)
                       if not result:
                               return True
               if package_manager == 'rpm' and os_dep.command('rpm'):
                       try:
                               system('rpm -q ' + package)
                       except:
                               pass
                       return True
       return False


def install_package(package):
       if not os.path.isfile(package):
               raise ValueError, 'invalid file %s to install' % package
       # Use file and libmagic to determine the actual package file type.
       package_type = system_output('file ' + package)
       known_package = False
       known_package_managers = ['rpm', 'dpkg']
       for package_manager in known_package_managers:
               if package_manager == 'rpm':
                       package_version = system_output('rpm -qp ' + package)
                       package_pattern = 'RPM'
                       install_command = 'rpm -Uvh ' + package
               elif package_manager == 'dpkg':
                       package_version = \ 
                       system_output('dpkg -f %s Package' % package)
                       package_pattern = 'Debian'
                       install_command = 'dpkg -i ' + package
               if package_type.__contains__(package_pattern):
                       known_package = True
                       if not package_installed(package_version):
                               return system(install_command)
       if not known_package:
               raise PackageError, 'Package method not implemented' 
