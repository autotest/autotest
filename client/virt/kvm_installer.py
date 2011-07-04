import os, logging, datetime, glob, shutil
from autotest_lib.client.bin import utils, os_dep
from autotest_lib.client.common_lib import error
import virt_utils, virt_installer


def kill_qemu_processes():
    """
    Kills all qemu processes, also kills all processes holding /dev/kvm down.
    """
    logging.debug("Killing any qemu processes that might be left behind")
    utils.system("pkill qemu", ignore_status=True)
    # Let's double check to see if some other process is holding /dev/kvm
    if os.path.isfile("/dev/kvm"):
        utils.system("fuser -k /dev/kvm", ignore_status=True)


def create_symlinks(test_bindir, prefix=None, bin_list=None, unittest=None):
    """
    Create symbolic links for the appropriate qemu and qemu-img commands on
    the kvm test bindir.

    @param test_bindir: KVM test bindir
    @param prefix: KVM prefix path
    @param bin_list: List of qemu binaries to link
    @param unittest: Path to configuration file unittests.cfg
    """
    qemu_path = os.path.join(test_bindir, "qemu")
    qemu_img_path = os.path.join(test_bindir, "qemu-img")
    qemu_unittest_path = os.path.join(test_bindir, "unittests")
    if os.path.lexists(qemu_path):
        os.unlink(qemu_path)
    if os.path.lexists(qemu_img_path):
        os.unlink(qemu_img_path)
    if unittest and os.path.lexists(qemu_unittest_path):
        os.unlink(qemu_unittest_path)

    logging.debug("Linking qemu binaries")

    if bin_list:
        for bin in bin_list:
            if os.path.basename(bin) == 'qemu-kvm':
                os.symlink(bin, qemu_path)
            elif os.path.basename(bin) == 'qemu-img':
                os.symlink(bin, qemu_img_path)

    elif prefix:
        kvm_qemu = os.path.join(prefix, "bin", "qemu-system-x86_64")
        if not os.path.isfile(kvm_qemu):
            raise error.TestError('Invalid qemu path')
        kvm_qemu_img = os.path.join(prefix, "bin", "qemu-img")
        if not os.path.isfile(kvm_qemu_img):
            raise error.TestError('Invalid qemu-img path')
        os.symlink(kvm_qemu, qemu_path)
        os.symlink(kvm_qemu_img, qemu_img_path)

    if unittest:
        logging.debug("Linking unittest dir")
        os.symlink(unittest, qemu_unittest_path)


def install_roms(rom_dir, prefix):
    logging.debug("Path to roms specified. Copying roms to install prefix")
    rom_dst_dir = os.path.join(prefix, 'share', 'qemu')
    for rom_src in glob.glob('%s/*.bin' % rom_dir):
        rom_dst = os.path.join(rom_dst_dir, os.path.basename(rom_src))
        logging.debug("Copying rom file %s to %s", rom_src, rom_dst)
        shutil.copy(rom_src, rom_dst)


class KvmInstallException(Exception):
    pass


class FailedKvmInstall(KvmInstallException):
    pass


class KvmNotInstalled(KvmInstallException):
    pass


class BaseInstaller(object):
    def __init__(self, mode=None):
        self.install_mode = mode
        self._full_module_list = None

    def set_install_params(self, test, params):
        self.params = params

        load_modules = params.get('load_modules', 'no')
        if not load_modules or load_modules == 'yes':
            self.should_load_modules = True
        elif load_modules == 'no':
            self.should_load_modules = False
        default_extra_modules = str(None)
        self.extra_modules = eval(params.get("extra_modules",
                                             default_extra_modules))

        self.cpu_vendor = virt_utils.get_cpu_vendor()

        self.srcdir = test.srcdir
        if not os.path.isdir(self.srcdir):
            os.makedirs(self.srcdir)

        self.test_bindir = test.bindir
        self.results_dir = test.resultsdir

        # KVM build prefix, for the modes that do need it
        prefix = os.path.join(test.bindir, 'build')
        self.prefix = os.path.abspath(prefix)

        # Current host kernel directory
        default_host_kernel_source = '/lib/modules/%s/build' % os.uname()[2]
        self.host_kernel_srcdir = params.get('host_kernel_source',
                                             default_host_kernel_source)

        # Extra parameters that can be passed to the configure script
        self.extra_configure_options = params.get('extra_configure_options',
                                                  None)

        # Do we want to save the result of the build on test.resultsdir?
        self.save_results = True
        save_results = params.get('save_results', 'no')
        if save_results == 'no':
            self.save_results = False

        self._full_module_list = list(self._module_list())


    def install_unittests(self):
        userspace_srcdir = os.path.join(self.srcdir, "kvm_userspace")
        test_repo = self.params.get("test_git_repo")
        test_branch = self.params.get("test_branch", "master")
        test_commit = self.params.get("test_commit", None)
        test_lbranch = self.params.get("test_lbranch", "master")

        if test_repo:
            test_srcdir = os.path.join(self.srcdir, "kvm-unit-tests")
            virt_utils.get_git_branch(test_repo, test_branch, test_srcdir,
                                     test_commit, test_lbranch)
            unittest_cfg = os.path.join(test_srcdir, 'x86',
                                        'unittests.cfg')
            self.test_srcdir = test_srcdir
        else:
            unittest_cfg = os.path.join(userspace_srcdir, 'kvm', 'test', 'x86',
                                        'unittests.cfg')
        self.unittest_cfg = None
        if os.path.isfile(unittest_cfg):
            self.unittest_cfg = unittest_cfg
        else:
            if test_repo:
                logging.error("No unittest config file %s found, skipping "
                              "unittest build", self.unittest_cfg)

        self.unittest_prefix = None
        if self.unittest_cfg:
            logging.info("Building and installing unittests")
            os.chdir(os.path.dirname(os.path.dirname(self.unittest_cfg)))
            utils.system('./configure --prefix=%s' % self.prefix)
            utils.system('make')
            utils.system('make install')
            self.unittest_prefix = os.path.join(self.prefix, 'share', 'qemu',
                                                'tests')


    def full_module_list(self):
        """Return the module list used by the installer

        Used by the module_probe test, to avoid using utils.unload_module().
        """
        if self._full_module_list is None:
            raise KvmNotInstalled("KVM modules not installed yet (installer: %s)" % (type(self)))
        return self._full_module_list


    def _module_list(self):
        """Generate the list of modules that need to be loaded
        """
        yield 'kvm'
        yield 'kvm-%s' % (self.cpu_vendor)
        if self.extra_modules:
            for module in self.extra_modules:
                yield module


    def _load_modules(self, mod_list):
        """
        Load the KVM modules

        May be overridden by subclasses.
        """
        logging.info("Loading KVM modules")
        for module in mod_list:
            utils.system("modprobe %s" % module)


    def load_modules(self, mod_list=None):
        if mod_list is None:
            mod_list = self.full_module_list()
        self._load_modules(mod_list)


    def _unload_modules(self, mod_list=None):
        """
        Just unload the KVM modules, without trying to kill Qemu
        """
        if mod_list is None:
            mod_list = self.full_module_list()
        logging.info("Unloading previously loaded KVM modules")
        for module in reversed(mod_list):
            utils.unload_module(module)


    def unload_modules(self, mod_list=None):
        """
        Kill Qemu and unload the KVM modules
        """
        kill_qemu_processes()
        self._unload_modules(mod_list)


    def reload_modules(self):
        """
        Reload the KVM modules after killing Qemu and unloading the current modules
        """
        self.unload_modules()
        self.load_modules()


    def reload_modules_if_needed(self):
        if self.should_load_modules:
            self.reload_modules()


class YumInstaller(BaseInstaller):
    """
    Class that uses yum to install and remove packages.
    """
    def set_install_params(self, test, params):
        super(YumInstaller, self).set_install_params(test, params)
        # Checking if all required dependencies are available
        os_dep.command("rpm")
        os_dep.command("yum")

        default_pkg_list = str(['qemu-kvm', 'qemu-kvm-tools'])
        default_qemu_bin_paths = str(['/usr/bin/qemu-kvm', '/usr/bin/qemu-img'])
        default_pkg_path_list = str(None)
        self.pkg_list = eval(params.get("pkg_list", default_pkg_list))
        self.pkg_path_list = eval(params.get("pkg_path_list",
                                             default_pkg_path_list))
        self.qemu_bin_paths = eval(params.get("qemu_bin_paths",
                                              default_qemu_bin_paths))


    def _clean_previous_installs(self):
        kill_qemu_processes()
        removable_packages = ""
        for pkg in self.pkg_list:
            removable_packages += " %s" % pkg

        utils.system("yum remove -y %s" % removable_packages)


    def _get_packages(self):
        for pkg in self.pkg_path_list:
            utils.get_file(pkg, os.path.join(self.srcdir,
                                             os.path.basename(pkg)))


    def _install_packages(self):
        """
        Install all downloaded packages.
        """
        os.chdir(self.srcdir)
        utils.system("yum install --nogpgcheck -y *.rpm")


    def install(self):
        self.install_unittests()
        self._clean_previous_installs()
        self._get_packages()
        self._install_packages()
        create_symlinks(test_bindir=self.test_bindir,
                        bin_list=self.qemu_bin_paths,
                        unittest=self.unittest_prefix)
        self.reload_modules_if_needed()
        if self.save_results:
            virt_utils.archive_as_tarball(self.srcdir, self.results_dir)


class KojiInstaller(YumInstaller):
    """
    Class that handles installing KVM from the fedora build service, koji.

    It uses yum to install and remove packages. Packages are specified
    according to the syntax defined in the PkgSpec class.
    """
    def set_install_params(self, test, params):
        """
        Gets parameters and initializes the package downloader.

        @param test: kvm test object
        @param params: Dictionary with test arguments
        """
        super(KojiInstaller, self).set_install_params(test, params)
        self.tag = params.get("koji_tag", None)
        self.koji_cmd = params.get("koji_cmd", None)
        if self.tag is not None:
            virt_utils.set_default_koji_tag(self.tag)
        self.koji_pkgs = eval(params.get("koji_pkgs", "[]"))


    def _get_packages(self):
        """
        Downloads the specific arch RPMs for the specific build name.
        """
        koji_client = virt_utils.KojiClient(cmd=self.koji_cmd)
        for pkg_text in self.koji_pkgs:
            pkg = virt_utils.KojiPkgSpec(pkg_text)
            if pkg.is_valid():
                koji_client.get_pkgs(pkg, dst_dir=self.srcdir)
            else:
                logging.error('Package specification (%s) is invalid: %s', pkg,
                              pkg.describe_invalid())


    def _clean_previous_installs(self):
        kill_qemu_processes()
        removable_packages = " ".join(self._get_rpm_names())
        utils.system("yum -y remove %s" % removable_packages)


    def install(self):
        self._clean_previous_installs()
        self._get_packages()
        self._install_packages()
        self.install_unittests()
        create_symlinks(test_bindir=self.test_bindir,
                        bin_list=self.qemu_bin_paths,
                        unittest=self.unittest_prefix)
        self.reload_modules_if_needed()
        if self.save_results:
            virt_utils.archive_as_tarball(self.srcdir, self.results_dir)


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


    def _install_packages(self):
        """
        Install all downloaded packages.
        """
        os.chdir(self.srcdir)
        rpm_file_names = " ".join(self._get_rpm_file_names())
        utils.system("yum --nogpgcheck -y localinstall %s" % rpm_file_names)


class SourceDirInstaller(BaseInstaller):
    """
    Class that handles building/installing KVM directly from a tarball or
    a single source code dir.
    """
    def set_install_params(self, test, params):
        """
        Initializes class attributes, and retrieves KVM code.

        @param test: kvm test object
        @param params: Dictionary with test arguments
        """
        super(SourceDirInstaller, self).set_install_params(test, params)

        self.mod_install_dir = os.path.join(self.prefix, 'modules')

        srcdir = params.get("srcdir", None)
        self.path_to_roms = params.get("path_to_rom_images", None)

        if self.install_mode == 'localsrc':
            if srcdir is None:
                raise error.TestError("Install from source directory specified"
                                      "but no source directory provided on the"
                                      "control file.")
            else:
                shutil.copytree(srcdir, self.srcdir)

        elif self.install_mode == 'localtar':
            tarball = params.get("tarball")
            if not tarball:
                raise error.TestError("KVM Tarball install specified but no"
                                      " tarball provided on control file.")
            logging.info("Installing KVM from a local tarball")
            logging.info("Using tarball %s")
            tarball = utils.unmap_url("/", params.get("tarball"), "/tmp")
            utils.extract_tarball_to_dir(tarball, self.srcdir)

        if self.install_mode in ['localtar', 'srcdir']:
            self.repo_type = virt_utils.check_kvm_source_dir(self.srcdir)
            p = os.path.join(self.srcdir, 'configure')
            self.configure_options = virt_installer.check_configure_options(p)


    def _build(self):
        make_jobs = utils.count_cpus()
        os.chdir(self.srcdir)
        # For testing purposes, it's better to build qemu binaries with
        # debugging symbols, so we can extract more meaningful stack traces.
        cfg = "./configure --prefix=%s" % self.prefix
        if "--disable-strip" in self.configure_options:
            cfg += " --disable-strip"
        steps = [cfg, "make clean", "make -j %s" % make_jobs]
        logging.info("Building KVM")
        for step in steps:
            utils.system(step)


    def _install(self):
        os.chdir(self.srcdir)
        logging.info("Installing KVM userspace")
        if self.repo_type == 1:
            utils.system("make -C qemu install")
        elif self.repo_type == 2:
            utils.system("make install")
        if self.path_to_roms:
            install_roms(self.path_to_roms, self.prefix)
        self.install_unittests()
        create_symlinks(test_bindir=self.test_bindir,
                        prefix=self.prefix,
                        unittest=self.unittest_prefix)


    def install(self):
        self._build()
        self._install()
        self.reload_modules_if_needed()
        if self.save_results:
            virt_utils.archive_as_tarball(self.srcdir, self.results_dir)

class GitRepo(object):
    def __init__(self, installer, prefix,
            srcdir, build_steps=[], repo_param=None):
        params = installer.params
        self.installer = installer
        self.repo = params.get(repo_param or (prefix + '_repo'))
        self.branch = params.get(prefix + '_branch', 'master')
        self.lbranch = params.get(prefix + '_lbranch', 'master')
        self.commit = params.get(prefix + '_commit', None)
        # The config system yields strings, which have to be evalued
        self.patches = eval(params.get(prefix + '_patches', "[]"))
        self.build_steps = build_steps
        self.srcdir = os.path.join(self.installer.srcdir, srcdir)


    def fetch_and_patch(self):
        if not self.repo:
            return
        virt_utils.get_git_branch(self.repo, self.branch, self.srcdir,
                                 self.commit, self.lbranch)
        os.chdir(self.srcdir)
        for patch in self.patches:
            utils.get_file(patch, os.path.join(self.srcdir,
                                               os.path.basename(patch)))
            utils.system('patch -p1 < %s' % os.path.basename(patch))


    def build(self):
        os.chdir(self.srcdir)
        for step in self.build_steps:
            logging.info(step)
            utils.run(step)


class GitInstaller(SourceDirInstaller):
    def _pull_code(self):
        """
        Retrieves code from git repositories.
        """
        params = self.params
        make_jobs = utils.count_cpus()
        cfg = 'PKG_CONFIG_PATH="%s/lib/pkgconfig:%s/share/pkgconfig" ./configure' % (
            self.prefix, self.prefix)

        self.spice_protocol = GitRepo(installer=self, prefix='spice_protocol',
            srcdir='spice-protocol',
            build_steps= ['./autogen.sh',
                          './configure --prefix=%s' % self.prefix,
                          'make clean',
                          'make -j %s' % (make_jobs),
                          'make install'])

        self.spice = GitRepo(installer=self, prefix='spice', srcdir='spice',
            build_steps= ['PKG_CONFIG_PATH="%s/lib/pkgconfig:%s/share/pkgconfig" CXXFLAGS=-Wl,--add-needed ./autogen.sh --prefix=%s' % (self.prefix, self.prefix, self.prefix),
                          'make clean',
                          'make -j %s' % (make_jobs),
                          'make install'])

        self.userspace = GitRepo(installer=self, prefix='user',
            repo_param='user_git_repo', srcdir='kvm_userspace')

        p = os.path.join(self.userspace.srcdir, 'configure')
        self.configure_options = virt_installer.check_configure_options(p)

        cfg = cfg + ' --prefix=%s' % self.prefix
        if "--disable-strip" in self.configure_options:
            cfg += ' --disable-strip'
        if self.extra_configure_options:
            cfg += ' %s' % self.extra_configure_options

        self.userspace.build_steps=[cfg, 'make clean', 'make -j %s' % make_jobs]

        if not self.userspace.repo:
            message = "KVM user git repository path not specified"
            logging.error(message)
            raise error.TestError(message)

        for repo in [self.userspace, self.spice_protocol, self.spice]:
            if not repo.repo:
                continue
            repo.fetch_and_patch()

    def _build(self):
        if self.spice_protocol.repo:
            logging.info('Building Spice-protocol')
            self.spice_protocol.build()

        if self.spice.repo:
            logging.info('Building Spice')
            self.spice.build()

        logging.info('Building KVM userspace code')
        self.userspace.build()


    def _install(self):
        os.chdir(self.userspace.srcdir)
        utils.system('make install')

        if self.path_to_roms:
            install_roms(self.path_to_roms, self.prefix)
        self.install_unittests()
        create_symlinks(test_bindir=self.test_bindir, prefix=self.prefix,
                        bin_list=None,
                        unittest=self.unittest_prefix)


    def install(self):
        self._pull_code()
        self._build()
        self._install()
        self.reload_modules_if_needed()
        if self.save_results:
            virt_utils.archive_as_tarball(self.srcdir, self.results_dir)


class PreInstalledKvm(BaseInstaller):
    def install(self):
        logging.info("Expecting KVM to be already installed. Doing nothing")


class FailedInstaller:
    """
    Class used to be returned instead of the installer if a installation fails

    Useful to make sure no installer object is used if KVM installation fails.
    """
    def __init__(self, msg="KVM install failed"):
        self._msg = msg


    def load_modules(self):
        """Will refuse to load the KVM modules as install failed"""
        raise FailedKvmInstall("KVM modules not available. reason: %s" % (self._msg))


installer_classes = {
    'localsrc': SourceDirInstaller,
    'localtar': SourceDirInstaller,
    'git': GitInstaller,
    'yum': YumInstaller,
    'koji': KojiInstaller,
    'preinstalled': PreInstalledKvm,
}


def _installer_class(install_mode):
    c = installer_classes.get(install_mode)
    if c is None:
        raise error.TestError('Invalid or unsupported'
                              ' install mode: %s' % install_mode)
    return c


def make_installer(params):
    # priority:
    # - 'install_mode' param
    # - 'mode' param
    mode = params.get("install_mode", params.get("mode"))
    klass = _installer_class(mode)
    return klass(mode)
