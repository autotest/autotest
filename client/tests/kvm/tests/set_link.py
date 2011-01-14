import logging
from autotest_lib.client.common_lib import error
from autotest_lib.client.tests.kvm.tests import file_transfer
import kvm_test_utils


def run_set_link(test, params, env):
    """
    KVM guest link test:
    1) Boot up guest with one nic
    2) Ping guest from host
    3) Disable guest link and ping guest from host
    4) Re-enable guest link and ping guest from host
    5) Do file transfer test

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    timeout = float(params.get("login_timeout", 360))
    session = kvm_test_utils.wait_for_login(vm, 0, timeout, 0, 2)

    ip = vm.get_address(0)
    linkname = vm.netdev_id[0]

    logging.info("Pinging guest from host")
    s, o = kvm_test_utils.ping(ip, count=10, timeout=20)
    if s != 0:
        raise error.TestFail("Ping failed, status: %s, output: %s" % (s, o))
    ratio = kvm_test_utils.get_loss_ratio(o)
    if ratio != 0:
        raise error.TestFail("Loss ratio is %s, output: %s" % (ratio, o))

    logging.info("Executing 'set link %s off'" % linkname)
    vm.monitor.cmd("set_link %s off" % linkname)
    logging.info(vm.monitor.info("network"))
    logging.info("Pinging guest from host")
    s, o = kvm_test_utils.ping(ip, count=10, timeout=20)
    if s == 0:
        raise error.TestFail("Ping unexpectedly succeeded, status: %s,"
                             "output: %s" % (s, o))
    ratio = kvm_test_utils.get_loss_ratio(o)
    if ratio != 100:
        raise error.TestFail("Loss ratio is not 100%%,"
                             "Loss ratio is %s" % ratio)

    logging.info("Executing 'set link %s on'" % linkname)
    vm.monitor.cmd("set_link %s on" % linkname)
    logging.info(vm.monitor.info("network"))
    logging.info("Pinging guest from host")
    s, o = kvm_test_utils.ping(ip, count=10, timeout=20)
    if s != 0:
        raise error.TestFail("Ping failed, status: %s, output: %s" % (s, o))
    ratio = kvm_test_utils.get_loss_ratio(o)
    if ratio != 0:
        raise error.TestFail("Loss ratio is %s, output: %s" % (ratio, o))

    file_transfer.run_file_transfer(test, params, env)
    session.close()
