'''
This module implements classes that perform the installation of the
virtualization software on a host system.

These classes can be, and usually are, inherited by subclasses that implement
custom logic for each virtualization hypervisor/software.
'''

import os, logging
from autotest_lib.client.bin import utils, os_dep
from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import virt_utils

class VirtInstallException(Exception):
    '''
    Base virtualization software components installation exception
    '''
    pass


class VirtInstallFailed(VirtInstallException):
    '''
    Installation of virtualization software components failed
    '''
    pass


class VirtInstallNotInstalled(VirtInstallException):
    '''
    Virtualization software components are not installed
    '''
    pass


class BaseInstaller(object):
    '''
    Base virtualization software installer

    This class holds all the skeleton features for installers and should be
    inherited from when creating a new installer.
    '''
    def __init__(self, mode, name, test=None, params=None):
        '''
        Instantiates a new base installer

        @param mode: installer mode, such as git_repo, local_src, etc
        @param name: installer short name, foo for git_repo_foo
        @param test: test
        @param params: params
        '''
        self.mode = mode
        self.name = name
        self.params = params
        self.param_key_prefix = '%s_%s' % (self.mode,
                                           self.name)

        if test and params:
            self.set_install_params(test, params)


    def _set_test_dirs(self, test):
        '''
        Save common test directories paths (srcdir, bindir) as class attributes

        Test variables values are saved here again because it's not possible to
        pickle the test instance inside BaseInstaller due to limitations
        in the pickle protocol. And, in case this pickle thing needs more
        explanation, take a loot at the Env class inside virt_utils.

        Besides that, we also ensure that srcdir exists, by creating it if
        necessary.

        For reference:
           * bindir = tests/<test>
           * srcdir = tests/<test>/src

        So, for KVM tests, it'd evaluate to:
           * bindir = tests/kvm/
           * srcdir = tests/kvm/src
        '''
        self.test_bindir = test.bindir
        self.test_srcdir = test.srcdir

        #
        # test_bindir is guaranteed to exist, but test_srcdir is not
        #
        if not os.path.isdir(test.srcdir):
            os.makedirs(test.srcdir)


    def _set_param_load_module(self):
        '''
        Checks whether kernel modules should be loaded

        Default behavior is to load modules unless set to 'no'

        Configuration file parameter: load_modules
        Class attribute set: should_load_modules
        '''
        load_modules = self.params.get('load_modules', 'no')
        if not load_modules or load_modules == 'yes':
            self.should_load_modules = True
        elif load_modules == 'no':
            self.should_load_modules = False


    def _set_param_module_list(self):
        '''
        Sets the list of kernel modules to be loaded during installation

        Configuration file parameter: module_list
        Class attribute set: module_list
        '''
        self.module_list = self.params.get('module_list', '').split()


    def _set_param_save_results(self):
        '''
        Checks whether to save the result of the build on test.resultsdir

        Configuration file parameter: save_results
        Class attribute set: save_results
        '''
        self.save_results = True
        save_results = self.params.get('save_results', 'no')
        if save_results == 'no':
            self.save_results = False


    def set_install_params(self, test=None, params=None):
        '''
        Called by test to setup parameters from the configuration file
        '''
        if test is not None:
            self._set_test_dirs(test)

        if params is not None:
            self.params = params
            self._set_param_load_module()
            self._set_param_module_list()
            self._set_param_save_results()


    def _install_phase_cleanup(self):
        '''
        Optional install phase for removing previous version of the software

        If a particular virtualization software installation mechanism
        needs to download files (it most probably does), override this
        method with custom functionality.

        This replaces methods such as KojiInstaller._get_packages()
        '''
        pass


    def _install_phase_cleanup_verify(self):
        '''
        Optional install phase for removing previous version of the software

        If a particular virtualization software installation mechanism
        needs to download files (it most probably does), override this
        method with custom functionality.

        This replaces methods such as KojiInstaller._get_packages()
        '''
        pass


    def _install_phase_download(self):
        '''
        Optional install phase for downloading software

        If a particular virtualization software installation mechanism
        needs to download files (it most probably does), override this
        method with custom functionality.

        This replaces methods such as KojiInstaller._get_packages()
        '''
        pass


    def _install_phase_download_verify(self):
        '''
        Optional install phase for checking downloaded software

        If you want to make sure the downloaded software is in good shape,
        override this method.

        Ideas for using this method:
          * check MD5SUM/SHA1SUM for tarball downloads
          * check RPM files, probaly by signature (rpm -k)
          * git status and check if there's no locally modified files
        '''
        pass


    def _install_phase_prepare(self):
        '''
        Optional install phase for preparing software

        If a particular virtualization software installation mechanism
        needs to do something to the obtained software, such as extracting
        a tarball or applying patches, this should be done here.
        '''
        pass


    def _install_phase_prepare_verify(self):
        '''
        Optional install phase for checking software preparation

        Ideas for using this method:
          * git status and check if there are locally patched files
        '''
        pass


    def _install_phase_build(self):
        '''
        Optional install phase for building software

        If a particular virtualization software installation mechanism
        needs to compile source code, it should be done here.
        '''
        pass


    def _install_phase_build_verify(self):
        '''
        Optional install phase for checking software build

        Ideas for using this method:
           * running 'make test' or something similar to it
        '''
        pass


    def _install_phase_install(self):
        '''
        Optional install phase for actually installing software

        Ideas for using this method:
           * running 'make install' or something similar to it
           * running 'yum localinstall *.rpm'
        '''
        pass


    def _install_phase_install_verify(self):
        '''
        Optional install phase for checking the installed software

        This should verify the installed software is in a desirable state.
        Ideas for using this include:
           * checking if installed files exists (like os.path.exists())
           * checking packages are indeed installed (rpm -q <pkg>.rpm)
        '''
        pass


    def _install_phase_init(self):
        '''
        Optional install phase for initializing the installed software

        This should initialize the installed software. Ideas for using this:
           * loading kernel modules
           * running services: 'service <daemon> start'
           * linking software (whether built or downloaded) to a common path
        '''
        pass


    def _install_phase_init_verify(self):
        '''
        Optional install phase for checking that software is initialized

        This should verify that the installed software is running. Ideas for
        using this include:
            * checking service (daemon) status: 'service <daemon> status'
            * checking service (functionality) status: 'virsh capabilities'
        '''
        pass


    def load_modules(self, module_list=None):
        '''
        Load Linux Kernel modules the virtualization software may depend on

        If module_directory is not set, the list of modules will simply be
        loaded by the system stock modprobe tool, meaning that modules will be
        looked for in the system default module paths.

        @type module_list: list
        @param module_list: list of kernel modules names to load
        '''
        if module_list is None:
            module_list = self.module_list

        logging.info("Loading modules from default locations through "
                     "modprobe")
        for module in module_list:
            utils.system("modprobe %s" % module)


    def unload_modules(self, module_list=None):
        '''
        Unloads kernel modules

        By default, if no module list is explicitly provided, the list on
        params (coming from the configuration file) will be used.
        '''
        if module_list is None:
            module_list = self.module_list
        module_list = reversed(module_list)
        logging.info("Unloading kernel modules: %s" % ",".join(module_list))
        for module in module_list:
            utils.unload_module(module)


    def reload_modules(self):
        """
        Reload the kernel modules (unload, then load)
        """
        self.unload_modules()
        self.load_modules()


    def reload_modules_if_needed(self):
        if self.should_load_modules:
            self.reload_modules()


    def install(self):
        '''
        Performs the installation of the virtualization software

        This is the main entry point of this class, and should  either
        be reimplemented completely, or simply implement one or many of the
        install  phases.
        '''
        self._install_phase_cleanup()
        self._install_phase_cleanup_verify()

        self._install_phase_download()
        self._install_phase_download_verify()

        self._install_phase_prepare()
        self._install_phase_prepare_verify()

        self._install_phase_build()
        self._install_phase_build_verify()

        self._install_phase_install()
        self._install_phase_install_verify()

        self._install_phase_init()
        self._install_phase_init_verify()

        self.reload_modules_if_needed()
        if self.save_results:
            virt_utils.archive_as_tarball(self.srcdir, self.results_dir)


    def uninstall(self):
        '''
        Performs the uninstallations of the virtualization software

        Note: This replaces old kvm_installer._clean_previous_install()
        '''
        raise NotImplementedError


class NoopInstaller(BaseInstaller):
    '''
    Dummy installer that does nothing, useful when software is pre-installed
    '''
    def install(self):
        logging.info("Assuming virtualization software to be already "
                     "installed. Doing nothing")


class YumInstaller(BaseInstaller):
    '''
    Installs virtualization software using YUM

    Notice: this class implements a change of behaviour if compared to
    kvm_installer.YumInstaller.set_install_params(). There's no longer
    a default package list, as each virtualization technology will have
    a completely different default. This should now be kept at the
    configuration file only.

    For now this class implements support for installing from the configured
    yum repos only. If the use case of installing from local RPM packages
    arises, we'll implement that.
    '''
    def set_install_params(self, test, params):
        super(YumInstaller, self).set_install_params(test, params)
        os_dep.command("rpm")
        os_dep.command("yum")
        self.yum_pkgs = eval(params.get("%s_pkgs" % self.param_key_prefix,
                                        "[]"))


    def _install_phase_cleanup(self):
        packages_to_remove = " ".join(self.yum_pkgs)
        utils.system("yum remove -y %s" % packages_to_remove)


    def _install_phase_install(self):
        if self.yum_pkgs:
            os.chdir(self.test_srcdir)
            utils.system("yum --nogpgcheck -y install %s" %
                         " ".join(self.yum_pkgs))


class KojiInstaller(BaseInstaller):
    '''
    Handles virtualization software installation via koji/brew

    It uses YUM to install and remove packages.

    Change notice: this is not a subclass of YumInstaller anymore. The
    parameters this class uses are different (koji_tag, koji_pgks) and
    the install process runs YUM.
    '''
    def set_install_params(self, test, params):
        super(KojiInstaller, self).set_install_params(test, params)
        os_dep.command("rpm")
        os_dep.command("yum")

        self.tag = params.get("%s_tag" % self.param_key_prefix, None)
        self.koji_cmd = params.get("%s_cmd" % self.param_key_prefix, None)
        if self.tag is not None:
            virt_utils.set_default_koji_tag(self.tag)
        self.koji_pkgs = eval(params.get("%s_pkgs" % self.param_key_prefix,
                                         "[]"))


    def _get_rpm_names(self):
        all_rpm_names = []
        koji_client = virt_utils.KojiClient(cmd=self.koji_cmd)
        for pkg_text in self.koji_pkgs:
            pkg = virt_utils.KojiPkgSpec(pkg_text)
            rpm_names = koji_client.get_pkg_rpm_names(pkg)
            all_rpm_names += rpm_names
        return all_rpm_names


    def _get_rpm_file_names(self):
        all_rpm_file_names = []
        koji_client = virt_utils.KojiClient(cmd=self.koji_cmd)
        for pkg_text in self.koji_pkgs:
            pkg = virt_utils.KojiPkgSpec(pkg_text)
            rpm_file_names = koji_client.get_pkg_rpm_file_names(pkg)
            all_rpm_file_names += rpm_file_names
        return all_rpm_file_names


    def _install_phase_cleanup(self):
        removable_packages = " ".join(self._get_rpm_names())
        utils.system("yum -y remove %s" % removable_packages)


    def _install_phase_download(self):
        koji_client = virt_utils.KojiClient(cmd=self.koji_cmd)
        for pkg_text in self.koji_pkgs:
            pkg = virt_utils.KojiPkgSpec(pkg_text)
            if pkg.is_valid():
                koji_client.get_pkgs(pkg, dst_dir=self.test_srcdir)
            else:
                logging.error('Package specification (%s) is invalid: %s' %
                              (pkg, pkg.describe_invalid()))


    def _install_phase_install(self):
        os.chdir(self.test_srcdir)
        rpm_file_names = " ".join(self._get_rpm_file_names())
        utils.system("yum --nogpgcheck -y localinstall %s" % rpm_file_names)


class BaseLocalSourceInstaller(BaseInstaller):
    def set_install_params(self, test, params):
        super(BaseLocalSourceInstaller, self).set_install_params(test, params)
        self._set_install_prefix()
        self._set_source_destination()

        #
        # There are really no choices for patch helpers
        #
        self.patch_helper = virt_utils.PatchParamHelper(
            self.params,
            self.param_key_prefix,
            self.source_destination)

        #
        # These helpers should be set by child classes
        #
        self.content_helper = None
        self.build_helper = None


    def _set_install_prefix(self):
        '''
        Prefix for installation of application built from source

        When installing virtualization software from *source*, this is where
        the resulting binaries will be installed. Usually this is the value
        passed to the configure script, ie: ./configure --prefix=<value>
        '''
        prefix = os.path.join(self.test_bindir, 'install_root')
        self.install_prefix = os.path.abspath(prefix)


    def _set_source_destination(self):
        '''
        Sets the source code destination directory path
        '''
        self.source_destination = os.path.join(self.test_srcdir,
                                               self.name)


    def _set_build_helper(self):
        '''
        Sets the build helper, default is 'gnu_autotools'
        '''
        build_helper_name = self.params.get('%s_build_helper' %
                                            self.param_key_prefix,
                                            'gnu_autotools')
        if build_helper_name == 'gnu_autotools':
            self.build_helper = virt_utils.GnuSourceBuildParamHelper(
                self.params, self.param_key_prefix,
                self.source_destination, self.install_prefix)


    def _install_phase_download(self):
        if self.content_helper is not None:
            self.content_helper.execute()


    def _install_phase_build(self):
        if self.build_helper is not None:
            self.build_helper.execute()


    def _install_phase_install(self):
        if self.build_helper is not None:
            self.build_helper.install()


class LocalSourceDirInstaller(BaseLocalSourceInstaller):
    '''
    Handles software installation by building/installing from a source dir
    '''
    def set_install_params(self, test, params):
        super(LocalSourceDirInstaller, self).set_install_params(test, params)

        self.content_helper = virt_utils.LocalSourceDirParamHelper(
            params,
            self.name,
            self.source_destination)

        self._set_build_helper()


class LocalSourceTarInstaller(BaseLocalSourceInstaller):
    '''
    Handles software installation by building/installing from a tarball
    '''
    def set_install_params(self, test, params):
        super(LocalSourceTarInstaller, self).set_install_params(test, params)

        self.content_helper = virt_utils.LocalTarParamHelper(
            params,
            self.name,
            self.source_destination)

        self._set_build_helper()


class RemoteSourceTarInstaller(BaseLocalSourceInstaller):
    '''
    Handles software installation by building/installing from a remote tarball
    '''
    def set_install_params(self, test, params):
        super(RemoteSourceTarInstaller, self).set_install_params(test, params)

        self.content_helper = virt_utils.RemoteTarParamHelper(
            params,
            self.name,
            self.source_destination)

        self._set_build_helper()


class GitRepoInstaller(BaseLocalSourceInstaller):
    def set_install_params(self, test, params):
        super(GitRepoInstaller, self).set_install_params(test, params)

        self.content_helper = virt_utils.GitRepoParamHelper(
            params,
            self.name,
            self.source_destination)

        self._set_build_helper()


class FailedInstaller:
    """
    Class used to be returned instead of the installer if a installation fails

    Useful to make sure no installer object is used if virt installation fails
    """
    def __init__(self, msg="Virtualization software install failed"):
        self._msg = msg


    def load_modules(self):
        """
        Will refuse to load the kerkel modules as install failed
        """
        raise VirtInstallFailed("Kernel modules not available. reason: %s" %
                                self._msg)
