import logging, time
import threading
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_utils, kvm_test_utils


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

    def reboot_test(client, session, address, reboot_command, port, username,
                    password, prompt, linesep, log_filename, timeout):
        """
        A version of reboot test which is safe to be called in the background as
        it only needs an vm object
        """
        # Send a reboot command to the guest's shell
        session.sendline(reboot_command)
        logging.info("Reboot command sent. Waiting for guest to go down...")

        # Wait for the session to become unresponsive and close it
        if not kvm_utils.wait_for(lambda: not session.is_responsive(timeout=30),
                                  120, 0, 1):
            raise error.TestFail("Guest refuses to go down")
        session.close()

        # Try logging into the guest until timeout expires
        logging.info("Guest is down. Waiting for it to go up again, timeout %ds",
                     timeout)
        session = kvm_utils.remote_login(client, address, port, username,
                                         password, prompt, linesep,
                                         log_filename, timeout)

        if not session:
            raise error.TestFail("Could not log into guest after reboot")
        logging.info("Guest is up again")
        session.close()

    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    timeout = int(params.get("login_timeout", 360))
    session = kvm_test_utils.wait_for_login(vm, timeout=timeout)

    # params of reboot
    username = params.get("username", "")
    password = params.get("password", "")
    prompt = params.get("shell_prompt", "[\#\$]")
    linesep = eval("'%s'" % params.get("shell_linesep", r"\n"))
    client = params.get("shell_client")
    address = vm.get_address(0)
    port = vm.get_port(int(params.get("shell_port")))
    log_filename = ("migration-reboot-%s-%s.log" %
                    (vm.name, kvm_utils.generate_random_string(4)))
    reboot_command = params.get("reboot_command")

    mig_timeout = float(params.get("mig_timeout", "3600"))
    mig_protocol = params.get("migration_protocol", "tcp")
    mig_cancel = bool(params.get("mig_cancel"))
    bg = None

    try:
        # reboot the VM in background
        bg = kvm_test_utils.BackgroundTest(reboot_test,
                                           (client, session, address,
                                            reboot_command, port, username,
                                            password, prompt, linesep,
                                            log_filename, timeout))
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
