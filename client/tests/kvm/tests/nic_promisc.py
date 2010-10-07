import logging
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
import kvm_utils, kvm_test_utils

def run_nic_promisc(test, params, env):
    """
    Test nic driver in promisc mode:

    1) Boot up a VM.
    2) Repeatedly enable/disable promiscuous mode in guest.
    3) TCP data transmission from host to guest, and from guest to host,
       with 1/1460/65000/100000000 bytes payloads.
    4) Clean temporary files.
    5) Stop enable/disable promiscuous mode change.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    timeout = int(params.get("login_timeout", 360))
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm, timeout=timeout)

    logging.info("Trying to log into guest '%s' by serial", vm.name)
    session2 = kvm_utils.wait_for(lambda: vm.serial_login(),
                                  timeout, 0, step=2)
    if not session2:
        raise error.TestFail("Could not log into guest '%s'" % vm.name)

    def compare(filename):
        cmd = "md5sum %s" % filename
        md5_host = utils.hash_file(filename, method="md5")
        rc_guest, md5_guest = session.get_command_status_output(cmd)
        if rc_guest:
            logging.debug("Could not get MD5 hash for file %s on guest,"
                          "output: %s", filename, md5_guest)
            return False
        md5_guest = md5_guest.split()[0]
        if md5_host != md5_guest:
            logging.error("MD5 hash mismatch between file %s "
                          "present on guest and on host", filename)
            logging.error("MD5 hash for file on guest: %s,"
                          "MD5 hash for file on host: %s", md5_host, md5_guest)
            return False
        return True

    ethname = kvm_test_utils.get_linux_ifname(session, vm.get_mac_address(0))
    set_promisc_cmd = ("ip link set %s promisc on; sleep 0.01;"
                       "ip link set %s promisc off; sleep 0.01" %
                       (ethname, ethname))
    logging.info("Set promisc change repeatedly in guest")
    session2.sendline("while true; do %s; done" % set_promisc_cmd)

    dd_cmd = "dd if=/dev/urandom of=%s bs=%d count=1"
    filename = "/tmp/nic_promisc_file"
    file_size = params.get("file_size", "1, 1460, 65000, 100000000").split(",")
    success_counter = 0
    try:
        for size in file_size:
            logging.info("Create %s bytes file on host" % size)
            utils.run(dd_cmd % (filename, int(size)))

            logging.info("Transfer file from host to guest")
            if not vm.copy_files_to(filename, filename):
                logging.error("File transfer failed")
                continue
            if not compare(filename):
                logging.error("Compare file failed")
                continue
            else:
                success_counter += 1

            logging.info("Create %s bytes file on guest" % size)
            if session.get_command_status(dd_cmd % (filename, int(size)),
                                                    timeout=100) != 0:
                logging.error("Create file on guest failed")
                continue

            logging.info("Transfer file from guest to host")
            if not vm.copy_files_from(filename, filename):
                logging.error("File transfer failed")
                continue
            if not compare(filename):
                logging.error("Compare file failed")
                continue
            else:
                success_counter += 1

            logging.info("Clean temporary files")
            cmd = "rm -f %s" % filename
            utils.run(cmd)
            session.get_command_status(cmd)

    finally:
        logging.info("Restore the %s to the nonpromisc mode", ethname)
        session2.close()
        session.get_command_status("ip link set %s promisc off" % ethname)
        session.close()

    if success_counter != 2 * len(file_size):
        raise error.TestFail("Some tests failed, succss_ratio : %s/%s" %
                             (success_counter, len(file_size)))
