import logging, time, os
from autotest_lib.client.common_lib import utils, error
from autotest_lib.client.bin import utils as client_utils
from autotest_lib.client.virt import virt_utils


@error.context_aware
def run_migration_with_file_transfer(test, params, env):
    """
    KVM migration test:
    1) Get a live VM and clone it.
    2) Verify that the source VM supports migration.  If it does, proceed with
            the test.
    3) Transfer file from host to guest.
    4) Repeatedly migrate VM and wait until transfer's finished.
    5) Transfer file from guest back to host.
    6) Repeatedly migrate VM and wait until transfer's finished.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    login_timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=login_timeout)

    mig_timeout = float(params.get("mig_timeout", "3600"))
    mig_protocol = params.get("migration_protocol", "tcp")
    mig_cancel_delay = int(params.get("mig_cancel") == "yes") * 2

    host_path = "/tmp/file-%s" % virt_utils.generate_random_string(6)
    host_path_returned = "%s-returned" % host_path
    guest_path = params.get("guest_path", "/tmp/file")
    file_size = params.get("file_size", "500")
    transfer_timeout = int(params.get("transfer_timeout", "240"))

    try:
        utils.run("dd if=/dev/urandom of=%s bs=1M count=%s" % (host_path,
                                                               file_size))

        def run_and_migrate(bg):
            bg.start()
            try:
                while bg.isAlive():
                    logging.info("File transfer not ended, starting a round of "
                                 "migration...")
                    vm.migrate(mig_timeout, mig_protocol, mig_cancel_delay)
            except:
                # If something bad happened in the main thread, ignore
                # exceptions raised in the background thread
                bg.join(suppress_exception=True)
                raise
            else:
                bg.join()

        error.context("transferring file to guest while migrating",
                      logging.info)
        bg = virt_utils.Thread(vm.copy_files_to, (host_path, guest_path),
                              dict(verbose=True, timeout=transfer_timeout))
        run_and_migrate(bg)

        error.context("transferring file back to host while migrating",
                      logging.info)
        bg = virt_utils.Thread(vm.copy_files_from,
                              (guest_path, host_path_returned),
                              dict(verbose=True, timeout=transfer_timeout))
        run_and_migrate(bg)

        # Make sure the returned file is identical to the original one
        error.context("comparing hashes", logging.info)
        orig_hash = client_utils.hash_file(host_path)
        returned_hash = client_utils.hash_file(host_path_returned)
        if orig_hash != returned_hash:
            raise error.TestFail("Returned file hash (%s) differs from "
                                 "original one (%s)" % (returned_hash,
                                                        orig_hash))
        error.context()

    finally:
        session.close()
        if os.path.isfile(host_path):
            os.remove(host_path)
        if os.path.isfile(host_path_returned):
            os.remove(host_path_returned)
