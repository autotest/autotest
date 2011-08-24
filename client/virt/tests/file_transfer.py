import logging, time, os
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
from autotest_lib.client.virt import virt_utils


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
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    login_timeout = int(params.get("login_timeout", 360))

    session = vm.wait_for_login(timeout=login_timeout)

    dir_name = test.tmpdir
    transfer_timeout = int(params.get("transfer_timeout"))
    transfer_type = params.get("transfer_type")
    tmp_dir = params.get("tmp_dir", "/tmp/")
    clean_cmd = params.get("clean_cmd", "rm -f")
    filesize = int(params.get("filesize", 4000))
    count = int(filesize / 10)
    if count == 0:
        count = 1

    host_path = os.path.join(dir_name, "tmp-%s" %
                             virt_utils.generate_random_string(8))
    host_path2 = host_path + ".2"
    cmd = "dd if=/dev/zero of=%s bs=10M count=%d" % (host_path, count)
    guest_path = (tmp_dir + "file_transfer-%s" %
                  virt_utils.generate_random_string(8))

    try:
        logging.info("Creating %dMB file on host", filesize)
        utils.run(cmd)

        if transfer_type == "remote":
            logging.info("Transfering file host -> guest, timeout: %ss",
                         transfer_timeout)
            t_begin = time.time()
            vm.copy_files_to(host_path, guest_path, timeout=transfer_timeout)
            t_end = time.time()
            throughput = filesize / (t_end - t_begin)
            logging.info("File transfer host -> guest succeed, "
                         "estimated throughput: %.2fMB/s", throughput)

            logging.info("Transfering file guest -> host, timeout: %ss",
                         transfer_timeout)
            t_begin = time.time()
            vm.copy_files_from(guest_path, host_path2, timeout=transfer_timeout)
            t_end = time.time()
            throughput = filesize / (t_end - t_begin)
            logging.info("File transfer guest -> host succeed, "
                         "estimated throughput: %.2fMB/s", throughput)
        else:
            raise error.TestError("Unknown test file transfer mode %s" %
                                  transfer_type)

        if (utils.hash_file(host_path, method="md5") !=
            utils.hash_file(host_path2, method="md5")):
            raise error.TestFail("File changed after transfer host -> guest "
                                 "and guest -> host")

    finally:
        logging.info('Cleaning temp file on guest')
        session.cmd("%s %s" % (clean_cmd, guest_path))
        logging.info('Cleaning temp files on host')
        try:
            os.remove(host_path)
            os.remove(host_path2)
        except OSError:
            pass
        session.close()
