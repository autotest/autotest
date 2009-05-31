import time, os, sys, urllib, re, signal, logging, datetime
from datetime import *
from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error
import kvm_utils


def run_kvm_install(test, params, env):
    """
    KVM build test. Installs KVM using the selected install mode. Most install
    methods will take kvm source code, build it and install it to a given
    location.

    @param test: kvm test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    install_mode = params.get("mode")
    logging.info("Selected installation mode: %s" % install_mode)

    srcdir = params.get("srcdir", test.srcdir)
    if not os.path.exists(srcdir):
        os.mkdir(srcdir)

    # do not install
    if install_mode == "noinstall":
        logging.info("Skipping installation")

    # install from git
    elif install_mode == "git":
        repo = params.get("git_repo")
        user_repo = params.get("user_git_repo")
        branch = params.get("git_branch", "master")
        lbranch = params.get("lbranch")
        tag = params.get("git_tag", "HEAD")
        user_tag = params.get("user_git_tag", "HEAD")
        if not repo:
            message = "KVM git repository path not specified"
            logging.error(message)
            raise error.TestError(message)
        if not user_repo:
            message = "KVM user git repository path not specified"
            logging.error(message)
            raise error.TestError(message)
        __install_kvm_from_git(test, srcdir, repo, user_repo, branch, tag,
                               user_tag, lbranch)

    # install from release
    elif install_mode == "release":
        release_dir = params.get("release_dir")
        release_tag = params.get("release_tag")
        if not release_dir:
            message = "Release dir not specified"
            logging.error(message)
            raise error.TestError(message)
        __install_kvm_release(test, srcdir, release_dir, release_tag)

    # install from snapshot
    elif install_mode == "snapshot":
        snapshot_dir = params.get("snapshot_dir")
        snapshot_date = params.get("snapshot_date")
        if not snapshot_dir:
            message = "Snapshot dir not specified"
            logging.error(message)
            raise error.TestError(message)
        __install_kvm_from_snapshot(test, srcdir, snapshot_dir, snapshot_date)

    # install from tarball
    elif install_mode == "localtar":
        tarball = params.get("tarball")
        if not tarball:
            message = "Local tarball filename not specified"
            logging.error(message)
            raise error.TestError(message)
        __install_kvm_from_local_tarball(test, srcdir, tarball)

    # install from local sources
    elif install_mode == "localsrc":
        __install_kvm(test, srcdir)

    # invalid installation mode
    else:
        message = "Invalid installation mode: '%s'" % install_mode
        logging.error(message)
        raise error.TestError(message)

    # load kvm modules (unless requested not to)
    if params.get('load_modules', "yes") == "yes":
        __load_kvm_modules()
    else:
        logging.info("user requested not to load kvm modules")

def __cleanup_dir(dir):
    # only alerts if src directory is not empty
    for root, dirs, files in os.walk(dir):
        if dirs or files:
            message = "Directory \'%s\' is not empty" % dir
            logging.error(message)
            raise error.TestError(message)

def __install_kvm_release(test, srcdir, release_dir, release_tag):
    if not release_tag:
        try:
            # look for the latest release in the web
            page_url = os.path.join(release_dir, "showfiles.php")
            local_web_page = utils.unmap_url("/", page_url, "/tmp")
            f = open(local_web_page, "r")
            data = f.read()
            f.close()
            rx = re.compile("package_id=(\d+).*\>kvm\<", re.IGNORECASE)
            matches = rx.findall(data)
            package_id = matches[0]
            #package_id = 209008
            rx = re.compile("package_id=%s.*release_id=\d+\">(\d+)" %
                            package_id, re.IGNORECASE)
            matches = rx.findall(data)
            # the first match contains the latest release tag
            release_tag = matches[0]
        except Exception, e:
            message = "Could not fetch latest KVM release tag (%s)" % str(e)
            logging.error(message)
            raise error.TestError(message)

    logging.info("Installing release %s (kvm-%s)" % (release_tag, release_tag))
    tarball = os.path.join(release_dir, "kvm-%s.tar.gz" % release_tag)
    tarball = utils.unmap_url("/", tarball, "/tmp")
    __install_kvm_from_local_tarball(test, srcdir, tarball)


def __install_kvm_from_git(test, srcdir, repo, user_repo, branch, tag,
                           user_tag, lbranch):
    local_git_srcdir = os.path.join(srcdir, "kvm")
    if not os.path.exists(local_git_srcdir):
        os.mkdir(local_git_srcdir)
    local_user_git_srcdir = os.path.join(srcdir, "kvmuser")
    if not os.path.exists(local_user_git_srcdir):
        os.mkdir(local_user_git_srcdir)

    __get_git_branch(repo, branch, local_git_srcdir, tag, lbranch)
    __get_git_branch(user_repo, branch, local_user_git_srcdir, user_tag,
                     lbranch)
    utils.system("cd %s && ./configure &&  make -C kernel LINUX=%s sync" %
                 (local_user_git_srcdir, local_git_srcdir))
    __install_kvm(test, local_user_git_srcdir)


def __get_git_branch(repository, branch, srcdir, commit=None, lbranch=None):
    logging.info("Getting sources from git <REP=%s BRANCH=%s TAG=%s> to local"
                 "directory <%s>" % (repository, branch, commit, srcdir))
    pwd = os.getcwd()
    os.chdir(srcdir)
    if os.path.exists(".git"):
        utils.system("git reset --hard")
    else:
        utils.system("git init")

    if not lbranch:
        lbranch = branch

    utils.system("git fetch -q -f -u -t %s %s:%s" %
                 (repository, branch, lbranch))
    utils.system("git checkout %s" % lbranch)
    if commit:
        utils.system("git checkout %s" % commit)

    h = utils.system_output('git log --pretty=format:"%H" -1')
    desc = utils.system_output("git describe")
    logging.info("Commit hash for %s is %s (%s)" % (repository, h.strip(),
                                                    desc))
    os.chdir(pwd)


def __install_kvm_from_snapshot(test, srcdir, snapshot_dir ,snapshot_date):
    logging.info("Source snapshot dir: %s" % snaphost_dir)
    logging.info("Source snapshot date: %s" % snapshot_date)

    if not snapshot_date:
        # takes yesterday's snapshot
        d = (datetime.date.today() - datetime.timedelta(1)).strftime("%Y%m%d")
    else:
        d = snapshot_date

    tarball = os.path.join(snaphost_dir, "kvm-snapshot-%s.tar.gz" % d)
    logging.info("Tarball url: %s" % tarball)
    tarball = utils.unmap_url("/", tarball, "/tmp")
    __install_kvm_from_local_tarball(test, srcdir, tarball)


def __install_kvm_from_local_tarball(test, srcdir, tarball):
    pwd = os.getcwd()
    os.chdir(srcdir)
    newdir = utils.extract_tarball(tarball)
    if newdir:
        srcdir = os.path.join(srcdir, newdir)
    os.chdir(pwd)
    __install_kvm(test, srcdir)


def __load_kvm_modules():
    logging.info("Detecting CPU vendor...")
    vendor = "intel"
    if os.system("grep vmx /proc/cpuinfo 1>/dev/null") != 0:
        vendor = "amd"
    logging.info("Detected CPU vendor as '%s'" %(vendor))

    #if self.config.load_modules == "yes":
    # remove existing in kernel kvm modules
    logging.info("Unloading loaded KVM modules (if present)...")
    #utils.system("pkill qemu 1>/dev/null 2>&1", ignore_status=True)
    utils.system("pkill qemu", ignore_status=True)
    #if utils.system("grep kvm_%s /proc/modules 1>/dev/null" % vendor,
    #                ignore_status=True) == 0:
    utils.system("/sbin/modprobe -r kvm_%s" % vendor, ignore_status=True)
    #if utils.system("grep kvm /proc/modules 1>/dev/null",
    #                ignore_status=True) == 0:
    utils.system("/sbin/modprobe -r kvm", ignore_status=True)

    if utils.system("grep kvm /proc/modules 1>/dev/null",
                    ignore_status=True) == 0:
        message = "Failed to remove old KVM modules"
        logging.error(message)
        raise error.TestError(message)

    logging.info("Loading new KVM modules...")
    os.chdir("kernel")
    if os.path.exists("x86"):
        os.chdir("x86")
    utils.system("/sbin/insmod ./kvm.ko && sleep 1 && /sbin/insmod"
                 "./kvm-%s.ko" % vendor)

    #elif self.config.load_modules == "no":
        #logging.info("user requested not to load kvm modules")

    ### no matter if new kvm modules are to be loaded or not
    ### make sure there are kvm modules installed.
    if utils.system("grep kvm_%s /proc/modules 1>/dev/null" %(vendor),
                    ignore_status=True) != 0:
        message = "Failed to load KVM modules"
        logging.error(message)
        raise error.TestError(message)

def __install_kvm(test, srcdir):
    # create destination dir

    kvm_build_dir = os.path.join(srcdir, '..', '..', 'build')
    kvm_build_dir = os.path.abspath(kvm_build_dir)

    if not os.path.exists(kvm_build_dir):
        os.mkdir(kvm_build_dir)

    # change to source dir
    os.chdir(srcdir)

    # start working...
    logging.info("Building KVM...")

    def run(cmd, title, timeout):
        (status, pid, output) = kvm_utils.run_bg(cmd, None, logging.info,
                                                 '(%s)' % title,
                                                 timeout=timeout)
        if status != 0:
            kvm_utils.safe_kill(pid, signal.SIGTERM)
            raise error.TestFail, "'%s' failed" % cmd

    # configure + make
    run("./configure --prefix=%s" % kvm_build_dir, "configure", 30)
    run("make clean", "make clean", 30)
    run("make", "make", 1200)

    # make bios binaries if missing
    if not os.path.exists('qemu/pc-bios/bios.bin'):
        run("make -C bios", "make bios", 60)
        run("make -C vgabios", "make vgabios", 60)
        run("make -C extboot", "make extboot", 60)
        cp1 = "cp -f bios/BIOS-bochs-latest qemu/pc-bios/bios.bin"
        cp2 = "cp -f vgabios/VGABIOS-lgpl-latest.bin qemu/pc-bios/vgabios.bin"
        cp3 = "cp -f vgabios/VGABIOS-lgpl-latest.cirrus.bin qemu/pc-bios/vgabios-cirrus.bin"
        cp4 = "cp -f extboot/extboot.bin qemu/pc-bios/extboot.bin"
        cmd = "&& ".join([cp1, cp2, cp3, cp4])
        run(cmd, "copy bios binaries", 30)

    # install from qemu directory
    run("make -C qemu install", "(make install) ", 120)

    # create symlinks
    qemu_path = os.path.join(test.bindir, "qemu")
    qemu_img_path = os.path.join(test.bindir, "qemu-img")
    if os.path.lexists(qemu_path):
        os.unlink(qemu_path)
    if os.path.lexists(qemu_img_path):
        os.unlink(qemu_img_path)
    kvm_qemu = os.path.join(kvm_build_dir, "bin", "qemu-system-x86_64")
    kvm_qemu_img = os.path.join(kvm_build_dir, "bin", "qemu-img")
    os.symlink(kvm_qemu, qemu_path)
    os.symlink(kvm_qemu_img, qemu_img_path)

    logging.info("Done building and installing KVM")
