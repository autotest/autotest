import logging, commands, re, time, os
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
import kvm_utils, kvm_test_utils

def run_file_transfer(test, params, env):
    """
    Test ethrnet device function by ethtool

    1) Boot up a VM.
    2) Create a large file by dd on host.
    3) Copy this file from host to guest.
    4) Copy this file from guest to host.
    5) Check if file transfers ended good.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    timeout=int(params.get("login_timeout", 360))

    session = kvm_test_utils.wait_for_login(vm, timeout=timeout)
    if not session:
        raise error.TestFail("Could not log into guest '%s'" % vm.name)

    dir = test.tmpdir
    transfer_timeout = int(params.get("transfer_timeout"))
    transfer_type = params.get("transfer_type")
    tmp_dir = params.get("tmp_dir", "/tmp/")
    clean_cmd = params.get("clean_cmd", "rm -f")
    filesize = int(params.get("filesize", 4000))
    cmd = "dd if=/dev/urandom of=%s/a.out bs=1M count=%d" % (dir, filesize)
    guest_path = tmp_dir + "b.out"

    try:
        logging.info("Creating %dMB file on host", filesize)
        utils.run(cmd)

        if transfer_type == "remote":
            logging.info("Transfering file host -> guest, timeout: %ss",
                         transfer_timeout)
            t_begin = time.time()
            success = vm.copy_files_to("%s/a.out" % dir, guest_path,
                                       timeout=transfer_timeout)
            t_end = time.time()
            throughput = filesize / (t_end - t_begin)
            if not success:
                raise error.TestFail("Fail to transfer file from host to guest")
            logging.info("File transfer host -> guest succeed, "
                         "estimated throughput: %.2fMB/s", throughput)

            logging.info("Transfering file guest -> host, timeout: %ss",
                         transfer_timeout)
            t_begin = time.time()
            success = vm.copy_files_from(guest_path, "%s/c.out" % dir,
                                         timeout=transfer_timeout)
            t_end = time.time()
            throughput = filesize / (t_end - t_begin)
            if not success:
                raise error.TestFail("Fail to transfer file from guest to host")
            logging.info("File transfer guest -> host succeed, "
                         "estimated throughput: %.2fMB/s", throughput)
        else:
            raise error.TestError("Unknown test file transfer mode %s" %
                                  transfer_type)

        for f in ['a.out', 'c.out']:
            p = os.path.join(dir, f)
            size = os.path.getsize(p)
            logging.debug('Size of %s: %sB', f, size)

        md5_orig = utils.hash_file("%s/a.out" % dir, method="md5")
        md5_new = utils.hash_file("%s/c.out" % dir, method="md5")

        if md5_orig != md5_new:
            raise error.TestFail("File changed after transfer host -> guest "
                                 "and guest -> host")

    finally:
        logging.info('Cleaning temp file on guest')
        clean_cmd += " %s" % guest_path
        s, o = session.get_command_status_output(clean_cmd)
        if s:
            logging.warning("Failed to clean remote file %s, output:%s",
                            guest_path, o)
        logging.info('Cleaning temp files on host')
        try:
            os.remove('%s/a.out' % dir)
            os.remove('%s/c.out' % dir)
        except OSError:
            pass
        session.close()
