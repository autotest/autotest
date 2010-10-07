import logging, threading, os
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
import kvm_utils, kvm_test_utils

def run_nicdriver_unload(test, params, env):
    """
    Test nic driver.

    1) Boot a VM.
    2) Get the NIC driver name.
    3) Repeatedly unload/load NIC driver.
    4) Multi-session TCP transfer on test interface.
    5) Check whether the test interface should still work.

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

    ethname = kvm_test_utils.get_linux_ifname(session, vm.get_mac_address(0))
    sys_path = "/sys/class/net/%s/device/driver" % (ethname)
    s, o = session.get_command_status_output('readlink -e %s' % sys_path)
    if s:
        raise error.TestError("Could not find driver name")
    driver = os.path.basename(o.strip())
    logging.info("driver is %s", driver)

    class ThreadScp(threading.Thread):
        def run(self):
            remote_file = '/tmp/' + self.getName()
            file_list.append(remote_file)
            ret = vm.copy_files_to(file_name, remote_file, timeout=scp_timeout)
            if ret:
                logging.debug("File %s was transfered successfuly", remote_file)
            else:
                logging.debug("Failed to transfer file %s", remote_file)

    def compare(origin_file, receive_file):
        cmd = "md5sum %s"
        check_sum1 = utils.hash_file(origin_file, method="md5")
        s, output2 = session.get_command_status_output(cmd % receive_file)
        if s != 0:
            logging.error("Could not get md5sum of receive_file")
            return False
        check_sum2 = output2.strip().split()[0]
        logging.debug("original file md5: %s, received file md5: %s",
                      check_sum1, check_sum2)
        if check_sum1 != check_sum2:
            logging.error("MD5 hash of origin and received files doesn't match")
            return False
        return True

    #produce sized file in host
    file_size = params.get("file_size")
    file_name = "/tmp/nicdriver_unload_file"
    cmd = "dd if=/dev/urandom of=%s bs=%sM count=1"
    utils.system(cmd % (file_name, file_size))

    file_list = []
    connect_time = params.get("connect_time")
    scp_timeout = int(params.get("scp_timeout"))
    thread_num = int(params.get("thread_num"))
    unload_load_cmd = ("sleep %s && ifconfig %s down && modprobe -r %s && "
                       "sleep 1 && modprobe %s && sleep 4 && ifconfig %s up" %
                       (connect_time, ethname, driver, driver, ethname))
    pid = os.fork()
    if pid != 0:
        logging.info("Unload/load NIC driver repeatedly in guest...")
        while True:
            logging.debug("Try to unload/load nic drive once")
            if session2.get_command_status(unload_load_cmd, timeout=120) != 0:
                session.get_command_output("rm -rf /tmp/Thread-*")
                raise error.TestFail("Unload/load nic driver failed")
            pid, s = os.waitpid(pid, os.WNOHANG)
            status = os.WEXITSTATUS(s)
            if (pid, status) != (0, 0):
                logging.debug("Child process ending")
                break
    else:
        logging.info("Multi-session TCP data transfer")
        threads = []
        for i in range(thread_num):
            t = ThreadScp()
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout = scp_timeout)
        os._exit(0)

    session2.close()

    try:
        logging.info("Check MD5 hash for received files in multi-session")
        for f in file_list:
            if not compare(file_name, f):
                raise error.TestFail("Fail to compare (guest) file %s" % f)

        logging.info("Test nic function after load/unload")
        if not vm.copy_files_to(file_name, file_name):
            raise error.TestFail("Fail to copy file from host to guest")
        if not compare(file_name, file_name):
            raise error.TestFail("Test nic function after load/unload fail")

    finally:
        session.get_command_output("rm -rf /tmp/Thread-*")
        session.close()
