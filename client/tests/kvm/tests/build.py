import time, os, sys, urllib, re, signal, logging, datetime
from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error
import kvm_utils


def load_kvm_modules(module_dir):
    """
    Unload previously loaded kvm modules, then load modules present on any
    sub directory of module_dir. Function will walk through module_dir until
    it finds the modules.

    @param module_dir: Directory where the KVM modules are located.
    """
    vendor = "intel"
    if os.system("grep vmx /proc/cpuinfo 1>/dev/null") != 0:
        vendor = "amd"
    logging.debug("Detected CPU vendor as '%s'" %(vendor))

    logging.debug("Killing any qemu processes that might be left behind")
    utils.system("pkill qemu", ignore_status=True)

    logging.info("Unloading previously loaded KVM modules")
    kvm_utils.unload_module("kvm")
    if utils.module_is_loaded("kvm"):
        message = "Failed to remove old KVM modules"
        logging.error(message)
        raise error.TestError(message)

    logging.info("Loading new KVM modules...")
    kvm_module_path = None
    kvm_vendor_module_path = None
    # Search for the built KVM modules
    for folder, subdirs, files in os.walk(module_dir):
        if "kvm.ko" in files:
            kvm_module_path = os.path.join(folder, "kvm.ko")
            kvm_vendor_module_path = os.path.join(folder, "kvm-%s.ko" % vendor)
    abort = False
    if not kvm_module_path:
        logging.error("Need a directory containing both kernel module and "
                      "userspace sources.")
        logging.error("If you are trying to build only KVM userspace and use "
                      "the KVM modules you have already loaded, put "
                      "'load_modules': 'no' on the control file 'params' "
                      "dictionary.")
        raise error.TestError("Could not find a built kvm.ko module on the "
                              "source dir.")
    elif not os.path.isfile(kvm_vendor_module_path):
        logging.error("Could not find KVM (%s) module that was supposed to be"
                      " built on the source dir", vendor)
        abort = True
    if abort:
        raise error.TestError("Could not load KVM modules.")
    utils.system("/sbin/insmod %s" % kvm_module_path)
    time.sleep(1)
    utils.system("/sbin/insmod %s" % kvm_vendor_module_path)

    if not utils.module_is_loaded("kvm"):
        message = "Failed to load the KVM modules built for the test"
        logging.error(message)
        raise error.TestError(message)


def create_symlinks(test_bindir, prefix):
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
    kvm_qemu = os.path.join(prefix, "bin", "qemu-system-x86_64")
    if not os.path.isfile(kvm_qemu):
        raise error.TestError('Invalid qemu path')
    kvm_qemu_img = os.path.join(prefix, "bin", "qemu-img")
    if not os.path.isfile(kvm_qemu_img):
        raise error.TestError('Invalid qemu-img path')
    os.symlink(kvm_qemu, qemu_path)
    os.symlink(kvm_qemu_img, qemu_img_path)


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
            tarball = os.path.join(release_dir, "kvm-%s.tar.gz" % release_tag)
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


    def __build(self):
        os.chdir(self.srcdir)
        # For testing purposes, it's better to build qemu binaries with
        # debugging symbols, so we can extract more meaningful stack traces.
        cfg = "./configure --disable-strip --prefix=%s" % self.prefix
        steps = [cfg, "make clean", "make -j %s" % (utils.count_cpus() + 1)]
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
        load_kvm_modules(self.srcdir)


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
        # Are we going to load modules?
        load_modules = params.get('load_modules')
        if not load_modules:
            self.load_modules = True
        elif load_modules == 'yes':
            self.load_modules = True
        elif load_modules == 'no':
            self.load_modules = False

        kernel_repo = params.get("git_repo")
        user_repo = params.get("user_git_repo")
        kmod_repo = params.get("kmod_repo")

        branch = params.get("git_branch", "master")
        lbranch = params.get("lbranch")

        tag = params.get("git_tag", "HEAD")
        user_tag = params.get("user_git_tag", "HEAD")
        kmod_tag = params.get("kmod_git_tag", "HEAD")

        if not kernel_repo:
            message = "KVM git repository path not specified"
            logging.error(message)
            raise error.TestError(message)
        if not user_repo:
            message = "KVM user git repository path not specified"
            logging.error(message)
            raise error.TestError(message)

        kernel_srcdir = os.path.join(srcdir, "kvm")
        kvm_utils.get_git_branch(kernel_repo, branch, kernel_srcdir, tag,
                                 lbranch)
        self.kernel_srcdir = kernel_srcdir

        userspace_srcdir = os.path.join(srcdir, "kvm_userspace")
        kvm_utils.get_git_branch(user_repo, branch, userspace_srcdir, user_tag,
                                 lbranch)
        self.userspace_srcdir = userspace_srcdir

        if kmod_repo:
            kmod_srcdir = os.path.join (srcdir, "kvm_kmod")
            kvm_utils.get_git_branch(kmod_repo, branch, kmod_srcdir, user_tag,
                                     lbranch)
            self.kmod_srcdir = kmod_srcdir


    def __build(self):
        if self.kmod_srcdir:
            logging.info('Building KVM modules')
            os.chdir(self.kmod_srcdir)
            utils.system('./configure')
            utils.system('make clean')
            utils.system('make sync LINUX=%s' % self.kernel_srcdir)
            utils.system('make -j %s' % utils.count_cpus())
            logging.info('Building KVM userspace code')
            os.chdir(self.userspace_srcdir)
            utils.system('./configure --disable-strip --prefix=%s' %
                         self.prefix)
            utils.system('make clean')
            utils.system('make -j %s' % utils.count_cpus())
        else:
            os.chdir(self.userspace_srcdir)
            utils.system('./configure --disable-strip --prefix=%s' %
                         self.prefix)
            logging.info('Building KVM modules')
            utils.system('make clean')
            utils.system('make -C kernel LINUX=%s sync' % self.kernel_srcdir)
            logging.info('Building KVM userspace code')
            utils.system('make -j %s' % utils.count_cpus())


    def __install(self):
        os.chdir(self.userspace_srcdir)
        utils.system('make install')
        create_symlinks(self.test_bindir, self.prefix)


    def __load_modules(self):
        if self.kmod_srcdir:
            load_kvm_modules(self.kmod_srcdir)
        else:
            load_kvm_modules(self.userspace_srcdir)


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
    else:
        raise error.TestError('Invalid or unsupported'
                              ' install mode: %s' % install_mode)

    installer.install()
