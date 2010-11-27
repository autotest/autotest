import logging, time, threading
from autotest_lib.client.common_lib import error
from tests import file_transfer
import kvm_test_utils, kvm_utils

def run_nic_bonding(test, params, env):
    """
    Nic bonding test in guest.

    1) Start guest with four nic models.
    2) Setup bond0 in guest by script bonding_setup.py.
    3) Execute file transfer test between guest and host.
    4) Repeatedly put down/up interfaces by set_link
    5) Execute file transfer test between guest and host.

    @param test: Kvm test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    def control_link_loop(vm, termination_event):
        logging.info("Repeatedly put down/up interfaces by set_link")
        while True:
            for i in range(len(params.get("nics").split())):
                linkname = "%s.%s" % (params.get("nic_model"), i)
                cmd = "set_link %s down" % linkname
                vm.monitor.cmd(cmd)
                time.sleep(1)
                cmd = "set_link %s up" % linkname
                vm.monitor.cmd(cmd)
            if termination_event.isSet():
                break

    timeout = int(params.get("login_timeout", 1200))
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session_serial = kvm_test_utils.wait_for_login(vm, 0, timeout, 0, 2,
                                                   serial=True)
    script_path = kvm_utils.get_path(test.bindir, "scripts/bonding_setup.py")
    vm.copy_files_to(script_path, "/tmp/bonding_setup.py")
    cmd = "python /tmp/bonding_setup.py %s" % vm.get_mac_address()
    session_serial.cmd(cmd)

    termination_event = threading.Event()
    t = threading.Thread(target=control_link_loop,
                         args=(vm, termination_event))
    try:
        logging.info("Do some basic test before testing high availability")
        file_transfer.run_file_transfer(test, params, env)
        t.start()
        logging.info("Do file transfer testing")
        file_transfer.run_file_transfer(test, params, env)
    finally:
        termination_event.set()
        t.join(10)
        session_serial.close()
