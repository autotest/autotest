import logging, time, socket, re
from autotest_lib.client.common_lib import error
import kvm_vm


@error.context_aware
def run_unattended_install(test, params, env):
    """
    Unattended install test:
    1) Starts a VM with an appropriated setup to start an unattended OS install.
    2) Wait until the install reports to the install watcher its end.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    vm.verify_kernel_crash()

    install_timeout = int(params.get("timeout", 3000))
    post_install_delay = int(params.get("post_install_delay", 0))
    port = vm.get_port(int(params.get("guest_port_unattended_install")))

    migrate_background = params.get("migrate_background") == "yes"
    if migrate_background:
        mig_timeout = float(params.get("mig_timeout", "3600"))
        mig_protocol = params.get("migration_protocol", "tcp")

    logging.info("Waiting for installation to finish. Timeout set to %d s "
                 "(%d min)", install_timeout, install_timeout/60)
    error.context("waiting for installation to finish")

    start_time = time.time()
    while (time.time() - start_time) < install_timeout:
        vm.verify_alive()
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.connect((vm.get_address(), port))
            if client.recv(1024) == "done":
                break
        except (socket.error, kvm_vm.VMAddressError):
            pass
        if migrate_background:
            # Drop the params which may break the migration
            # Better method is to use dnsmasq to do the
            # unattended installation
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
    else:
        raise error.TestFail("Timeout elapsed while waiting for install to "
                             "finish")

    time_elapsed = time.time() - start_time
    logging.info("Guest reported successful installation after %d s (%d min)",
                 time_elapsed, time_elapsed/60)

    if post_install_delay:
        logging.debug("Post install delay specified, waiting %s s...",
                      post_install_delay)
        time.sleep(post_install_delay)
