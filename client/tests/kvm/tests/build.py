import time, os, sys, urllib, re, signal, logging, datetime, glob, ConfigParser
import shutil
try:
    import koji
    KOJI_INSTALLED = True
except ImportError:
    KOJI_INSTALLED = False
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
    utils.unload_module("kvm")
    if extra_modules:
        for module in extra_modules:
            utils.unload_module(module)

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


def save_build(build_dir, dest_dir):
    logging.debug('Saving the result of the build on %s', dest_dir)
    base_name = os.path.basename(build_dir)
    tarball_name = base_name + '.tar.bz2'
    os.chdir(os.path.dirname(build_dir))
    utils.system('tar -cjf %s %s' % (tarball_name, base_name))
    shutil.move(tarball_name, os.path.join(dest_dir, tarball_name))


class BaseInstaller(object):
    def __init__(self, test, params):
        load_modules = params.get('load_modules', 'no')
        if not load_modules or load_modules == 'yes':
            self.load_modules = True
        elif load_modules == 'no':
            self.load_modules = False
        default_extra_modules = str(None)
        self.extra_modules = eval(params.get("extra_modules",
                                             default_extra_modules))

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


class YumInstaller(BaseInstaller):
    """
    Class that uses yum to install and remove packages.
    """
    def __init__(self, test, params):
        super(YumInstaller, self).__init__(test, params)
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
        self._clean_previous_installs()
        self._get_packages()
        self._install_packages()
        create_symlinks(test_bindir=self.test_bindir,
                        bin_list=self.qemu_bin_paths)
        if self.load_modules:
            load_kvm_modules(load_stock=True, extra_modules=self.extra_modules)
        if self.save_results:
            save_build(self.srcdir, self.results_dir)


class KojiInstaller(YumInstaller):
    """
    Class that handles installing KVM from the fedora build service, koji.
    It uses yum to install and remove packages.
    """
    def __init__(self, test, params):
        """
        Initialize koji/brew session.

        @param test: kvm test object
        @param params: Dictionary with test arguments
        """
        super(KojiInstaller, self).__init__(test, params)

        default_koji_cmd = '/usr/bin/koji'
        default_src_pkg = 'qemu'

        self.koji_cmd = params.get("koji_cmd", default_koji_cmd)
        self.src_pkg = params.get("src_pkg", default_src_pkg)

        # Checking if all required dependencies are available
        os_dep.command(self.koji_cmd)

        config_map = {'/usr/bin/koji': '/etc/koji.conf',
                      '/usr/bin/brew': '/etc/brewkoji.conf'}
        config_file = config_map[self.koji_cmd]
        base_name = os.path.basename(self.koji_cmd)
        if os.access(config_file, os.F_OK):
            f = open(config_file)
            config = ConfigParser.ConfigParser()
            config.readfp(f)
            f.close()
        else:
            raise error.TestError('Configuration file %s missing or with wrong '
                                  'permissions' % config_file)

        if config.has_section(base_name):
            self.koji_options = {}
            session_options = {}
            server = None
            for name, value in config.items(base_name):
                if name in ('user', 'password', 'debug_xmlrpc', 'debug'):
                    session_options[name] = value
                self.koji_options[name] = value
            self.session = koji.ClientSession(self.koji_options['server'],
                                              session_options)
        else:
            raise error.TestError('Koji config file %s does not have a %s '
                                  'session' % (config_file, base_name))

        self.tag = params.get("koji_tag", None)
        self.build = params.get("koji_build", None)
        if self.build and self.build.isdigit():
            self.build = int(self.build)
        if self.tag and self.build:
            logging.info("Both tag and build parameters provided, ignoring tag "
                         "parameter...")
        if not self.tag and not self.build:
            raise error.TestError("Koji install selected but neither koji_tag "
                                  "nor koji_build parameters provided. Please "
                                  "provide an appropriate tag or build name.")


    def _get_packages(self):
        """
        Downloads the specific arch RPMs for the specific build name.
        """
        if self.build is None:
            try:
                builds = self.session.listTagged(self.tag, latest=True,
                                                 package=self.src_pkg)
            except koji.GenericError, e:
                raise error.TestError("Error finding latest build for tag %s: "
                                      "%s" % (self.tag, e))
            if not builds:
                raise error.TestError("Tag %s has no builds of %s" %
                                      (self.tag, self.src_pkg))
            info = builds[0]
        else:
            info = self.session.getBuild(self.build)

        if info is None:
            raise error.TestError('No such brew/koji build: %s' %
                                  self.build)
        rpms = self.session.listRPMs(buildID=info['id'],
                                     arches=utils.get_arch())
        if not rpms:
            raise error.TestError("No %s packages available for %s" %
                                  utils.get_arch(), koji.buildLabel(info))
        for rpm in rpms:
            rpm_name = koji.pathinfo.rpm(rpm)
            url = ("%s/%s/%s/%s/%s" % (self.koji_options['pkgurl'],
                                       info['package_name'],
                                       info['version'], info['release'],
                                       rpm_name))
            utils.get_file(url,
                           os.path.join(self.srcdir, os.path.basename(url)))


    def install(self):
        super(KojiInstaller, self)._clean_previous_installs()
        self._get_packages()
        super(KojiInstaller, self)._install_packages()
        create_symlinks(test_bindir=self.test_bindir,
                        bin_list=self.qemu_bin_paths)
        if self.load_modules:
            load_kvm_modules(load_stock=True, extra_modules=self.extra_modules)
        if self.save_results:
            save_build(self.srcdir, self.results_dir)


class SourceDirInstaller(BaseInstaller):
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
        super(SourceDirInstaller, self).__init__(test, params)

        install_mode = params["mode"]
        srcdir = params.get("srcdir", None)

        if install_mode == 'localsrc':
            if srcdir is None:
                raise error.TestError("Install from source directory specified"
                                      "but no source directory provided on the"
                                      "control file.")
            else:
                shutil.copytree(srcdir, self.srcdir)

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

        if install_mode in ['release', 'snapshot', 'localtar']:
            utils.extract_tarball_to_dir(tarball, self.srcdir)

        if install_mode in ['release', 'snapshot', 'localtar', 'srcdir']:
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


    def _install(self):
        os.chdir(self.srcdir)
        logging.info("Installing KVM userspace")
        if self.repo_type == 1:
            utils.system("make -C qemu install")
        elif self.repo_type == 2:
            utils.system("make install")
        create_symlinks(self.test_bindir, self.prefix)


    def _load_modules(self):
        load_kvm_modules(module_dir=self.srcdir,
                         extra_modules=self.extra_modules)


    def install(self):
        self._build()
        self._install()
        if self.load_modules:
            self._load_modules()
        if self.save_results:
            save_build(self.srcdir, self.results_dir)


class GitInstaller(SourceDirInstaller):
    def __init__(self, test, params):
        """
        Initialize class parameters and retrieves code from git repositories.

        @param test: kvm test object.
        @param params: Dictionary with test parameters.
        """
        super(GitInstaller, self).__init__(test, params)

        kernel_repo = params.get("git_repo")
        user_repo = params.get("user_git_repo")
        kmod_repo = params.get("kmod_repo")
        test_repo = params.get("test_git_repo")

        kernel_branch = params.get("kernel_branch", "master")
        user_branch = params.get("user_branch", "master")
        kmod_branch = params.get("kmod_branch", "master")
        test_branch = params.get("test_branch", "master")

        kernel_lbranch = params.get("kernel_lbranch", "master")
        user_lbranch = params.get("user_lbranch", "master")
        kmod_lbranch = params.get("kmod_lbranch", "master")
        test_lbranch = params.get("test_lbranch", "master")

        kernel_commit = params.get("kernel_commit", None)
        user_commit = params.get("user_commit", None)
        kmod_commit = params.get("kmod_commit", None)
        test_commit = params.get("test_commit", None)

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
        self.modules_build_succeed = False
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

        try:
            if module_build_steps:
                for step in module_build_steps:
                    utils.run(step)
                self.modules_build_succeed = True
        except error.CmdError, e:
            logging.error("KVM modules build failed to build: %s" % e)

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

        self.unittest_prefix = None
        if self.unittest_cfg:
            os.chdir(os.path.dirname(os.path.dirname(self.unittest_cfg)))
            utils.system('./configure --prefix=%s' % self.prefix)
            utils.system('make')
            utils.system('make install')
            self.unittest_prefix = os.path.join(self.prefix, 'share', 'qemu',
                                                'tests')


    def _install(self):
        os.chdir(self.userspace_srcdir)
        utils.system('make install')
        create_symlinks(test_bindir=self.test_bindir, prefix=self.prefix,
                        bin_list=None,
                        unittest=self.unittest_prefix)


    def _load_modules(self):
        if self.kmod_srcdir and self.modules_build_succeed:
            load_kvm_modules(module_dir=self.kmod_srcdir,
                             extra_modules=self.extra_modules)
        elif self.kernel_srcdir and self.modules_build_succeed:
            load_kvm_modules(module_dir=self.userspace_srcdir,
                             extra_modules=self.extra_modules)
        else:
            logging.info("Loading stock KVM modules")
            load_kvm_modules(load_stock=True,
                             extra_modules=self.extra_modules)


    def install(self):
        self._build()
        self._install()
        if self.load_modules:
            self._load_modules()
        if self.save_results:
            save_build(self.srcdir, self.results_dir)


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

    if install_mode in ['localsrc', 'localtar', 'release', 'snapshot']:
        installer = SourceDirInstaller(test, params)
    elif install_mode == 'git':
        installer = GitInstaller(test, params)
    elif install_mode == 'yum':
        installer = YumInstaller(test, params)
    elif install_mode == 'koji':
        if KOJI_INSTALLED:
            installer = KojiInstaller(test, params)
        else:
            raise error.TestError('Koji install selected but koji/brew are not '
                                  'installed')
    else:
        raise error.TestError('Invalid or unsupported'
                              ' install mode: %s' % install_mode)

    installer.install()
