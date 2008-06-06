# Wrapper to LSB testsuite
# Copyright 2008, IBM Corp.
import os, glob, re
from autotest_lib.client.bin import test, autotest_utils, package
from autotest_lib.client.bin.test_config import config_loader
from autotest_lib.client.common_lib import utils, error


__author__ = '''
pnaregun@in.ibm.com (Pavan Naregundi)
lucasmr@br.ibm.com (Lucas Meneghel Rodrigues)
'''

class lsb_dtk(test.test):
    version = 1
    def get_lsb_arch(self):
        self.arch = autotest_utils.get_current_kernel_arch()
        if self.arch in ['i386', 'i486', 'i586', 'i686', 'athlon']:
            return 'ia32'
        elif self.arch == 'ppc':
            return 'ppc32'
        elif self.arch in ['s390', 's390x', 'ia64', 'x86_64', 'ppc64']:
            return self.arch
        else:
            e_msg = 'Architecture %s not supported by LSB' % self.arch
            raise error.TestError(e_msg)


    def install_lsb_packages(self, srcdir, cachedir, my_config):
        # First, we download the LSB DTK manager package, worry about installing it later
        self.dtk_manager_arch = my_config.get('dtk-manager', 'arch-%s' % self.get_lsb_arch())
        self.dtk_manager_url = my_config.get('dtk-manager', 'tarball_url') % self.dtk_manager_arch
        if not self.dtk_manager_url:
            raise error.TestError('Could not get DTK manager URL from configuration file')
        self.dtk_md5 = my_config.get('dtk-manager', 'md5-%s' % self.get_lsb_arch())
        if self.dtk_md5:
            print 'Caching LSB DTK manager RPM'
            self.dtk_manager_pkg = autotest_utils.unmap_url_cache(cachedir, self.dtk_manager_url, self.dtk_md5)
        else:
            raise error.TestError('Could not find DTK manager package md5, cannot cache DTK manager tarball')

        # Get LSB tarball, cache it and uncompress under autotest srcdir
        if my_config.get('lsb', 'override_default_url') == 'no':
            self.lsb_url = my_config.get('lsb', 'tarball_url') % self.get_lsb_arch()
        else:
            self.lsb_url = my_config.get('lsb', 'tarball_url_alt') % self.get_lsb_arch()
        if not self.lsb_url:
            raise TestError('Could not get lsb URL from configuration file')
        self.md5_key = 'md5-%s' % self.get_lsb_arch()
        self.lsb_md5 = my_config.get('lsb', self.md5_key)
        if self.lsb_md5:
            print 'Caching LSB tarball'
            self.lsb_pkg = autotest_utils.unmap_url_cache(self.cachedir, self.lsb_url, self.lsb_md5)
        else:
            raise error.TestError('Could not find LSB package md5, cannot cache LSB tarball')

        autotest_utils.extract_tarball_to_dir(self.lsb_pkg, srcdir)

        # Lets load a file that contains the list of RPMs
        os.chdir(srcdir)
        if not os.path.isfile('inst-config'):
            raise IOError('Could not find file with package info, inst-config')
        self.rpm_file_list = open('inst-config', 'r')
        self.pkg_pattern = re.compile('[A-Za-z0-9_.-]*[.][r][p][m]')
        self.lsb_pkg_list = []
        for self.line in self.rpm_file_list.readlines():
            try:
                # We will install lsb-dtk-manager separately, so we can remove
                # it from the list of packages
                if not 'lsb-dtk-manager' in self.line:
                    self.line = re.findall(self.pkg_pattern, self.line)[0]
                    self.lsb_pkg_list.append(self.line)
            except:
                # If we don't get a match, no problem
                pass

        # Lets figure out the host distro
        distro_pkg_support = package.os_support()
        if os.path.isfile('/etc/debian_version') and distro_pkg_support['dpkg']:
            print 'Debian based distro detected'
            if distro_pkg_support['conversion']:
                print 'Package conversion supported'
                self.distro_type = 'debian-based'
            else:
                e_msg = 'Package conversion not supported. Cannot handle LSB package installation'
                raise EnvironmentError(e_msg)
        elif distro_pkg_support['rpm']:
            print 'Red Hat based distro detected'
            self.distro_type = 'redhat-based'
        else:
            print 'OS does not seem to be red hat or debian based'
            e_msg = 'Cannot handle LSB package installation'
            raise EnvironmentError(e_msg)

        # According to the host distro detection, we can install the packages
        # using the list previously assembled
        if self.distro_type == 'redhat-based':
            print 'Installing LSB RPM packages'
            package.install(self.dtk_manager_pkg)
            for self.lsb_rpm in self.lsb_pkg_list:
                package.install(self.lsb_rpm, nodeps = True)
        elif self.distro_type == 'debian-based':
            print 'Remember that you must have the following lsb compliance packages installed:'
            print 'lsb-core lsb-cxx lsb-graphics lsb-desktop lsb-qt4 lsb-languages lsb-multimedia lsb-printing'
            print 'Converting and installing LSB packages'
            self.dtk_manager_dpkg = package.convert(self.dtk_manager_pkg, 'dpkg')
            package.install(self.dtk_manager_dpkg)
            for self.lsb_rpm in self.lsb_pkg_list:
                self.lsb_dpkg = package.convert(self.lsb_rpm, 'dpkg')
                package.install(self.lsb_dpkg, nodeps = True)

    def link_lsb_libraries(self, config):
        print 'Linking LSB libraries'
        self.libdir_key = 'libdir-%s' % self.get_lsb_arch()
        self.os_libdir = config.get('lib', self.libdir_key)
        if not self.os_libdir:
            raise TypeError('Could not find OS lib dir from conf file')
        self.lib_key = 'lib-%s' % self.get_lsb_arch()
        self.lib_list_raw = config.get('lib', self.lib_key)
        if not self.lib_list_raw:
            raise TypeError('Could not find library list from conf file')
        self.lib_list = eval(self.lib_list_raw)

        # Remove any previous ld-lsb*.so symbolic links
        self.lsb_libs = glob.glob('%s/ld-lsb*.so*' % self.os_libdir)
        for self.lib in self.lsb_libs:
            os.remove(self.lib)

        # Get the base library that we'll use to recreate the symbolic links
        self.system_lib = glob.glob('%s/ld-2*.so*' % self.os_libdir)[0]

        # Now just link the system lib that we just found to each one of the
        # needed LSB libraries that we provided on the conf file
        for self.lsb_lib in self.lib_list:
            # Get the library absolute path
            self.lsb_lib = os.path.join(self.os_libdir, self.lsb_lib)
            # Link the library system_lib -> lsb_lib
            os.symlink(self.system_lib, self.lsb_lib)


    def execute(self, args = 'all', config = './lsb31.cfg'):
        # Load configuration. Use autotest tmpdir if needed
        my_config = config_loader(config, self.tmpdir)
        # Cache directory, that will store LSB tarball and DTK manager RPM
        self.cachedir = os.path.join(self.bindir, 'cache')
        if not os.path.isdir(self.cachedir):
            os.makedirs(self.cachedir)

        self.install_lsb_packages(self.srcdir, self.cachedir, my_config)
        self.link_lsb_libraries(my_config)

        self.main_script_path = my_config.get('lsb', 'main_script_path')
        logfile = os.path.join(self.resultsdir, 'lsb.log')
        args2 = '-r %s' % (logfile)
        args = args + ' ' + args2
        cmd = os.path.join(self.srcdir, self.main_script_path) + ' ' + args

        profilers = self.job.profilers
        if profilers.present():
            profilers.start(self)
        print 'Executing LSB main test script'
        utils.system(cmd)
        if profilers.present():
            profilers.stop(self)
            profilers.report(self)
