import os, glob, re, logging
from autotest_lib.client.bin import test, utils, package
from autotest_lib.client.bin.test_config import config_loader
from autotest_lib.client.common_lib import error

class lsb_dtk(test.test):
    """
    This autotest module runs the LSB test suite.

    @copyright: IBM 2008
    @author: Pavan Naregundi (pnaregun@in.ibm.com)
    @author: Lucas Meneghel Rodrigues (lucasmr@br.ibm.com)
    """
    version = 1
    def initialize(self, config):
        arch = utils.get_current_kernel_arch()
        if arch in ['i386', 'i486', 'i586', 'i686', 'athlon']:
            self.arch = 'ia32'
        elif arch == 'ppc':
            self.arch = 'ppc32'
        elif arch in ['s390', 's390x', 'ia64', 'x86_64', 'ppc64']:
            self.arch = arch
        else:
            e_msg = 'Architecture %s not supported by LSB' % arch
            raise error.TestError(e_msg)

        self.config = config_loader(config, self.tmpdir)
        self.cachedir = os.path.join(self.bindir, 'cache')
        if not os.path.isdir(self.cachedir):
            os.makedirs(self.cachedir)

        self.packages_installed = False
        self.libraries_linked = False



    def install_lsb_packages(self):
        if not self.packages_installed:
            # First, we download the LSB DTK manager package, worry about
            # installing it later
            dtk_manager_arch = self.config.get('dtk-manager', 'arch-%s' % self.arch)
            dtk_manager_url = self.config.get('dtk-manager',
                                         'tarball_url') % dtk_manager_arch
            if not dtk_manager_url:
                raise error.TestError('Could not get DTK manager URL from'
                                      ' configuration file')

            dtk_md5 = self.config.get('dtk-manager', 'md5-%s' % self.arch)
            if dtk_md5:
                logging.info('Caching LSB DTK manager RPM')
                dtk_manager_pkg = utils.unmap_url_cache(self.cachedir,
                                                        dtk_manager_url,
                                                        dtk_md5)
            else:
                raise error.TestError('Could not find DTK manager package md5,'
                                      ' cannot cache DTK manager tarball')

            # Get LSB tarball, cache it and uncompress under autotest srcdir
            if self.config.get('lsb', 'override_default_url') == 'no':
                lsb_url = self.config.get('lsb', 'tarball_url') % self.arch
            else:
                lsb_url = self.config.get('lsb', 'tarball_url_alt') % self.arch
            if not lsb_url:
                raise error.TestError('Could not get LSB URL from configuration'
                                      ' file')
            md5_key = 'md5-%s' % self.arch
            lsb_md5 = self.config.get('lsb', md5_key)
            if lsb_md5:
                logging.info('Caching LSB tarball')
                lsb_pkg = utils.unmap_url_cache(self.cachedir, lsb_url, lsb_md5)
            else:
                raise error.TestError('Could not find LSB package md5, cannot'
                                      ' cache LSB tarball')

            utils.extract_tarball_to_dir(lsb_pkg, self.srcdir)

            # Lets load a file that contains the list of RPMs
            os.chdir(self.srcdir)
            if not os.path.isfile('inst-config'):
                raise IOError('Could not find file with package info,'
                              ' inst-config')
            rpm_file_list = open('inst-config', 'r')
            pkg_pattern = re.compile('[A-Za-z0-9_.-]*[.][r][p][m]')
            lsb_pkg_list = []
            for line in rpm_file_list.readlines():
                try:
                    # We will install lsb-dtk-manager separately, so we can remove
                    # it from the list of packages
                    if not 'lsb-dtk-manager' in line:
                        line = re.findall(pkg_pattern, line)[0]
                        lsb_pkg_list.append(line)
                except:
                    # If we don't get a match, no problem
                    pass

            # Lets figure out the host distro
            distro_pkg_support = package.os_support()
            if os.path.isfile('/etc/debian_version') and \
            distro_pkg_support['dpkg']:
                logging.debug('Debian based distro detected')
                if distro_pkg_support['conversion']:
                    logging.debug('Package conversion supported')
                    distro_type = 'debian-based'
                else:
                    raise EnvironmentError('Package conversion not supported.'
                                           'Cannot handle LSB package'
                                           ' installation')
            elif distro_pkg_support['rpm']:
                logging.debug('Red Hat based distro detected')
                distro_type = 'redhat-based'
            else:
                logging.error('OS does not seem to be red hat or debian based')
                raise EnvironmentError('Cannot handle LSB package installation')

            # According to the host distro detection, we can install the packages
            # using the list previously assembled
            if distro_type == 'redhat-based':
                logging.info('Installing LSB RPM packages')
                package.install(dtk_manager_pkg)
                for lsb_rpm in lsb_pkg_list:
                    package.install(lsb_rpm, nodeps=True)
            elif distro_type == 'debian-based':
                logging.info('Remember that you must have the following lsb'
                             ' compliance packages installed:')
                logging.info('lsb-core lsb-cxx lsb-graphics lsb-desktop lsb-qt4'
                             ' lsb-languages lsb-multimedia lsb-printing')
                logging.info('Converting and installing LSB packages')
                dtk_manager_dpkg = package.convert(dtk_manager_pkg, 'dpkg')
                package.install(dtk_manager_dpkg)
                for lsb_rpm in lsb_pkg_list:
                    lsb_dpkg = package.convert(lsb_rpm, 'dpkg')
                    package.install(lsb_dpkg, nodeps=True)

            self.packages_installed = True


    def link_lsb_libraries(self):
        if not self.libraries_linked:
            logging.info('Linking LSB libraries')
            libdir_key = 'libdir-%s' % self.arch
            os_libdir = self.config.get('lib', libdir_key)
            if not os_libdir:
                raise TypeError('Could not find OS lib dir from conf file')
            lib_key = 'lib-%s' % self.arch
            lib_list_raw = self.config.get('lib', lib_key)
            if not lib_list_raw:
                raise TypeError('Could not find library list from conf file')
            lib_list = eval(lib_list_raw)

            # Remove any previous ld-lsb*.so symbolic links
            lsb_libs = glob.glob('%s/ld-lsb*.so*' % os_libdir)
            for lib in lsb_libs:
                os.remove(lib)

            # Get the base library that we'll use to recreate the symbolic links
            system_lib = glob.glob('%s/ld-2*.so*' % os_libdir)[0]

            # Now just link the system lib that we just found to each one of the
            # needed LSB libraries that we provided on the conf file
            for lsb_lib in lib_list:
                # Get the library absolute path
                lsb_lib = os.path.join(os_libdir, lsb_lib)
                # Link the library system_lib -> lsb_lib
                os.symlink(system_lib, lsb_lib)

            self.libraries_linked = True


    def run_once(self, args = 'all'):
        self.install_lsb_packages()
        self.link_lsb_libraries()

        main_script_path = self.config.get('lsb', 'main_script_path')

        logfile = os.path.join(self.resultsdir, 'lsb.log')
        log_arg = '-r %s' % (logfile)
        args = args + ' ' + log_arg
        cmd = os.path.join(self.srcdir, main_script_path) + ' ' + args

        logging.info('Executing LSB main test script')
        utils.system(cmd)
