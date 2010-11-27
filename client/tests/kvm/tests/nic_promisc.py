import logging, threading
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
    session_serial = kvm_test_utils.wait_for_login(vm, 0, timeout, 0, 2,
                                                   serial=True)

    def compare(filename):
        md5_host = utils.hash_file(filename, method="md5")
        md5_guest = session.cmd("md5sum %s" % filename)
        md5_guest = md5_guest.split()[0]
        if md5_host != md5_guest:
            logging.error("MD5 hash mismatch between file %s "
                          "present on guest and on host", filename)
            logging.error("MD5 hash for file on guest: %s,"
                          "MD5 hash for file on host: %s", md5_host, md5_guest)
            return False
        return True

    ethname = kvm_test_utils.get_linux_ifname(session, vm.get_mac_address(0))

    class ThreadPromiscCmd(threading.Thread):
        def __init__(self, session, termination_event):
            self.session = session
            self.termination_event = termination_event
            super(ThreadPromiscCmd, self).__init__()


        def run(self):
            set_promisc_cmd = ("ip link set %s promisc on; sleep 0.01;"
                               "ip link set %s promisc off; sleep 0.01" %
                               (ethname, ethname))
            while True:
                self.session.cmd_output(set_promisc_cmd)
                if self.termination_event.isSet():
                    break


    logging.info("Started thread to change promisc mode in guest")
    termination_event = threading.Event()
    promisc_thread = ThreadPromiscCmd(session_serial, termination_event)
    promisc_thread.start()

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
            session.cmd(dd_cmd % (filename, int(size)), timeout=100)

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
            session.cmd_output(cmd)

    finally:
        logging.info("Stopping the promisc thread")
        termination_event.set()
        promisc_thread.join(10)
        logging.info("Restore the %s to the nonpromisc mode", ethname)
        session.cmd_output("ip link set %s promisc off" % ethname)
        session.close()

    if success_counter != 2 * len(file_size):
        raise error.TestFail("Some tests failed, succss_ratio : %s/%s" %
                             (success_counter, len(file_size)))
