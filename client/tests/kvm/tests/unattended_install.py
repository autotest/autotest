import logging, time, socket, re
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
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()

    port = vm.get_port(int(params.get("guest_port_unattended_install")))
    if params.get("post_install_delay"):
        post_install_delay = int(params.get("post_install_delay"))
    else:
        post_install_delay = 0

    install_timeout = float(params.get("timeout", 3000))
    migrate_background = params.get("migrate_background") == "yes"
    if migrate_background:
        mig_timeout = float(params.get("mig_timeout", "3600"))
        mig_protocol = params.get("migration_protocol", "tcp")

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

        if migrate_background:
            # Drop the params which may break the migration
            # Better method is to used dnsmasq to do the unattended installation
            if vm.params.get("initrd"):
                vm.params["initrd"] = None
            if vm.params.get("kernel"):
                vm.params["kernel"] = None
            if vm.params.get("extra_params"):
                vm.params["extra_params"] = re.sub("--append '.*'", "",
                                                   vm.params["extra_params"])
            vm.migrate(timeout=mig_timeout, protocol=mig_protocol)
        else:
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
