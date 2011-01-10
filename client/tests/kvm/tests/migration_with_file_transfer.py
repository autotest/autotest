import logging, time, os
from autotest_lib.client.common_lib import utils, error
from autotest_lib.client.bin import utils as client_utils
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
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

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
    host_path = "/tmp/file-%s" % kvm_utils.generate_random_string(6)
    host_path_returned = "%s-returned" % host_path
    guest_path = params.get("guest_path", "/tmp/file")
    file_size = params.get("file_size", "500")
    transfer_timeout = int(params.get("transfer_timeout", "240"))

    try:
        utils.run("dd if=/dev/urandom of=%s bs=1M count=%s" % (host_path,
                                                               file_size))

        logging.info("Transferring file from host to guest")
        bg = kvm_utils.Thread(kvm_utils.copy_files_to,
                              (address, client, username, password, port,
                               host_path, guest_path, log_filename,
                               transfer_timeout))
        bg.start()
        try:
            while bg.is_alive():
                logging.info("File transfer not ended, starting a round of "
                             "migration...")
                vm = kvm_test_utils.migrate(vm, env, mig_timeout, mig_protocol)
        finally:
            bg.join()

        logging.info("Transferring file back from guest to host")
        bg = kvm_utils.Thread(kvm_utils.copy_files_from,
                              (address, client, username, password, port,
                               host_path_returned, guest_path, log_filename,
                               transfer_timeout))
        bg.start()
        try:
            while bg.is_alive():
                logging.info("File transfer not ended, starting a round of "
                             "migration...")
                vm = kvm_test_utils.migrate(vm, env, mig_timeout, mig_protocol)
        finally:
            bg.join()

        # Make sure the returned file is indentical to the original one
        orig_hash = client_utils.hash_file(host_path)
        returned_hash = client_utils.hash_file(host_path_returned)
        if orig_hash != returned_hash:
            raise error.TestFail("Returned file hash (%s) differs from "
                                 "original one (%s)" % (returned_hash,
                                                        orig_hash))

    finally:
        session.close()
        if os.path.isfile(host_path):
            os.remove(host_path)
        if os.path.isfile(host_path_returned):
            os.remove(host_path_returned)
