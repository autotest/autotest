"""
Functions to handle software packages. The functions covered here aim to be
generic, with implementations that deal with different package managers, such
as dpkg and rpm.
"""

__author__ = 'lucasmr@br.ibm.com (Lucas Meneghel Rodrigues)'

import os, re
from autotest_lib.client.bin import os_dep, utils
from autotest_lib.client.common_lib import error

# As more package methods are implemented, this list grows up
KNOWN_PACKAGE_MANAGERS = ['rpm', 'dpkg']


def _rpm_info(rpm_package):
    """\
    Private function that returns a dictionary with information about an
    RPM package file
    - type: Package management program that handles the file
    - system_support: If the package management program is installed on the
    system or not
    - source: If it is a source (True) our binary (False) package
    - version: The package version (or name), that is used to check against the
    package manager if the package is installed
    - arch: The architecture for which a binary package was built
    - installed: Whether the package is installed (True) on the system or not
    (False)
    """
    # We will make good use of what the file command has to tell us about the
    # package :)
    file_result = utils.system_output('file ' + rpm_package)
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
        i_cmd = 'rpm -q ' + utils.system_output(v_cmd) + ' 2>&1 >/dev/null'

        package_info['system_support'] = True
        # Checking whether this is a source or src package
        source = utils.system_output(s_cmd)
        if source == '(none)':
            package_info['source'] = False
        else:
            package_info['source'] = True
        package_info['version'] = utils.system_output(v_cmd)
        package_info['arch'] = utils.system_output(a_cmd)
        # Checking if package is installed
        try:
            utils.system(i_cmd)
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


def _dpkg_info(dpkg_package):
    """\
    Private function that returns a dictionary with information about a
    dpkg package file
    - type: Package management program that handles the file
    - system_support: If the package management program is installed on the
    system or not
    - source: If it is a source (True) our binary (False) package
    - version: The package version (or name), that is used to check against the
    package manager if the package is installed
    - arch: The architecture for which a binary package was built
    - installed: Whether the package is installed (True) on the system or not
    (False)
    """
    # We will make good use of what the file command has to tell us about the
    # package :)
    file_result = utils.system_output('file ' + dpkg_package)
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
        i_cmd = 'dpkg -s ' + utils.system_output(v_cmd) + ' 2>/dev/null'

        package_info['system_support'] = True
        package_info['version'] = utils.system_output(v_cmd)
        package_info['arch'] = utils.system_output(a_cmd)
        # Checking if package is installed
        package_status = utils.system_output(i_cmd, ignore_status=True)
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


def list_all():
    """Returns a list with the names of all currently installed packages."""
    support_info = os_support()
    installed_packages = []

    if support_info['rpm']:
        installed_packages += utils.system_output('rpm -qa').splitlines()

    if support_info['dpkg']:
        raw_list = utils.system_output('dpkg -l').splitlines()[5:]
        for line in raw_list:
            parts = line.split()
            if parts[0] == "ii":  # only grab "installed" packages
                installed_packages.append("%s-%s" % (parts[1], parts[2]))

    return installed_packages


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
    file_result = utils.system_output('file ' + package)
    for package_manager in KNOWN_PACKAGE_MANAGERS:
        if package_manager == 'rpm':
            package_pattern = re.compile('RPM', re.IGNORECASE)
        elif package_manager == 'dpkg':
            package_pattern = re.compile('Debian', re.IGNORECASE)

        result = re.search(package_pattern, file_result)

        if result and package_manager == 'rpm':
            return _rpm_info(package)
        elif result and package_manager == 'dpkg':
            return _dpkg_info(package)

    # If it's not one of the implemented package manager methods, there's
    # not much that can be done, hence we throw an exception.
    raise error.PackageError('Unknown package type %s' % file_result)


def install(package, nodeps = False):
    """\
    Tries to install a package file. If the package is already installed,
    it prints a message to the user and ends gracefully. If nodeps is set to
    true, it will ignore package dependencies.
    """
    my_package_info = info(package)
    type = my_package_info['type']
    system_support = my_package_info['system_support']
    source = my_package_info['source']
    installed = my_package_info['installed']

    if not system_support:
        e_msg = ('Client does not have package manager %s to handle %s install'
                 % (type, package))
        raise error.PackageError(e_msg)

    opt_args = ''
    if type == 'rpm':
        if nodeps:
            opt_args = opt_args + '--nodeps'
        install_command = 'rpm %s -U %s' % (opt_args, package)
    if type == 'dpkg':
        if nodeps:
            opt_args = opt_args + '--force-depends'
        install_command = 'dpkg %s -i %s' % (opt_args, package)

    # RPM source packages can be installed along with the binary versions
    # with this check
    if installed and not source:
        return 'Package %s is already installed' % package

    # At this point, the most likely thing to go wrong is that there are
    # unmet dependencies for the package. We won't cover this case, at
    # least for now.
    utils.system(install_command)
    return 'Package %s was installed successfuly' % package


def convert(package, destination_format):
    """\
    Convert packages with the 'alien' utility. If alien is not installed, it
    throws a NotImplementedError exception.
    returns: filename of the package generated.
    """
    try:
        os_dep.command('alien')
    except:
        e_msg = 'Cannot convert to %s, alien not installed' % destination_format
        raise error.TestError(e_msg)

    # alien supports converting to many formats, but its interesting to map
    # convertions only for the implemented package types.
    if destination_format == 'dpkg':
        deb_pattern = re.compile('[A-Za-z0-9_.-]*[.][d][e][b]')
        conv_output = utils.system_output('alien --to-deb %s 2>/dev/null'
                                          % package)
        converted_package = re.findall(deb_pattern, conv_output)[0]
    elif destination_format == 'rpm':
        rpm_pattern = re.compile('[A-Za-z0-9_.-]*[.][r][p][m]')
        conv_output = utils.system_output('alien --to-rpm %s 2>/dev/null'
                                          % package)
        converted_package = re.findall(rpm_pattern, conv_output)[0]
    else:
        e_msg = 'Convertion to format %s not implemented' % destination_format
        raise NotImplementedError(e_msg)

    print 'Package %s successfuly converted to %s' % \
            (os.path.basename(package), os.path.basename(converted_package))
    return os.path.abspath(converted_package)


def os_support():
    """\
    Returns a dictionary with host os package support info:
    - rpm: True if system supports rpm packages, False otherwise
    - dpkg: True if system supports dpkg packages, False otherwise
    - conversion: True if the system can convert packages (alien installed),
    or False otherwise
    """
    support_info = {}
    for package_manager in KNOWN_PACKAGE_MANAGERS:
        try:
            os_dep.command(package_manager)
            support_info[package_manager] = True
        except:
            support_info[package_manager] = False

    try:
        os_dep.command('alien')
        support_info['conversion'] = True
    except:
        support_info['conversion'] = False

    return support_info
