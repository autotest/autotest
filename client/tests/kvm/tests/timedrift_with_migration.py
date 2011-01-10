import logging, time, commands, re
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils, kvm_utils


def run_timedrift_with_migration(test, params, env):
    """
    Time drift test with migration:

    1) Log into a guest.
    2) Take a time reading from the guest and host.
    3) Migrate the guest.
    4) Take a second time reading.
    5) If the drift (in seconds) is higher than a user specified value, fail.

    @param test: KVM test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    timeout = int(params.get("login_timeout", 360))
    session = kvm_test_utils.wait_for_login(vm, timeout=timeout)

    # Collect test parameters:
    # Command to run to get the current time
    time_command = params.get("time_command")
    # Filter which should match a string to be passed to time.strptime()
    time_filter_re = params.get("time_filter_re")
    # Time format for time.strptime()
    time_format = params.get("time_format")
    drift_threshold = float(params.get("drift_threshold", "10"))
    drift_threshold_single = float(params.get("drift_threshold_single", "3"))
    migration_iterations = int(params.get("migration_iterations", 1))

    try:
        # Get initial time
        # (ht stands for host time, gt stands for guest time)
        (ht0, gt0) = kvm_test_utils.get_time(session, time_command,
                                             time_filter_re, time_format)

        # Migrate
        for i in range(migration_iterations):
            # Get time before current iteration
            (ht0_, gt0_) = kvm_test_utils.get_time(session, time_command,
                                                   time_filter_re, time_format)
            session.close()
            # Run current iteration
            logging.info("Migrating: iteration %d of %d..." %
                         (i + 1, migration_iterations))
            vm = kvm_test_utils.migrate(vm, env)
            # Log in
            logging.info("Logging in after migration...")
            # Temporary hack
            time.sleep(30)
            session = vm.remote_login()
            logging.info("Logged in after migration")
            # Get time after current iteration
            (ht1_, gt1_) = kvm_test_utils.get_time(session, time_command,
                                                   time_filter_re, time_format)
            # Report iteration results
            host_delta = ht1_ - ht0_
            guest_delta = gt1_ - gt0_
            drift = abs(host_delta - guest_delta)
            logging.info("Host duration (iteration %d): %.2f" %
                         (i + 1, host_delta))
            logging.info("Guest duration (iteration %d): %.2f" %
                         (i + 1, guest_delta))
            logging.info("Drift at iteration %d: %.2f seconds" %
                         (i + 1, drift))
            # Fail if necessary
            if drift > drift_threshold_single:
                raise error.TestFail("Time drift too large at iteration %d: "
                                     "%.2f seconds" % (i + 1, drift))

        # Get final time
        (ht1, gt1) = kvm_test_utils.get_time(session, time_command,
                                             time_filter_re, time_format)

    finally:
        if session:
            session.close()

    # Report results
    host_delta = ht1 - ht0
    guest_delta = gt1 - gt0
    drift = abs(host_delta - guest_delta)
    logging.info("Host duration (%d migrations): %.2f" %
                 (migration_iterations, host_delta))
    logging.info("Guest duration (%d migrations): %.2f" %
                 (migration_iterations, guest_delta))
    logging.info("Drift after %d migrations: %.2f seconds" %
                 (migration_iterations, drift))

    # Fail if necessary
    if drift > drift_threshold:
        raise error.TestFail("Time drift too large after %d migrations: "
                             "%.2f seconds" % (migration_iterations, drift))
