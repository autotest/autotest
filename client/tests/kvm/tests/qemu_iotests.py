import os
from autotest_lib.client.common_lib import git, error
from autotest_lib.client.bin import utils
from autotest_lib.client.virt import virt_utils


@error.context_aware
def run_qemu_iotests(test, params, env):
    """
    Fetch from git and run qemu-iotests using the qemu binaries under test.

    1) Fetch qemu-io from git
    3) Run test for the file format detected
    4) Report any errors found to autotest

    @param test:   KVM test object.
    @param params: Dictionary with the test parameters.
    @param env:    Dictionary with test environment.
    """
    # First, let's get qemu-io
    std = "git://git.kernel.org/pub/scm/linux/kernel/git/hch/qemu-iotests.git"
    uri = params.get("qemu_io_uri", std)
    branch = params.get("qemu_io_branch", 'master')
    lbranch = params.get("qemu_io_lbranch", 'master')
    commit = params.get("qemu_io_commit", None)
    base_uri = params.get("qemu_io_base_uri", None)
    destination_dir = os.path.join(test.srcdir, "qemu_io_tests")
    git.get_repo(uri=uri, branch=branch, lbranch=lbranch, commit=commit,
                 destination_dir=destination_dir, base_uri=base_uri)

    # Then, set the qemu paths for the use of the testsuite
    os.environ["QEMU_PROG"] = virt_utils.get_path(test.bindir,
                                    params.get("qemu_binary", "qemu"))
    os.environ["QEMU_IMG_PROG"] = virt_utils.get_path(test.bindir,
                                    params.get("qemu_img_binary", "qemu-img"))
    os.environ["QEMU_IO_PROG"] = virt_utils.get_path(test.bindir,
                                    params.get("qemu_io_binary", "qemu-io"))

    os.chdir(destination_dir)
    image_format = params.get("qemu_io_image_format")
    extra_options = params.get("qemu_io_extra_options", "")

    cmd = './check'
    if extra_options:
        cmd += extra_options

    error.context("running qemu-iotests for image format %s" % image_format)
    utils.system("%s -%s" % (cmd, image_format))
