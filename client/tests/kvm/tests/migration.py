import logging, time
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils, kvm_utils


def run_migration(test, params, env):
    """
    KVM migration test:
    1) Get a live VM and clone it.
    2) Verify that the source VM supports migration.  If it does, proceed with
            the test.
    3) Send a migration command to the source VM and wait until it's finished.
    4) Kill off the source VM.
    3) Log into the destination VM after the migration is finished.
    4) Compare the output of a reference command executed on the source with
            the output of the same command on the destination machine.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm)

    # Get the output of migration_test_command
    test_command = params.get("migration_test_command")
    reference_output = session.get_command_output(test_command)

    # Start some process in the background (and leave the session open)
    background_command = params.get("migration_bg_command", "")
    session.sendline(background_command)
    time.sleep(5)

    # Start another session with the guest and make sure the background
    # process is running
    session2 = kvm_test_utils.wait_for_login(vm)

    try:
        check_command = params.get("migration_bg_check_command", "")
        if session2.get_command_status(check_command, timeout=30) != 0:
            raise error.TestError("Could not start background process '%s'" %
                                  background_command)
        session2.close()

        # Migrate the VM
        dest_vm = kvm_test_utils.migrate(vm, env)

        # Log into the guest again
        logging.info("Logging into guest after migration...")
        session2 = kvm_utils.wait_for(dest_vm.remote_login, 30, 0, 2)
        if not session2:
            raise error.TestFail("Could not log into guest after migration")
        logging.info("Logged in after migration")

        # Make sure the background process is still running
        if session2.get_command_status(check_command, timeout=30) != 0:
            raise error.TestFail("Could not find running background process "
                                 "after migration: '%s'" % background_command)

        # Get the output of migration_test_command
        output = session2.get_command_output(test_command)

        # Compare output to reference output
        if output != reference_output:
            logging.info("Command output before migration differs from "
                         "command output after migration")
            logging.info("Command: %s" % test_command)
            logging.info("Output before:" +
                         kvm_utils.format_str_for_message(reference_output))
            logging.info("Output after:" +
                         kvm_utils.format_str_for_message(output))
            raise error.TestFail("Command '%s' produced different output "
                                 "before and after migration" % test_command)

    finally:
        # Kill the background process
        if session2.is_alive():
            session2.get_command_output(params.get("migration_bg_kill_command",
                                                   ""))

    session2.close()
    session.close()
