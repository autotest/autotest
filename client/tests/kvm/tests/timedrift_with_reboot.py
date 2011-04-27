import logging
from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import virt_test_utils


def run_timedrift_with_reboot(test, params, env):
    """
    Time drift test with reboot:

    1) Log into a guest.
    2) Take a time reading from the guest and host.
    3) Reboot the guest.
    4) Take a second time reading.
    5) If the drift (in seconds) is higher than a user specified value, fail.

    @param test: KVM test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

    # Collect test parameters:
    # Command to run to get the current time
    time_command = params.get("time_command")
    # Filter which should match a string to be passed to time.strptime()
    time_filter_re = params.get("time_filter_re")
    # Time format for time.strptime()
    time_format = params.get("time_format")
    drift_threshold = float(params.get("drift_threshold", "10"))
    drift_threshold_single = float(params.get("drift_threshold_single", "3"))
    reboot_iterations = int(params.get("reboot_iterations", 1))

    try:
        # Get initial time
        # (ht stands for host time, gt stands for guest time)
        (ht0, gt0) = virt_test_utils.get_time(session, time_command,
                                             time_filter_re, time_format)

        # Reboot
        for i in range(reboot_iterations):
            # Get time before current iteration
            (ht0_, gt0_) = virt_test_utils.get_time(session, time_command,
                                                   time_filter_re, time_format)
            # Run current iteration
            logging.info("Rebooting: iteration %d of %d...",
                         (i + 1), reboot_iterations)
            session = vm.reboot(session)
            # Get time after current iteration
            (ht1_, gt1_) = virt_test_utils.get_time(session, time_command,
                                                   time_filter_re, time_format)
            # Report iteration results
            host_delta = ht1_ - ht0_
            guest_delta = gt1_ - gt0_
            drift = abs(host_delta - guest_delta)
            logging.info("Host duration (iteration %d): %.2f",
                         (i + 1), host_delta)
            logging.info("Guest duration (iteration %d): %.2f",
                         (i + 1), guest_delta)
            logging.info("Drift at iteration %d: %.2f seconds",
                         (i + 1), drift)
            # Fail if necessary
            if drift > drift_threshold_single:
                raise error.TestFail("Time drift too large at iteration %d: "
                                     "%.2f seconds" % (i + 1, drift))

        # Get final time
        (ht1, gt1) = virt_test_utils.get_time(session, time_command,
                                             time_filter_re, time_format)

    finally:
        if session:
            session.close()

    # Report results
    host_delta = ht1 - ht0
    guest_delta = gt1 - gt0
    drift = abs(host_delta - guest_delta)
    logging.info("Host duration (%d reboots): %.2f",
                 reboot_iterations, host_delta)
    logging.info("Guest duration (%d reboots): %.2f",
                 reboot_iterations, guest_delta)
    logging.info("Drift after %d reboots: %.2f seconds",
                 reboot_iterations, drift)

    # Fail if necessary
    if drift > drift_threshold:
        raise error.TestFail("Time drift too large after %d reboots: "
                             "%.2f seconds" % (reboot_iterations, drift))
