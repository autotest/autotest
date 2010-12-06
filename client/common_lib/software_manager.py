#!/usr/bin/python
"""
Software package management library.

This is an abstraction layer on top of the existing distributions high level
package managers. It supports package operations useful for testing purposes,
and multiple high level package managers (here called backends). If you want
to make this lib to support your particular package manager/distro, please
implement the given backend class.

@author: Higor Vieira Alves (halves@br.ibm.com)
@author: Lucas Meneghel Rodrigues (lmr@redhat.com)
@author: Ramon de Carvalho Valle (rcvalle@br.ibm.com)

@copyright: IBM 2008-2009
@copyright: Red Hat 2009-2010
"""
import os, re, logging, ConfigParser, optparse, random, string
try:
    import yum
except:
    pass
import common
from autotest_lib.client.bin import os_dep, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import logging_config, logging_manager


def generate_random_string(length):
    """
    Return a random string using alphanumeric characters.

    @length: Length of the string that will be generated.
    """
    r = random.SystemRandom()
    str = ""
    chars = string.letters + string.digits
    while length > 0:
        str += r.choice(chars)
        length -= 1
    return str


class SoftwareManagerLoggingConfig(logging_config.LoggingConfig):
    """
    Used with the sole purpose of providing convenient logging setup
    for the KVM test auxiliary programs.
    """
    def configure_logging(self, results_dir=None, verbose=False):
        super(SoftwareManagerLoggingConfig, self).configure_logging(
                                                            use_console=True,
                                                            verbose=verbose)


class SystemInspector(object):
    """
    System inspector class.

    This may grow up to include more complete reports of operating system and
    machine properties.
    """
    def __init__(self):
        """
        Probe system, and save information for future reference.
        """
        self.distro = utils.get_os_vendor()
        self.high_level_pms = ['apt-get', 'yum', 'zypper']


    def get_package_management(self):
        """
        Determine the supported package management systems present on the
        system. If more than one package management system installed, try
        to find the best supported system.
        """
        list_supported = []
        for high_level_pm in self.high_level_pms:
            try:
                os_dep.command(high_level_pm)
                list_supported.append(high_level_pm)
            except:
                pass

        pm_supported = None
        if len(list_supported) == 0:
            pm_supported = None
        if len(list_supported) == 1:
            pm_supported = list_supported[0]
        elif len(list_supported) > 1:
            if 'apt-get' in list_supported and self.distro in ['Debian', 'Ubuntu']:
                pm_supported = 'apt-get'
            elif 'yum' in list_supported and self.distro == 'Fedora':
                pm_supported = 'yum'
            else:
                pm_supported = list_supported[0]

        logging.debug('Package Manager backend: %s' % pm_supported)
        return pm_supported


class SoftwareManager(object):
    """
    Package management abstraction layer.

    It supports a set of common package operations for testing purposes, and it
    uses the concept of a backend, a helper class that implements the set of
    operations of a given package management tool.
    """
    def __init__(self):
        """
        Class constructor.

        Determines the best supported package management system for the given
        operating system running and initializes the appropriate backend.
        """
        inspector = SystemInspector()
        backend_type = inspector.get_package_management()
        if backend_type == 'yum':
            self.backend = YumBackend()
        elif backend_type == 'zypper':
            self.backend = ZypperBackend()
        elif backend_type == 'apt-get':
            self.backend = AptBackend()
        else:
            raise NotImplementedError('Unimplemented package management '
                                      'system: %s.' % backend_type)


    def check_installed(self, name, version=None, arch=None):
        """
        Check whether a package is installed on this system.

        @param name: Package name.
        @param version: Package version.
        @param arch: Package architecture.
        """
        return self.backend.check_installed(name, version, arch)


    def list_all(self):
        """
        List all installed packages.
        """
        return self.backend.list_all()


    def list_files(self, name):
        """
        Get a list of all files installed by package [name].

        @param name: Package name.
        """
        return self.backend.list_files(name)


    def install(self, name):
        """
        Install package [name].

        @param name: Package name.
        """
        return self.backend.install(name)


    def remove(self, name):
        """
        Remove package [name].

        @param name: Package name.
        """
        return self.backend.remove(name)


    def add_repo(self, url):
        """
        Add package repo described by [url].

        @param name: URL of the package repo.
        """
        return self.backend.add_repo(url)


    def remove_repo(self, url):
        """
        Remove package repo described by [url].

        @param url: URL of the package repo.
        """
        return self.backend.remove_repo(url)


    def upgrade(self):
        """
        Upgrade all packages available.
        """
        return self.backend.upgrade()


    def provides(self, file):
        """
        Returns a list of packages that provides a given capability to the
        system (be it a binary, a library).

        @param file: Path to the file.
        """
        return self.backend.provides(file)


    def install_what_provides(self, file):
        """
        Installs package that provides [file].

        @param file: Path to file.
        """
        provides = self.provides(file)
        if provides is not None:
            self.install(provides)
        else:
            logging.warning('No package seems to provide %s', file)


class RpmBackend(object):
    """
    This class implements operations executed with the rpm package manager.

    rpm is a lower level package manager, used by higher level managers such
    as yum and zypper.
    """
    def __init__(self):
        self.lowlevel_base_cmd = os_dep.command('rpm')


    def _check_installed_version(self, name, version):
        """
        Helper for the check_installed public method.

        @param name: Package name.
        @param version: Package version.
        """
        cmd = (self.lowlevel_base_cmd + ' -q --qf %{VERSION} ' + name +
               ' 2> /dev/null')
        inst_version = utils.system_output(cmd)

        if inst_version >= version:
            return True
        else:
            return False


    def check_installed(self, name, version=None, arch=None):
        """
        Check if package [name] is installed.

        @param name: Package name.
        @param version: Package version.
        @param arch: Package architecture.
        """
        if arch:
            cmd = (self.lowlevel_base_cmd + ' -q --qf %{ARCH} ' + name +
                   ' 2> /dev/null')
            inst_archs = utils.system_output(cmd)
            inst_archs = inst_archs.split('\n')

            for inst_arch in inst_archs:
                if inst_arch == arch:
                    return self._check_installed_version(name, version)
            return False

        elif version:
            return self._check_installed_version(name, version)
        else:
            cmd = 'rpm -q ' + name + ' 2> /dev/null'
            return (os.system(cmd) == 0)


    def list_all(self):
        """
        List all installed packages.
        """
        installed_packages = utils.system_output('rpm -qa').splitlines()
        return installed_packages


    def list_files(self, name):
        """
        List files installed on the system by package [name].

        @param name: Package name.
        """
        path = os.path.abspath(name)
        if os.path.isfile(path):
            option = '-qlp'
            name = path
        else:
            option = '-ql'

        l_cmd = 'rpm' + ' ' + option + ' ' + name + ' 2> /dev/null'

        try:
            result = utils.system_output(l_cmd)
            list_files = result.split('\n')
            return list_files
        except error.CmdError:
            return []


class DpkgBackend(object):
    """
    This class implements operations executed with the dpkg package manager.

    dpkg is a lower level package manager, used by higher level managers such
    as apt and aptitude.
    """
    def __init__(self):
        self.lowlevel_base_cmd = os_dep.command('dpkg')


    def check_installed(self, name):
        if os.path.isfile(name):
            n_cmd = (self.lowlevel_base_cmd + ' -f ' + name +
                     ' Package 2>/dev/null')
            name = utils.system_output(n_cmd)
        i_cmd = self.lowlevel_base_cmd + ' -s ' + name + ' 2>/dev/null'
        # Checking if package is installed
        package_status = utils.system_output(i_cmd, ignore_status=True)
        not_inst_pattern = re.compile('not-installed', re.IGNORECASE)
        dpkg_not_installed = re.search(not_inst_pattern, package_status)
        if dpkg_not_installed:
            return False
        return True


    def list_all(self):
        """
        List all packages available in the system.
        """
        installed_packages = []
        raw_list = utils.system_output('dpkg -l').splitlines()[5:]
        for line in raw_list:
            parts = line.split()
            if parts[0] == "ii":  # only grab "installed" packages
                installed_packages.append("%s-%s" % (parts[1], parts[2]))


    def list_files(self, package):
        """
        List files installed by package [package].

        @param package: Package name.
        @return: List of paths installed by package.
        """
        if os.path.isfile(package):
            l_cmd = self.lowlevel_base_cmd + ' -c ' + package
        else:
            l_cmd = self.lowlevel_base_cmd + ' -l ' + package
        return utils.system_output(l_cmd).split('\n')


class YumBackend(RpmBackend):
    """
    Implements the yum backend for software manager.

    Set of operations for the yum package manager, commonly found on Yellow Dog
    Linux and Red Hat based distributions, such as Fedora and Red Hat
    Enterprise Linux.
    """
    def __init__(self):
        """
        Initializes the base command and the yum package repository.
        """
        super(YumBackend, self).__init__()
        executable = os_dep.command('yum')
        base_arguments = '-y'
        self.base_command = executable + ' ' + base_arguments
        self.repo_file_path = '/etc/yum.repos.d/autotest.repo'
        self.cfgparser = ConfigParser.ConfigParser()
        self.cfgparser.read(self.repo_file_path)
        y_cmd = executable + ' --version | head -1'
        self.yum_version = utils.system_output(y_cmd, ignore_status=True)
        logging.debug('Yum backend initialized')
        logging.debug('Yum version: %s' % self.yum_version)
        self.yum_base = yum.YumBase()


    def _cleanup(self):
        """
        Clean up the yum cache so new package information can be downloaded.
        """
        utils.system("yum clean all")


    def install(self, name):
        """
        Installs package [name]. Handles local installs.
        """
        if os.path.isfile(name):
            name = os.path.abspath(name)
            command = 'localinstall'
        else:
            command = 'install'

        i_cmd = self.base_command + ' ' + command + ' ' + name

        try:
            utils.system(i_cmd)
            return True
        except:
            return False


    def remove(self, name):
        """
        Removes package [name].

        @param name: Package name (eg. 'ipython').
        """
        r_cmd = self.base_command + ' ' + 'erase' + ' ' + name
        try:
            utils.system(r_cmd)
            return True
        except:
            return False


    def add_repo(self, url):
        """
        Adds package repository located on [url].

        @param url: Universal Resource Locator of the repository.
        """
        # Check if we URL is already set
        for section in self.cfgparser.sections():
            for option, value in self.cfgparser.items(section):
                if option == 'url' and value == url:
                    return True

        # Didn't find it, let's set it up
        while True:
            section_name = 'software_manager' + '_' + generate_random_string(4)
            if not self.cfgparser.has_section(section_name):
                break
        self.cfgparser.add_section(section_name)
        self.cfgparser.set(section_name, 'name',
                           'Repository added by the autotest software manager.')
        self.cfgparser.set(section_name, 'url', url)
        self.cfgparser.set(section_name, 'enabled', 1)
        self.cfgparser.set(section_name, 'gpgcheck', 0)
        self.cfgparser.write(self.repo_file_path)


    def remove_repo(self, url):
        """
        Removes package repository located on [url].

        @param url: Universal Resource Locator of the repository.
        """
        for section in self.cfgparser.sections():
            for option, value in self.cfgparser.items(section):
                if option == 'url' and value == url:
                    self.cfgparser.remove_section(section)
                    self.cfgparser.write(self.repo_file_path)


    def upgrade(self):
        """
        Upgrade all available packages.
        """
        r_cmd = self.base_command + ' ' + 'update'
        try:
            utils.system(r_cmd)
            return True
        except:
            return False


    def provides(self, name):
        """
        Returns a list of packages that provides a given capability.

        @param name: Capability name (eg, 'foo').
        """
        d_provides = self.yum_base.searchPackageProvides(args=[name])
        provides_list = [key for key in d_provides]
        if provides_list:
            logging.info("Package %s provides %s", provides_list[0], name)
            return str(provides_list[0])
        else:
            return None


class ZypperBackend(RpmBackend):
    """
    Implements the zypper backend for software manager.

    Set of operations for the zypper package manager, found on SUSE Linux.
    """
    def __init__(self):
        """
        Initializes the base command and the yum package repository.
        """
        super(ZypperBackend, self).__init__()
        self.base_command = os_dep.command('zypper') + ' -n'
        z_cmd = self.base_command + ' --version'
        self.zypper_version = utils.system_output(z_cmd, ignore_status=True)
        logging.debug('Zypper backend initialized')
        logging.debug('Zypper version: %s' % self.zypper_version)


    def install(self, name):
        """
        Installs package [name]. Handles local installs.

        @param name: Package Name.
        """
        path = os.path.abspath(name)
        i_cmd = self.base_command + ' install -l ' + name
        try:
            utils.system(i_cmd)
            return True
        except:
            return False


    def add_repo(self, url):
        """
        Adds repository [url].

        @param url: URL for the package repository.
        """
        ar_cmd = self.base_command + ' addrepo ' + url
        try:
            utils.system(ar_cmd)
            return True
        except:
            return False


    def remove_repo(self, url):
        """
        Removes repository [url].

        @param url: URL for the package repository.
        """
        rr_cmd = self.base_command + ' removerepo ' + url
        try:
            utils.system(rr_cmd)
            return True
        except:
            return False


    def remove(self, name):
        """
        Removes package [name].
        """
        r_cmd = self.base_command + ' ' + 'erase' + ' ' + name

        try:
            utils.system(r_cmd)
            return True
        except:
            return False


    def upgrade(self):
        """
        Upgrades all packages of the system.
        """
        u_cmd = self.base_command + ' update -l'

        try:
            utils.system(u_cmd)
            return True
        except:
            return False


    def provides(self, name):
        """
        Searches for what provides a given file.

        @param name: File path.
        """
        p_cmd = self.base_command + ' what-provides ' + name
        list_provides = []
        try:
            p_output = utils.system_output(p_cmd).split('\n')[4:]
            for line in p_output:
                line = [a.strip() for a in line.split('|')]
                try:
                    state, pname, type, version, arch, repository = line
                    if pname not in list_provides:
                        list_provides.append(pname)
                except IndexError:
                    pass
            if len(list_provides) > 1:
                logging.warning('More than one package found, '
                                'opting by the first queue result')
            if list_provides:
                logging.info("Package %s provides %s", list_provides[0], name)
                return list_provides[0]
            return None
        except:
            return None


class AptBackend(DpkgBackend):
    """
    Implements the apt backend for software manager.

    Set of operations for the apt package manager, commonly found on Debian and
    Debian based distributions, such as Ubuntu Linux.
    """
    def __init__(self):
        """
        Initializes the base command and the debian package repository.
        """
        super(AptBackend, self).__init__()
        executable = os_dep.command('apt-get')
        self.base_command = executable + ' -y'
        self.repo_file_path = '/etc/apt/sources.list.d/autotest'
        self.apt_version = utils.system_output('apt-get -v | head -1',
                                               ignore_status=True)
        logging.debug('Apt backend initialized')
        logging.debug('apt version: %s' % self.apt_version)


    def install(self, name):
        """
        Installs package [name].

        @param name: Package name.
        """
        command = 'install'
        i_cmd = self.base_command + ' ' + command + ' ' + name

        try:
            utils.system(i_cmd)
            return True
        except:
            return False


    def remove(self, name):
        """
        Remove package [name].

        @param name: Package name.
        """
        command = 'remove'
        flag = '--purge'
        r_cmd = self.base_command + ' ' + command + ' ' + flag + ' ' + name

        try:
            utils.system(r_cmd)
            return True
        except:
            return False


    def add_repo(self, repo):
        """
        Add an apt repository.

        @param repo: Repository string. Example:
                'deb http://archive.ubuntu.com/ubuntu/ maverick universe'
        """
        repo_file = open(self.repo_file_path, 'a')
        repo_file_contents = repo_file.read()
        if repo not in repo_file_contents:
            repo_file.write(repo)


    def remove_repo(self, repo):
        """
        Remove an apt repository.

        @param repo: Repository string. Example:
                'deb http://archive.ubuntu.com/ubuntu/ maverick universe'
        """
        repo_file = open(self.repo_file_path, 'r')
        new_file_contents = []
        for line in repo_file.readlines:
            if not line == repo:
                new_file_contents.append(line)
        repo_file.close()
        new_file_contents = "\n".join(new_file_contents)
        repo_file.open(self.repo_file_path, 'w')
        repo_file.write(new_file_contents)
        repo_file.close()


    def upgrade(self):
        """
        Upgrade all packages of the system with eventual new versions.
        """
        ud_command = 'update'
        ud_cmd = self.base_command + ' ' + ud_command
        try:
            utils.system(ud_cmd)
        except:
            logging.error("Apt package update failed")
        up_command = 'upgrade'
        up_cmd = self.base_command + ' ' + up_command
        try:
            utils.system(up_cmd)
            return True
        except:
            return False


    def provides(self, file):
        """
        Return a list of packages that provide [file].

        @param file: File path.
        """
        if not self.check_installed('apt-file'):
            self.install('apt-file')
        command = os_dep.command('apt-file')
        cache_update_cmd = command + ' update'
        try:
            utils.system(cache_update_cmd, ignore_status=True)
        except:
            logging.error("Apt file cache update failed")
        fu_cmd = command + ' search ' + file
        try:
            provides = utils.system_output(fu_cmd).split('\n')
            list_provides = []
            for line in provides:
                if line:
                    try:
                        line = line.split(':')
                        package = line[0].strip()
                        path = line[1].strip()
                        if path == file and package not in list_provides:
                            list_provides.append(package)
                    except IndexError:
                        pass
            if len(list_provides) > 1:
                logging.warning('More than one package found, '
                                'opting by the first queue result')
            if list_provides:
                logging.info("Package %s provides %s", list_provides[0], file)
                return list_provides[0]
            return None
        except:
            return None


if __name__ == '__main__':
    parser = optparse.OptionParser(
    "usage: %prog [install|remove|list-all|list-files|add-repo|remove-repo|"
    "upgrade|what-provides|install-what-provides] arguments")
    parser.add_option('--verbose', dest="debug", action='store_true',
                      help='include debug messages in console output')

    options, args = parser.parse_args()
    debug = options.debug
    logging_manager.configure_logging(SoftwareManagerLoggingConfig(),
                                      verbose=debug)
    software_manager = SoftwareManager()
    if args:
        action = args[0]
        args = " ".join(args[1:])
    else:
        action = 'show-help'

    if action == 'install':
        software_manager.install(args)
    elif action == 'remove':
        software_manager.remove(args)
    if action == 'list-all':
        software_manager.list_all()
    elif action == 'list-files':
        software_manager.list_files(args)
    elif action == 'add-repo':
        software_manager.add_repo(args)
    elif action == 'remove-repo':
        software_manager.remove_repo(args)
    elif action == 'upgrade':
        software_manager.upgrade()
    elif action == 'what-provides':
        software_manager.provides(args)
    elif action == 'install-what-provides':
        software_manager.install_what_provides(args)
    elif action == 'show-help':
        parser.print_help()
