import logging, time, os
from autotest_lib.client.common_lib import utils, error
import kvm_subprocess, kvm_test_utils, kvm_utils


def run_migration_with_file_transfer(test, params, env):
    """
    KVM migration test:
    1) Get a live VM and clone it.
    2) Verify that the source VM supports migration.  If it does, proceed with
            the test.
    3) Reboot the VM
    4) Send a migration command to the source VM and wait until it's finished.
    5) Kill off the source VM.
    6) Log into the destination VM after the migration is finished.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """

    def transfer_test(address, client, username, password, port, local_path,
                      remote_path, log_filename, timeout):
        # kvm_utils.copy_files_to does not raise exception, so we need a wrapper
        # in order to make it to be used by BackgroundTest.
        if not kvm_utils.copy_files_to(address, client, username, password,
                      port, local_path, remote_path, log_filename, timeout):
            raise error.TestError("Fail to do the file transfer!")

    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    timeout = int(params.get("login_timeout", 360))
    session = kvm_test_utils.wait_for_login(vm, timeout=timeout)

    mig_timeout = float(params.get("mig_timeout", "3600"))
    mig_protocol = params.get("migration_protocol", "tcp")

    # params of transfer test
    username = vm.params.get("username", "")
    password = vm.params.get("password", "")
    client = vm.params.get("file_transfer_client")
    address = vm.get_address(0)
    port = vm.get_port(int(params.get("file_transfer_port")))
    log_filename = ("migration-transfer-%s-to-%s-%s.log" %
                    (vm.name, address,
                     kvm_utils.generate_random_string(4)))
    guest_path = params.get("guest_path", "/tmp")
    file_size = params.get("file_size", "1000")
    transfer_timeout = int(params.get("transfer_timeout", "240"))

    bg = None

    try:
        utils.run("dd if=/dev/zero of=/tmp/file bs=1M count=%s" % file_size)

        # Transfer file from host to guest in the backgroud
        bg = kvm_test_utils.BackgroundTest(transfer_test,
                                           (address, client, username, password,
                                            port, "/tmp/file", guest_path,
                                            log_filename, transfer_timeout))
        bg.start()

        while bg.is_alive():
            logging.info("File transfer is not ended, start a round of"
                         "migration ...")

            # Migrate the VM
            dest_vm = kvm_test_utils.migrate(vm, env, mig_timeout,
                                             mig_protocol, False)

            vm = dest_vm
    finally:
        if bg: bg.join()
        session.close()
        if os.path.isfile("/tmp/zero"):
            os.remove("/tmp/zero")
