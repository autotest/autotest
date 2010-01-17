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
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('', 12323))
    server.listen(1)

    install_timeout = float(params.get("timeout", 3000))
    logging.info("Starting unattended install watch process. "
                 "Timeout set to %ds (%d min)", install_timeout,
                 install_timeout/60)
    start_time = time.time()

    while True:
        server.settimeout(install_timeout)
        try:
            (client, addr) = server.accept()
        except socket.timeout:
            server.close()
            raise error.TestFail('Timeout elapsed while waiting for install to '
                                 'finish.')
        msg = client.recv(1024)
        logging.debug("Received '%s' from %s", msg, addr)
        if msg == 'done':
            end_time = time.time()
            time_elapsed = int(end_time - start_time)
            logging.info('Guest reported successful installation after %ds '
                         '(%d min)', time_elapsed, time_elapsed/60)
            server.close()
            break
        else:
            logging.error('Got invalid string from client: %s.' % msg)
