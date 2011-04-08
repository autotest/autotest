import os, logging, datetime, glob
import shutil
from autotest_lib.client.bin import utils, os_dep
from autotest_lib.client.common_lib import error
import kvm_utils


def check_configure_options(script_path):
    """
    Return the list of available options (flags) of a given kvm configure build
    script.

    @param script: Path to the configure script
    """
    abspath = os.path.abspath(script_path)
    help_raw = utils.system_output('%s --help' % abspath, ignore_status=True)
    help_output = help_raw.split("\n")
    option_list = []
    for line in help_output:
        cleaned_line = line.lstrip()
        if cleaned_line.startswith("--"):
            option = cleaned_line.split()[0]
            option = option.split("=")[0]
            option_list.append(option)

    return option_list


def kill_qemu_processes():
    """
    Kills all qemu processes, also kills all processes holding /dev/kvm down.
    """
    logging.debug("Killing any qemu processes that might be left behind")
    utils.system("pkill qemu", ignore_status=True)
    # Let's double check to see if some other process is holding /dev/kvm
    if os.path.isfile("/dev/kvm"):
        utils.system("fuser -k /dev/kvm", ignore_status=True)


def cpu_vendor():
    vendor = "intel"
    if os.system("grep vmx /proc/cpuinfo 1>/dev/null") != 0:
        vendor = "amd"
    logging.debug("Detected CPU vendor as '%s'", vendor)
    return vendor


def _unload_kvm_modules(mod_list):
    logging.info("Unloading previously loaded KVM modules")
    for module in reversed(mod_list):
        utils.unload_module(module)


def _load_kvm_modules(mod_list, module_dir=None, load_stock=False):
    """
    Just load the KVM modules, without killing Qemu or unloading previous
    modules.

    Load modules present on any sub directory of module_dir. Function will walk
    through module_dir until it finds the modules.

    @param module_dir: Directory where the KVM modules are located.
    @param load_stock: Whether we are going to load system kernel modules.
    @param extra_modules: List of extra modules to load.
    """
    if module_dir:
        logging.info("Loading the built KVM modules...")
        kvm_module_path = None
        kvm_vendor_module_path = None
        abort = False

        list_modules = ['%s.ko' % (m) for m in mod_list]

        list_module_paths = []
        for folder, subdirs, files in os.walk(module_dir):
            for module in list_modules:
                if module in files:
                    module_path = os.path.join(folder, module)
                    list_module_paths.append(module_path)

        # We might need to arrange the modules in the correct order
        # to avoid module load problems
        list_modules_load = []
        for module in list_modules:
            for module_path in list_module_paths:
                if os.path.basename(module_path) == module:
                    list_modules_load.append(module_path)

        if len(list_module_paths) != len(list_modules):
            logging.error("KVM modules not found. If you don't want to use the "
                          "modules built by this test, make sure the option "
                          "load_modules: 'no' is marked on the test control "
                          "file.")
            raise error.TestError("The modules %s were requested to be loaded, "
                                  "but the only modules found were %s" %
                                  (list_modules, list_module_paths))

        for module_path in list_modules_load:
            try:
                utils.system("insmod %s" % module_path)
            except Exception, e:
                raise error.TestFail("Failed to load KVM modules: %s" % e)

    if load_stock:
        logging.info("Loading current system KVM modules...")
        for module in mod_list:
            utils.system("modprobe %s" % module)


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


def save_build(build_dir, dest_dir):
    logging.debug('Saving the result of the build on %s', dest_dir)
    base_name = os.path.basename(build_dir)
    tarball_name = base_name + '.tar.bz2'
    os.chdir(os.path.dirname(build_dir))
    utils.system('tar -cjf %s %s' % (tarball_name, base_name))
    shutil.move(tarball_name, os.path.join(dest_dir, tarball_name))


class KvmInstallException(Exception):
    pass


class FailedKvmInstall(KvmInstallException):
    pass


class KvmNotInstalled(KvmInstallException):
    pass


class BaseInstaller(object):
    # default value for load_stock argument
    load_stock_modules = True
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

        self.cpu_vendor = cpu_vendor()

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
            kvm_utils.get_git_branch(test_repo, test_branch, test_srcdir,
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
        _load_kvm_modules(mod_list, load_stock=self.load_stock_modules)


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
        _unload_kvm_modules(mod_list)


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
    load_stock_modules = True
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
            save_build(self.srcdir, self.results_dir)


class KojiInstaller(YumInstaller):
    """
    Class that handles installing KVM from the fedora build service, koji.

    It uses yum to install and remove packages. Packages are specified
    according to the syntax defined in the PkgSpec class.
    """
    load_stock_modules = True
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
            kvm_utils.set_default_koji_tag(self.tag)
        self.koji_pkgs = eval(params.get("koji_pkgs", "[]"))


    def _get_packages(self):
        """
        Downloads the specific arch RPMs for the specific build name.
        """
        koji_client = kvm_utils.KojiClient(cmd=self.koji_cmd)
        for pkg_text in self.koji_pkgs:
            pkg = kvm_utils.KojiPkgSpec(pkg_text)
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
            save_build(self.srcdir, self.results_dir)


    def _get_rpm_names(self):
        all_rpm_names = []
        koji_client = kvm_utils.KojiClient(cmd=self.koji_cmd)
        for pkg_text in self.koji_pkgs:
            pkg = kvm_utils.KojiPkgSpec(pkg_text)
            rpm_names = koji_client.get_pkg_rpm_names(pkg)
            all_rpm_names += rpm_names
        return all_rpm_names


    def _get_rpm_file_names(self):
        all_rpm_file_names = []
        koji_client = kvm_utils.KojiClient(cmd=self.koji_cmd)
        for pkg_text in self.koji_pkgs:
            pkg = kvm_utils.KojiPkgSpec(pkg_text)
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
        self.installed_kmods = False  # it will be set to True in case we
                                      # installed our own modules

        srcdir = params.get("srcdir", None)
        self.path_to_roms = params.get("path_to_rom_images", None)

        if self.install_mode == 'localsrc':
            if srcdir is None:
                raise error.TestError("Install from source directory specified"
                                      "but no source directory provided on the"
                                      "control file.")
            else:
                shutil.copytree(srcdir, self.srcdir)

        if self.install_mode == 'release':
            release_tag = params.get("release_tag")
            release_dir = params.get("release_dir")
            release_listing = params.get("release_listing")
            logging.info("Installing KVM from release tarball")
            if not release_tag:
                release_tag = kvm_utils.get_latest_kvm_release_tag(
                                                                release_listing)
            tarball = os.path.join(release_dir, 'kvm', release_tag,
                                   "kvm-%s.tar.gz" % release_tag)
            logging.info("Retrieving release kvm-%s" % release_tag)
            tarball = utils.unmap_url("/", tarball, "/tmp")

        elif self.install_mode == 'snapshot':
            logging.info("Installing KVM from snapshot")
            snapshot_dir = params.get("snapshot_dir")
            if not snapshot_dir:
                raise error.TestError("Snapshot dir not provided")
            snapshot_date = params.get("snapshot_date")
            if not snapshot_date:
                # Take yesterday's snapshot
                d = (datetime.date.today() -
                     datetime.timedelta(1)).strftime("%Y%m%d")
            else:
                d = snapshot_date
            tarball = os.path.join(snapshot_dir, "kvm-snapshot-%s.tar.gz" % d)
            logging.info("Retrieving kvm-snapshot-%s" % d)
            tarball = utils.unmap_url("/", tarball, "/tmp")

        elif self.install_mode == 'localtar':
            tarball = params.get("tarball")
            if not tarball:
                raise error.TestError("KVM Tarball install specified but no"
                                      " tarball provided on control file.")
            logging.info("Installing KVM from a local tarball")
            logging.info("Using tarball %s")
            tarball = utils.unmap_url("/", params.get("tarball"), "/tmp")

        if self.install_mode in ['release', 'snapshot', 'localtar']:
            utils.extract_tarball_to_dir(tarball, self.srcdir)

        if self.install_mode in ['release', 'snapshot', 'localtar', 'srcdir']:
            self.repo_type = kvm_utils.check_kvm_source_dir(self.srcdir)
            configure_script = os.path.join(self.srcdir, 'configure')
            self.configure_options = check_configure_options(configure_script)


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


    def _install_kmods_old_userspace(self, userspace_path):
        """
        Run the module install command.

        This is for the "old userspace" code, that contained a 'kernel' subdirectory
        with the kmod build code.

        The code would be much simpler if we could specify the module install
        path as parameter to the toplevel Makefile. As we can't do that and
        the module install code doesn't use --prefix, we have to call
        'make -C kernel install' directly, setting the module directory
        parameters.

        If the userspace tree doens't have a 'kernel' subdirectory, the
        module install step will be skipped.

        @param userspace_path: the path the kvm-userspace directory
        """
        kdir = os.path.join(userspace_path, 'kernel')
        if os.path.isdir(kdir):
            os.chdir(kdir)
            # INSTALLDIR is the target dir for the modules
            # ORIGMODDIR is the dir where the old modules will be removed. we
            #            don't want to mess with the system modules, so set it
            #            to a non-existing directory
            utils.system('make install INSTALLDIR=%s ORIGMODDIR=/tmp/no-old-modules' % (self.mod_install_dir))
            self.installed_kmods = True


    def _install_kmods(self, kmod_path):
        """Run the module install command for the kmod-kvm repository

        @param kmod_path: the path to the kmod-kvm.git working copy
        """
        os.chdir(kmod_path)
        utils.system('make modules_install DESTDIR=%s' % (self.mod_install_dir))
        self.installed_kmods = True


    def _install(self):
        os.chdir(self.srcdir)
        logging.info("Installing KVM userspace")
        if self.repo_type == 1:
            utils.system("make -C qemu install")
            self._install_kmods_old_userspace(self.srcdir)
        elif self.repo_type == 2:
            utils.system("make install")
        if self.path_to_roms:
            install_roms(self.path_to_roms, self.prefix)
        self.install_unittests()
        create_symlinks(test_bindir=self.test_bindir,
                        prefix=self.prefix,
                        unittest=self.unittest_prefix)


    def _load_modules(self, mod_list):
        # load the installed KVM modules in case we installed them
        # ourselves. Otherwise, just load the system modules.
        if self.installed_kmods:
            logging.info("Loading installed KVM modules")
            _load_kvm_modules(mod_list, module_dir=self.mod_install_dir)
        else:
            logging.info("Loading stock KVM modules")
            _load_kvm_modules(mod_list, load_stock=True)


    def install(self):
        self._build()
        self._install()
        self.reload_modules_if_needed()
        if self.save_results:
            save_build(self.srcdir, self.results_dir)


class GitInstaller(SourceDirInstaller):
    def _pull_code(self):
        """
        Retrieves code from git repositories.
        """
        params = self.params

        kernel_repo = params.get("git_repo")
        user_repo = params.get("user_git_repo")
        kmod_repo = params.get("kmod_repo")

        kernel_branch = params.get("kernel_branch", "master")
        user_branch = params.get("user_branch", "master")
        kmod_branch = params.get("kmod_branch", "master")

        kernel_lbranch = params.get("kernel_lbranch", "master")
        user_lbranch = params.get("user_lbranch", "master")
        kmod_lbranch = params.get("kmod_lbranch", "master")

        kernel_commit = params.get("kernel_commit", None)
        user_commit = params.get("user_commit", None)
        kmod_commit = params.get("kmod_commit", None)

        kernel_patches = eval(params.get("kernel_patches", "[]"))
        user_patches = eval(params.get("user_patches", "[]"))
        kmod_patches = eval(params.get("user_patches", "[]"))

        if not user_repo:
            message = "KVM user git repository path not specified"
            logging.error(message)
            raise error.TestError(message)

        userspace_srcdir = os.path.join(self.srcdir, "kvm_userspace")
        kvm_utils.get_git_branch(user_repo, user_branch, userspace_srcdir,
                                 user_commit, user_lbranch)
        self.userspace_srcdir = userspace_srcdir

        if user_patches:
            os.chdir(self.userspace_srcdir)
            for patch in user_patches:
                utils.get_file(patch, os.path.join(self.userspace_srcdir,
                                                   os.path.basename(patch)))
                utils.system('patch -p1 %s' % os.path.basename(patch))

        if kernel_repo:
            kernel_srcdir = os.path.join(self.srcdir, "kvm")
            kvm_utils.get_git_branch(kernel_repo, kernel_branch, kernel_srcdir,
                                     kernel_commit, kernel_lbranch)
            self.kernel_srcdir = kernel_srcdir
            if kernel_patches:
                os.chdir(self.kernel_srcdir)
                for patch in kernel_patches:
                    utils.get_file(patch, os.path.join(self.userspace_srcdir,
                                                       os.path.basename(patch)))
                    utils.system('patch -p1 %s' % os.path.basename(patch))
        else:
            self.kernel_srcdir = None

        if kmod_repo:
            kmod_srcdir = os.path.join (self.srcdir, "kvm_kmod")
            kvm_utils.get_git_branch(kmod_repo, kmod_branch, kmod_srcdir,
                                     kmod_commit, kmod_lbranch)
            self.kmod_srcdir = kmod_srcdir
            if kmod_patches:
                os.chdir(self.kmod_srcdir)
                for patch in kmod_patches:
                    utils.get_file(patch, os.path.join(self.userspace_srcdir,
                                                       os.path.basename(patch)))
                    utils.system('patch -p1 %s' % os.path.basename(patch))
        else:
            self.kmod_srcdir = None

        configure_script = os.path.join(self.userspace_srcdir, 'configure')
        self.configure_options = check_configure_options(configure_script)


    def _build(self):
        make_jobs = utils.count_cpus()
        cfg = './configure'
        if self.kmod_srcdir:
            logging.info('Building KVM modules')
            os.chdir(self.kmod_srcdir)
            module_build_steps = [cfg,
                                  'make clean',
                                  'make sync LINUX=%s' % self.kernel_srcdir,
                                  'make']
        elif self.kernel_srcdir:
            logging.info('Building KVM modules')
            os.chdir(self.userspace_srcdir)
            cfg += ' --kerneldir=%s' % self.host_kernel_srcdir
            module_build_steps = [cfg,
                            'make clean',
                            'make -C kernel LINUX=%s sync' % self.kernel_srcdir]
        else:
            module_build_steps = []

        for step in module_build_steps:
            utils.run(step)

        logging.info('Building KVM userspace code')
        os.chdir(self.userspace_srcdir)
        cfg += ' --prefix=%s' % self.prefix
        if "--disable-strip" in self.configure_options:
            cfg += ' --disable-strip'
        if self.extra_configure_options:
            cfg += ' %s' % self.extra_configure_options
        utils.system(cfg)
        utils.system('make clean')
        utils.system('make -j %s' % make_jobs)


    def _install(self):
        if self.kernel_srcdir:
            os.chdir(self.userspace_srcdir)
            # the kernel module install with --prefix doesn't work, and DESTDIR
            # wouldn't work for the userspace stuff, so we clear WANT_MODULE:
            utils.system('make install WANT_MODULE=')
            # and install the old-style-kmod modules manually:
            self._install_kmods_old_userspace(self.userspace_srcdir)
        elif self.kmod_srcdir:
            # if we have a kmod repository, it is easier:
            # 1) install userspace:
            os.chdir(self.userspace_srcdir)
            utils.system('make install')
            # 2) install kmod:
            self._install_kmods(self.kmod_srcdir)
        else:
            # if we don't have kmod sources, we just install
            # userspace:
            os.chdir(self.userspace_srcdir)
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
            save_build(self.srcdir, self.results_dir)


class PreInstalledKvm(BaseInstaller):
    # load_modules() will use the stock modules:
    load_stock_modules = True
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
    'release': SourceDirInstaller,
    'snapshot': SourceDirInstaller,
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
