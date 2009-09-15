import logging, time, commands, re
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils, kvm_utils


def run_timedrift(test, params, env):
    """
    Time drift test (mainly for Windows guests):

    1) Log into a guest.
    2) Take a time reading from the guest and host.
    3) Run load on the guest and host.
    4) Take a second time reading.
    5) Stop the load and rest for a while.
    6) Take a third time reading.
    7) If the drift immediately after load is higher than a user-
    specified value (in %), fail.
    If the drift after the rest period is higher than a user-specified value,
    fail.

    @param test: KVM test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    # Helper functions
    def set_cpu_affinity(pid, mask):
        """
        Set the CPU affinity of all threads of the process with PID pid.
        Do this recursively for all child processes as well.

        @param pid: The process ID.
        @param mask: The CPU affinity mask.
        @return: A dict containing the previous mask for each thread.
        """
        tids = commands.getoutput("ps -L --pid=%s -o lwp=" % pid).split()
        prev_masks = {}
        for tid in tids:
            prev_mask = commands.getoutput("taskset -p %s" % tid).split()[-1]
            prev_masks[tid] = prev_mask
            commands.getoutput("taskset -p %s %s" % (mask, tid))
        children = commands.getoutput("ps --ppid=%s -o pid=" % pid).split()
        for child in children:
            prev_masks.update(set_cpu_affinity(child, mask))
        return prev_masks

    def restore_cpu_affinity(prev_masks):
        """
        Restore the CPU affinity of several threads.

        @param prev_masks: A dict containing TIDs as keys and masks as values.
        """
        for tid, mask in prev_masks.items():
            commands.getoutput("taskset -p %s %s" % (mask, tid))

    def get_time(session, time_command, time_filter_re, time_format):
        """
        Returns the host time and guest time.

        @param session: A shell session.
        @param time_command: Command to issue to get the current guest time.
        @param time_filter_re: Regex filter to apply on the output of
                time_command in order to get the current time.
        @param time_format: Format string to pass to time.strptime() with the
                result of the regex filter.
        @return: A tuple containing the host time and guest time.
        """
        host_time = time.time()
        session.sendline(time_command)
        (match, s) = session.read_up_to_prompt()
        s = re.findall(time_filter_re, s)[0]
        guest_time = time.mktime(time.strptime(s, time_format))
        return (host_time, guest_time)

    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm)

    # Collect test parameters:
    # Command to run to get the current time
    time_command = params.get("time_command")
    # Filter which should match a string to be passed to time.strptime()
    time_filter_re = params.get("time_filter_re")
    # Time format for time.strptime()
    time_format = params.get("time_format")
    guest_load_command = params.get("guest_load_command")
    guest_load_stop_command = params.get("guest_load_stop_command")
    host_load_command = params.get("host_load_command")
    guest_load_instances = int(params.get("guest_load_instances", "1"))
    host_load_instances = int(params.get("host_load_instances", "0"))
    # CPU affinity mask for taskset
    cpu_mask = params.get("cpu_mask", "0xFF")
    load_duration = float(params.get("load_duration", "30"))
    rest_duration = float(params.get("rest_duration", "10"))
    drift_threshold = float(params.get("drift_threshold", "200"))
    drift_threshold_after_rest = float(params.get("drift_threshold_after_rest",
                                                  "200"))

    guest_load_sessions = []
    host_load_sessions = []

    # Set the VM's CPU affinity
    prev_affinity = set_cpu_affinity(vm.get_pid(), cpu_mask)

    try:
        # Get time before load
        (host_time_0, guest_time_0) = get_time(session, time_command,
                                               time_filter_re, time_format)

        # Run some load on the guest
        logging.info("Starting load on guest...")
        for i in range(guest_load_instances):
            load_session = vm.remote_login()
            if not load_session:
                raise error.TestFail("Could not log into guest")
            load_session.set_output_prefix("(guest load %d) " % i)
            load_session.set_output_func(logging.debug)
            load_session.sendline(guest_load_command)
            guest_load_sessions.append(load_session)

        # Run some load on the host
        logging.info("Starting load on host...")
        for i in range(host_load_instances):
            host_load_sessions.append(
                kvm_subprocess.run_bg(host_load_command,
                                      output_func=logging.debug,
                                      output_prefix="(host load %d) " % i,
                                      timeout=0.5))
            # Set the CPU affinity of the load process
            pid = host_load_sessions[-1].get_pid()
            set_cpu_affinity(pid, cpu_mask)

        # Sleep for a while (during load)
        logging.info("Sleeping for %s seconds..." % load_duration)
        time.sleep(load_duration)

        # Get time delta after load
        (host_time_1, guest_time_1) = get_time(session, time_command,
                                               time_filter_re, time_format)

        # Report results
        host_delta = host_time_1 - host_time_0
        guest_delta = guest_time_1 - guest_time_0
        drift = 100.0 * (host_delta - guest_delta) / host_delta
        logging.info("Host duration: %.2f" % host_delta)
        logging.info("Guest duration: %.2f" % guest_delta)
        logging.info("Drift: %.2f%%" % drift)

    finally:
        logging.info("Cleaning up...")
        # Restore the VM's CPU affinity
        restore_cpu_affinity(prev_affinity)
        # Stop the guest load
        if guest_load_stop_command:
            session.get_command_output(guest_load_stop_command)
        # Close all load shell sessions
        for load_session in guest_load_sessions:
            load_session.close()
        for load_session in host_load_sessions:
            load_session.close()

    # Sleep again (rest)
    logging.info("Sleeping for %s seconds..." % rest_duration)
    time.sleep(rest_duration)

    # Get time after rest
    (host_time_2, guest_time_2) = get_time(session, time_command,
                                           time_filter_re, time_format)

    # Report results
    host_delta_total = host_time_2 - host_time_0
    guest_delta_total = guest_time_2 - guest_time_0
    drift_total = 100.0 * (host_delta_total - guest_delta_total) / host_delta
    logging.info("Total host duration including rest: %.2f" % host_delta_total)
    logging.info("Total guest duration including rest: %.2f" % guest_delta_total)
    logging.info("Total drift after rest: %.2f%%" % drift_total)

    session.close()

    # Fail the test if necessary
    if drift > drift_threshold:
        raise error.TestFail("Time drift too large: %.2f%%" % drift)
    if drift_total > drift_threshold_after_rest:
        raise error.TestFail("Time drift too large after rest period: %.2f%%"
                             % drift_total)
