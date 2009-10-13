import logging
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

    # Log into guest and get the output of migration_test_command
    session = kvm_test_utils.wait_for_login(vm)
    migration_test_command = params.get("migration_test_command")
    reference_output = session.get_command_output(migration_test_command)
    session.close()

    # Migrate the VM
    dest_vm = kvm_test_utils.migrate(vm, env)

    # Log into guest and get the output of migration_test_command
    logging.info("Logging into guest after migration...")
    session = dest_vm.remote_login()
    if not session:
        raise error.TestFail("Could not log into guest after migration")
    logging.info("Logged in after migration")
    output = session.get_command_output(migration_test_command)
    session.close()

    # Compare output to reference output
    if output != reference_output:
        logging.info("Command output before migration differs from command "
                     "output after migration")
        logging.info("Command: %s" % params.get("migration_test_command"))
        logging.info("Output before:" +
                     kvm_utils.format_str_for_message(reference_output))
        logging.info("Output after:" +
                     kvm_utils.format_str_for_message(output))
        raise error.TestFail("Command produced different output before and "
                             "after migration")
