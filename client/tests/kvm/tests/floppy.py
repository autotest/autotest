import logging, time, os
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils


@error.context_aware
def run_floppy(test, params, env):
    """
    Test virtual floppy of guest:

    1) Create a floppy disk image on host
    2) Start the guest with this floppy image.
    3) Make a file system on guest virtual floppy.
    4) Calculate md5sum value of a file and copy it into floppy.
    5) Verify whether the md5sum does match.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    def master_floppy(params):
        error.context("creating test floppy")
        floppy = os.path.abspath(params.get("floppy"))
        utils.run("dd if=/dev/zero of=%s bs=512 count=2880" % floppy)


    master_floppy(params)
    vm = env.get_vm(params["main_vm"])
    vm.create()

    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

    dest_dir = params.get("mount_dir")
    # If mount_dir specified, treat guest as a Linux OS
    # Some Linux distribution does not load floppy at boot and Windows
    # needs time to load and init floppy driver
    if dest_dir:
        status = session.cmd("modprobe floppy")
    else:
        time.sleep(20)

    error.context("Formating floppy disk before using it")
    format_cmd = params.get("format_floppy_cmd")
    session.cmd(format_cmd, timeout=120)
    logging.info("Floppy disk formatted successfully")

    source_file = params.get("source_file")
    dest_file = params.get("dest_file")

    if dest_dir:
        error.context("Mounting floppy")
        session.cmd("mount /dev/fd0 %s" % dest_dir)
    error.context("Testing floppy")
    session.cmd(params.get("test_floppy_cmd"))

    try:
        error.context("Copying file to the floppy")
        session.cmd("%s %s %s" % (params.get("copy_cmd"), source_file,
                    dest_file))
        logging.info("Succeed to copy file '%s' into floppy disk" % source_file)

        error.context("Checking if the file is unchanged after copy")
        session.cmd("%s %s %s" % (params.get("diff_file_cmd"), source_file,
                    dest_file))
    finally:
        clean_cmd = "%s %s" % (params.get("clean_cmd"), dest_file)
        session.cmd(clean_cmd)
        if dest_dir:
            session.cmd("umount %s" % dest_dir)
        session.close()
