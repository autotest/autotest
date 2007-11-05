"""
Functions to handle software packages. The functions covered here aim to be 
generic, with implementations that deal with different package managers, such
as dpkg and rpm.
"""

import os, re
from error import *
from autotest_utils import *


def package_installed(package, package_type):
       # Verify if a package file from a known package manager is intstalled.
       if package_type == 'dpkg':
               status = system_output('dpkg -s %s | grep Status' % package)
               result = re.search('not-installed', status, re.IGNORECASE)
               if result:
                       return False
               else:
                       return True
       elif package_type == 'rpm':
               try:
                       system('rpm -q ' + package)
               except:
                       return False
               return True
       else:
               raise 'PackageError', 'Package method not implemented'


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
                       package_version = system_output('dpkg -f %s Package' % package)
                       package_pattern = 'Debian'
                       install_command = 'dpkg -i ' + package
               if package_type.__contains__(package_pattern):
                       known_package = True
                       if not package_installed(package_version, package_manager):
                               return system(install_command)
       if not known_package:
               raise 'PackageError', 'Package method not implemented'
