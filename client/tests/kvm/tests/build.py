import time, os, sys, urllib, re, signal, logging, datetime, glob
from autotest_lib.client.bin import utils, test, os_dep
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


def load_kvm_modules(module_dir=None, load_stock=False, extra_modules=None):
    """
    Unload previously loaded kvm modules, then load modules present on any
    sub directory of module_dir. Function will walk through module_dir until
    it finds the modules.

    @param module_dir: Directory where the KVM modules are located.
    @param load_stock: Whether we are going to load system kernel modules.
    @param extra_modules: List of extra modules to load.
    """
    vendor = "intel"
    if os.system("grep vmx /proc/cpuinfo 1>/dev/null") != 0:
        vendor = "amd"
    logging.debug("Detected CPU vendor as '%s'" %(vendor))

    kill_qemu_processes()

    logging.info("Unloading previously loaded KVM modules")
    kvm_utils.unload_module("kvm")
    if extra_modules:
        for module in extra_modules:
            kvm_utils.unload_module(module)

    if module_dir:
        logging.info("Loading the built KVM modules...")
        kvm_module_path = None
        kvm_vendor_module_path = None
        abort = False

        list_modules = ['kvm.ko', 'kvm-%s.ko' % vendor]
        if extra_modules:
            for extra_module in extra_modules:
                list_modules.append('%s.ko' % extra_module)

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
        utils.system("modprobe kvm")
        utils.system("modprobe kvm-%s" % vendor)
        if extra_modules:
            for module in extra_modules:
                utils.system("modprobe %s" % module)


def create_symlinks(test_bindir, prefix=None, bin_list=None):
    """
    Create symbolic links for the appropriate qemu and qemu-img commands on
    the kvm test bindir.

    @param test_bindir: KVM test bindir
    @param prefix: KVM prefix path
    """
    qemu_path = os.path.join(test_bindir, "qemu")
    qemu_img_path = os.path.join(test_bindir, "qemu-img")
    if os.path.lexists(qemu_path):
        os.unlink(qemu_path)
    if os.path.lexists(qemu_img_path):
        os.unlink(qemu_img_path)

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


class KojiInstaller:
    """
    Class that handles installing KVM from the fedora build service, koji.
    It uses yum to install and remove packages.
    """
    def __init__(self, test, params):
        """
        Class constructor. Sets default paths, and sets up class attributes

        @param test: kvm test object
        @param params: Dictionary with test arguments
        """
        default_koji_cmd = '/usr/bin/koji'
        default_src_pkg = 'qemu'
        default_pkg_list = ['qemu-kvm', 'qemu-kvm-tools']
        default_qemu_bin_paths = ['/usr/bin/qemu-kvm', '/usr/bin/qemu-img']
        default_extra_modules = None

        self.koji_cmd = params.get("koji_cmd", default_koji_cmd)

        # Checking if all required dependencies are available
        os_dep.command("rpm")
        os_dep.command("yum")
        os_dep.command(self.koji_cmd)

        self.src_pkg = params.get("src_pkg", default_src_pkg)
        self.pkg_list = params.get("pkg_list", default_pkg_list)
        self.qemu_bin_paths = params.get("qemu_bin_paths",
                                         default_qemu_bin_paths)
        self.tag = params.get("koji_tag", None)
        self.build = params.get("koji_build", None)
        if self.tag and self.build:
            logging.info("Both tag and build parameters provided, ignoring tag "
                         "parameter...")
        if self.tag and not self.build:
            self.build = self.__get_build()
        if not self.tag and not self.build:
            raise error.TestError("Koji install selected but neither koji_tag "
                                  "nor koji_build parameters provided. Please "
                                  "provide an appropriate tag or build name.")
        # Are we going to load modules?
        load_modules = params.get('load_modules')
        if not load_modules:
            self.load_modules = True
        elif load_modules == 'yes':
            self.load_modules = True
        elif load_modules == 'no':
            self.load_modules = False
        self.extra_modules = params.get("extra_modules", default_extra_modules)

        self.srcdir = test.srcdir
        self.test_bindir = test.bindir


    def __get_build(self):
        """
        Get the source package build name, according to the appropriate tag.
        """
        latest_cmd = "%s latest-pkg %s %s" % (self.koji_cmd, self.tag,
                                              self.src_pkg)
        latest_raw = utils.system_output(latest_cmd,
                                         ignore_status=True).split("\n")
        for line in latest_raw:
            if line.startswith(self.src_pkg):
                build_name = line.split()[0]
        return build_name


    def __clean_previous_installs(self):
        """
        Remove all rpms previously installed.
        """
        kill_qemu_processes()
        removable_packages = ""
        for pkg in self.pkg_list:
            removable_packages += " %s" % pkg

        utils.system("yum remove -y %s" % removable_packages)


    def __get_packages(self):
        """
        Downloads the entire build for the specific build name. It's
        inefficient, but it saves the need of having an NFS share set.

        @todo: Do selective package download using the koji library.
        """
        if not os.path.isdir(self.srcdir):
            os.makedirs(self.srcdir)
        os.chdir(self.srcdir)
        download_cmd = "%s download-build %s" % (self.koji_cmd, self.build)
        utils.system(download_cmd)


    def __install_packages(self):
        """
        Install all relevant packages from the build that was just downloaded.
        """
        os.chdir(self.srcdir)
        installable_packages = ""
        rpm_list = glob.glob("*.rpm")
        arch = utils.get_arch()
        for rpm in rpm_list:
            for pkg in self.pkg_list:
                # Pass to yum only appropriate packages (ie, non-source and
                # compatible with the machine's architecture)
                if (rpm.startswith(pkg) and
                    rpm.endswith(".%s.rpm" % arch) and not
                    rpm.endswith(".src.rpm")):
                    installable_packages += " %s" % rpm

        utils.system("yum install --nogpgcheck -y %s" % installable_packages)


    def __check_installed_binaries(self):
        """
        Make sure the relevant binaries installed actually come from the build
        that was installed.
        """
        source_rpm = "%s.src.rpm" % self.build
        for bin in self.qemu_bin_paths:
            origin_source_rpm = utils.system_output(
                        "rpm -qf --queryformat '%{sourcerpm}' " + bin)
            if origin_source_rpm != source_rpm:
                raise error.TestError("File %s comes from source package %s. "
                                      "It doesn't come from build %s, "
                                      "aborting." % (bin, origin_source_rpm,
                                                     self.build))


    def install(self):
        self.__clean_previous_installs()
        self.__get_packages()
        self.__install_packages()
        self.__check_installed_binaries()
        create_symlinks(test_bindir=self.test_bindir,
                        bin_list=self.qemu_bin_paths)
        if self.load_modules:
            load_kvm_modules(load_stock=True, extra_modules=self.extra_modules)


class SourceDirInstaller:
    """
    Class that handles building/installing KVM directly from a tarball or
    a single source code dir.
    """
    def __init__(self, test, params):
        """
        Initializes class attributes, and retrieves KVM code.

        @param test: kvm test object
        @param params: Dictionary with test arguments
        """
        install_mode = params["mode"]
        srcdir = params.get("srcdir")
        # KVM build prefix
        self.test_bindir = test.bindir
        prefix = os.path.join(test.bindir, 'build')
        self.prefix = os.path.abspath(prefix)
        # Are we going to load modules?
        load_modules = params.get('load_modules')
        if not load_modules:
            self.load_modules = True
        elif load_modules == 'yes':
            self.load_modules = True
        elif load_modules == 'no':
            self.load_modules = False

        if install_mode == 'localsrc':
            if not srcdir:
                raise error.TestError("Install from source directory specified"
                                      "but no source directory provided on the"
                                      "control file.")
            else:
                self.srcdir = srcdir
                self.repo_type = kvm_utils.check_kvm_source_dir(self.srcdir)
                return
        else:
            srcdir = test.srcdir
            if not os.path.isdir(srcdir):
                os.makedirs(srcdir)

        if install_mode == 'release':
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

        elif install_mode == 'snapshot':
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

        elif install_mode == 'localtar':
            tarball = params.get("tarball")
            if not tarball:
                raise error.TestError("KVM Tarball install specified but no"
                                      " tarball provided on control file.")
            logging.info("Installing KVM from a local tarball")
            logging.info("Using tarball %s")
            tarball = utils.unmap_url("/", params.get("tarball"), "/tmp")

        os.chdir(srcdir)
        self.srcdir = os.path.join(srcdir, utils.extract_tarball(tarball))
        self.repo_type = kvm_utils.check_kvm_source_dir(self.srcdir)
        self.extra_modules = params.get('extra_modules', None)
        configure_script = os.path.join(self.srcdir, 'configure')
        self.configure_options = check_configure_options(configure_script)


    def __build(self):
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


    def __install(self):
        os.chdir(self.srcdir)
        logging.info("Installing KVM userspace")
        if self.repo_type == 1:
            utils.system("make -C qemu install")
        elif self.repo_type == 2:
            utils.system("make install")
        create_symlinks(self.test_bindir, self.prefix)


    def __load_modules(self):
        load_kvm_modules(module_dir=self.srcdir,
                         extra_modules=self.extra_modules)


    def install(self):
        self.__build()
        self.__install()
        if self.load_modules:
            self.__load_modules()


class GitInstaller:
    def __init__(self, test, params):
        """
        Initialize class parameters and retrieves code from git repositories.

        @param test: kvm test object.
        @param params: Dictionary with test parameters.
        """
        install_mode = params["mode"]
        srcdir = params.get("srcdir", test.bindir)
        if not srcdir:
            os.makedirs(srcdir)
        self.srcdir = srcdir
        # KVM build prefix
        self.test_bindir = test.bindir
        prefix = os.path.join(test.bindir, 'build')
        self.prefix = os.path.abspath(prefix)
        # Current host kernel directory
        default_host_kernel_source = '/lib/modules/%s/build' % os.uname()[2]
        self.host_kernel_srcdir = params.get('host_kernel_source',
                                             default_host_kernel_source)
        # Extra parameters that can be passed to the configure script
        self.extra_configure_options = params.get('extra_configure_options',
                                                  None)
        # Are we going to load modules?
        load_modules = params.get('load_modules')
        if not load_modules:
            self.load_modules = True
        elif load_modules == 'yes':
            self.load_modules = True
        elif load_modules == 'no':
            self.load_modules = False

        self.extra_modules = params.get("extra_modules", None)

        kernel_repo = params.get("git_repo")
        user_repo = params.get("user_git_repo")
        kmod_repo = params.get("kmod_repo")

        kernel_branch = params.get("kernel_branch", "master")
        user_branch = params.get("user_branch", "master")
        kmod_branch = params.get("kmod_branch", "master")

        kernel_lbranch = params.get("kernel_lbranch", "master")
        user_lbranch = params.get("user_lbranch", "master")
        kmod_lbranch = params.get("kmod_lbranch", "master")

        kernel_tag = params.get("kernel_tag", "HEAD")
        user_tag = params.get("user_tag", "HEAD")
        kmod_tag = params.get("kmod_tag", "HEAD")

        if not kernel_repo:
            message = "KVM git repository path not specified"
            logging.error(message)
            raise error.TestError(message)
        if not user_repo:
            message = "KVM user git repository path not specified"
            logging.error(message)
            raise error.TestError(message)

        kernel_srcdir = os.path.join(srcdir, "kvm")
        kvm_utils.get_git_branch(kernel_repo, kernel_branch, kernel_srcdir,
                                 kernel_tag, kernel_lbranch)
        self.kernel_srcdir = kernel_srcdir

        userspace_srcdir = os.path.join(srcdir, "kvm_userspace")
        kvm_utils.get_git_branch(user_repo, user_branch, userspace_srcdir,
                                 user_tag, user_lbranch)
        self.userspace_srcdir = userspace_srcdir

        if kmod_repo:
            kmod_srcdir = os.path.join (srcdir, "kvm_kmod")
            kvm_utils.get_git_branch(kmod_repo, kmod_branch, kmod_srcdir,
                                     kmod_tag, kmod_lbranch)
            self.kmod_srcdir = kmod_srcdir
        else:
            self.kmod_srcdir = None

        configure_script = os.path.join(self.userspace_srcdir, 'configure')
        self.configure_options = check_configure_options(configure_script)


    def __build(self):
        # Number of concurrent build tasks
        make_jobs = utils.count_cpus()
        if self.kmod_srcdir:
            logging.info('Building KVM modules')
            os.chdir(self.kmod_srcdir)
            utils.system('./configure')
            utils.system('make clean')
            utils.system('make sync LINUX=%s' % self.kernel_srcdir)
            utils.system('make -j %s' % make_jobs)

            logging.info('Building KVM userspace code')
            os.chdir(self.userspace_srcdir)
            cfg = './configure --prefix=%s' % self.prefix
            if "--disable-strip" in self.configure_options:
                cfg += ' --disable-strip'
            if self.extra_configure_options:
                cfg = ' %s' % self.extra_configure_options
            utils.system(cfg)
            utils.system('make clean')
            utils.system('make -j %s' % make_jobs)
        else:
            logging.info('Building KVM modules')
            os.chdir(self.userspace_srcdir)
            cfg = './configure --kerneldir=%s' % self.host_kernel_srcdir
            utils.system(cfg)
            utils.system('make clean')
            utils.system('make -j %s -C kernel LINUX=%s sync' %
                         (make_jobs, self.kernel_srcdir))

            logging.info('Building KVM userspace code')
            # This build method (no kvm-kmod) requires that we execute
            # configure again, but now let's use the full command line.
            cfg += ' --prefix=%s' % self.prefix
            if "--disable-strip" in self.configure_options:
                cfg += ' --disable-strip'
            if self.extra_configure_options:
                cfg += ' %s' % self.extra_configure_options
            steps = [cfg, 'make -j %s' % make_jobs]
            for step in steps:
                utils.system(step)


    def __install(self):
        os.chdir(self.userspace_srcdir)
        utils.system('make install')
        create_symlinks(self.test_bindir, self.prefix)


    def __load_modules(self):
        if self.kmod_srcdir:
            load_kvm_modules(module_dir=self.kmod_srcdir,
                             extra_modules=self.extra_modules)
        else:
            load_kvm_modules(module_dir=self.userspace_srcdir,
                             extra_modules=self.extra_modules)


    def install(self):
        self.__build()
        self.__install()
        if self.load_modules:
            self.__load_modules()


def run_build(test, params, env):
    """
    Installs KVM using the selected install mode. Most install methods will
    take kvm source code, build it and install it to a given location.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Test environment.
    """
    install_mode = params.get("mode")
    srcdir = params.get("srcdir", test.srcdir)
    params["srcdir"] = srcdir

    if install_mode == 'noinstall':
        logging.info("Skipping installation")
        return
    elif install_mode in ['localsrc', 'localtar', 'release', 'snapshot']:
        installer = SourceDirInstaller(test, params)
    elif install_mode == 'git':
        installer = GitInstaller(test, params)
    elif install_mode == 'koji':
        installer = KojiInstaller(test, params)
    else:
        raise error.TestError('Invalid or unsupported'
                              ' install mode: %s' % install_mode)

    installer.install()
