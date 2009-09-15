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

    # See if migration is supported
    s, o = vm.send_monitor_cmd("help info")
    if not "info migrate" in o:
        raise error.TestError("Migration is not supported")

    # Log into guest and get the output of migration_test_command
    session = kvm_test_utils.wait_for_login(vm)
    migration_test_command = params.get("migration_test_command")
    reference_output = session.get_command_output(migration_test_command)
    session.close()

    # Clone the main VM and ask it to wait for incoming migration
    dest_vm = vm.clone()
    dest_vm.create(for_migration=True)

    try:
        # Define the migration command
        cmd = "migrate -d tcp:localhost:%d" % dest_vm.migration_port
        logging.debug("Migration command: %s" % cmd)

        # Migrate
        s, o = vm.send_monitor_cmd(cmd)
        if s:
            logging.error("Migration command failed (command: %r, output: %r)"
                          % (cmd, o))
            raise error.TestFail("Migration command failed")

        # Define some helper functions
        def mig_finished():
            s, o = vm.send_monitor_cmd("info migrate")
            return s == 0 and not "Migration status: active" in o

        def mig_succeeded():
            s, o = vm.send_monitor_cmd("info migrate")
            return s == 0 and "Migration status: completed" in o

        def mig_failed():
            s, o = vm.send_monitor_cmd("info migrate")
            return s == 0 and "Migration status: failed" in o

        # Wait for migration to finish
        if not kvm_utils.wait_for(mig_finished, 90, 2, 2,
                                  "Waiting for migration to finish..."):
            raise error.TestFail("Timeout elapsed while waiting for migration "
                                 "to finish")

        # Report migration status
        if mig_succeeded():
            logging.info("Migration finished successfully")
        elif mig_failed():
            raise error.TestFail("Migration failed")
        else:
            raise error.TestFail("Migration ended with unknown status")

        # Kill the source VM
        vm.destroy(gracefully=False)

        # Replace the source VM with the new cloned VM
        kvm_utils.env_register_vm(env, params.get("main_vm"), dest_vm)

    except:
        dest_vm.destroy(gracefully=False)
        raise

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
