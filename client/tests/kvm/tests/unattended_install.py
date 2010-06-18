import logging, time, socket
from autotest_lib.client.common_lib import error
import kvm_utils, kvm_test_utils


def run_unattended_install(test, params, env):
    """
    Unattended install test:
    1) Starts a VM with an appropriated setup to start an unattended OS install.
    2) Wait until the install reports to the install watcher its end.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    buf = 1024
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))

    port = vm.get_port(int(params.get("guest_port_unattended_install")))
    if params.get("post_install_delay"):
        post_install_delay = int(params.get("post_install_delay"))
    else:
        post_install_delay = 0

    install_timeout = float(params.get("timeout", 3000))
    logging.info("Starting unattended install watch process. "
                 "Timeout set to %ds (%d min)", install_timeout,
                 install_timeout/60)
    start_time = time.time()
    time_elapsed = 0
    while time_elapsed < install_timeout:
        if not vm.is_alive():
            raise error.TestError("Guest died before end of OS install")
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        addr = vm.get_address()
        if addr is not None:
            try:
                client.connect((addr, port))
                msg = client.recv(1024)
                if msg == 'done':
                    if post_install_delay:
                        logging.debug("Post install delay specified, "
                                      "waiting %ss...", post_install_delay)
                        time.sleep(post_install_delay)
                    break
            except socket.error:
                pass
        time.sleep(1)
        client.close()
        end_time = time.time()
        time_elapsed = int(end_time - start_time)

    if time_elapsed < install_timeout:
        logging.info('Guest reported successful installation after %ds '
                     '(%d min)', time_elapsed, time_elapsed/60)
    else:
        raise error.TestFail('Timeout elapsed while waiting for install to '
                             'finish.')
