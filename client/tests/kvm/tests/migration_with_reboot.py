import logging, time
import threading
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils, kvm_utils


def run_migration_with_reboot(test, params, env):
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
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    timeout = int(params.get("login_timeout", 360))
    session = kvm_test_utils.wait_for_login(vm, timeout=timeout)

    mig_timeout = float(params.get("mig_timeout", "3600"))
    mig_protocol = params.get("migration_protocol", "tcp")
    mig_cancel = bool(params.get("mig_cancel"))
    bg = None

    try:
        # reboot the VM in background
        bg = kvm_test_utils.BackgroundTest(kvm_test_utils.reboot, (vm, session))
        bg.start()

        while bg.is_alive():
            # Migrate the VM
            dest_vm = kvm_test_utils.migrate(vm, env, mig_timeout, mig_protocol,
                                             False)
            vm = dest_vm

    finally:
        if bg:
            bg.join()
        session.close()
