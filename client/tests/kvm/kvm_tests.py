import time, os, logging, re, commands
from autotest_lib.client.common_lib import utils, error
import kvm_utils, kvm_subprocess, ppm_utils, scan_results

"""
KVM test definitions.

@copyright: 2008-2009 Red Hat Inc.
"""


def run_boot(test, params, env):
    """
    KVM reboot test:
    1) Log into a guest
    2) Send a reboot command to the guest
    3) Wait until it's up.
    4) Log into the guest to verify it's up again.

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = kvm_utils.env_get_vm(env, params.get("main_vm"))
    if not vm:
        raise error.TestError("VM object not found in environment")
    if not vm.is_alive():
        raise error.TestError("VM seems to be dead; Test requires a living VM")

    logging.info("Waiting for guest to be up...")

    session = kvm_utils.wait_for(vm.remote_login, 240, 0, 2)
    if not session:
        raise error.TestFail("Could not log into guest")

    logging.info("Logged in")

    if params.get("reboot") == "yes":
        # Send the VM's reboot command
        session.sendline(vm.get_params().get("reboot_command"))
        logging.info("Reboot command sent; waiting for guest to go down...")

        if not kvm_utils.wait_for(lambda: not session.is_responsive(),
                                  120, 0, 1):
            raise error.TestFail("Guest refuses to go down")

        session.close()

        logging.info("Guest is down; waiting for it to go up again...")

        session = kvm_utils.wait_for(vm.remote_login, 240, 0, 2)
        if not session:
            raise error.TestFail("Could not log into guest after reboot")

        logging.info("Guest is up again")

    session.close()


def run_shutdown(test, params, env):
    """
    KVM shutdown test:
    1) Log into a guest
    2) Send a shutdown command to the guest
    3) Wait until it's down

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment
    """
    vm = kvm_utils.env_get_vm(env, params.get("main_vm"))
    if not vm:
        raise error.TestError("VM object not found in environment")
    if not vm.is_alive():
        raise error.TestError("VM seems to be dead; Test requires a living VM")

    logging.info("Waiting for guest to be up...")

    session = kvm_utils.wait_for(vm.remote_login, 240, 0, 2)
    if not session:
        raise error.TestFail("Could not log into guest")

    try:
        logging.info("Logged in")

        # Send the VM's shutdown command
        session.sendline(vm.get_params().get("shutdown_command"))

        logging.info("Shutdown command sent; waiting for guest to go down...")

        if not kvm_utils.wait_for(vm.is_dead, 240, 0, 1):
            raise error.TestFail("Guest refuses to go down")

        logging.info("Guest is down")
    finally:
        session.close()


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
    vm = kvm_utils.env_get_vm(env, params.get("main_vm"))
    if not vm:
        raise error.TestError("VM object not found in environment")
    if not vm.is_alive():
        raise error.TestError("VM seems to be dead; Test requires a living VM")

    # See if migration is supported
    s, o = vm.send_monitor_cmd("help info")
    if not "info migrate" in o:
        raise error.TestError("Migration is not supported")

    dest_vm = vm.clone()
    dest_vm.create(for_migration=True)

    # Log into guest and get the output of migration_test_command
    logging.info("Waiting for guest to be up...")

    session = kvm_utils.wait_for(vm.remote_login, 240, 0, 2)
    if not session:
        raise error.TestFail("Could not log into guest")

    logging.info("Logged in")

    reference_output = session.get_command_output(params.get("migration_test_"
                                                             "command"))
    session.close()

    # Define the migration command
    cmd = "migrate -d tcp:localhost:%d" % dest_vm.migration_port
    logging.debug("Migration command: %s" % cmd)

    # Migrate
    s, o = vm.send_monitor_cmd(cmd)
    if s:
        logging.error("Migration command failed (command: %r, output: %r)" %
                      (cmd, o))
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
        raise error.TestFail("Timeout elapsed while waiting for migration to "
                             "finish")

    # Report migration status
    if mig_succeeded():
        logging.info("Migration finished successfully")
    elif mig_failed():
        raise error.TestFail("Migration failed")
    else:
        raise error.TestFail("Migration ended with unknown status")

    # Kill the source VM
    vm.destroy(gracefully=False)

    # Log into guest and get the output of migration_test_command
    logging.info("Logging into guest after migration...")

    session = dest_vm.remote_login()
    if not session:
        raise error.TestFail("Could not log into guest after migration")

    logging.info("Logged in after migration")

    output = session.get_command_output(params.get("migration_test_command"))
    session.close()

    # Compare output to reference output
    if output != reference_output:
        logging.info("Command output before migration differs from command "
                     "output after migration")
        logging.info("Command: %s" % params.get("migration_test_command"))
        logging.info("Output before:" +
                     kvm_utils.format_str_for_message(reference_output))
        logging.info("Output after:" + kvm_utils.format_str_for_message(output))
        raise error.TestFail("Command produced different output before and "
                             "after migration")

    kvm_utils.env_register_vm(env, params.get("main_vm"), dest_vm)


def run_autotest(test, params, env):
    """
    Run an autotest test inside a guest.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = kvm_utils.env_get_vm(env, params.get("main_vm"))
    if not vm:
        raise error.TestError("VM object not found in environment")
    if not vm.is_alive():
        raise error.TestError("VM seems to be dead; Test requires a living VM")

    logging.info("Logging into guest...")

    session = kvm_utils.wait_for(vm.remote_login, 240, 0, 2)
    if not session:
        raise error.TestFail("Could not log into guest")

    logging.info("Logged in")

    # Collect some info
    test_name = params.get("test_name")
    test_timeout = int(params.get("test_timeout", 300))
    test_control_file = params.get("test_control_file", "control")
    tarred_autotest_path = "/tmp/autotest.tar.bz2"
    tarred_test_path = "/tmp/%s.tar.bz2" % test_name

    # tar the contents of bindir/autotest
    cmd = "cd %s; tar cvjf %s autotest/*"
    cmd += " --exclude=autotest/tests"
    cmd += " --exclude=autotest/results"
    cmd += " --exclude=autotest/tmp"
    cmd += " --exclude=autotest/control"
    cmd += " --exclude=*.pyc"
    cmd += " --exclude=*.svn"
    cmd += " --exclude=*.git"
    kvm_subprocess.run_fg(cmd % (test.bindir, tarred_autotest_path), timeout=30)

    # tar the contents of bindir/autotest/tests/<test_name>
    cmd = "cd %s; tar cvjf %s %s/*"
    cmd += " --exclude=*.pyc"
    cmd += " --exclude=*.svn"
    cmd += " --exclude=*.git"
    kvm_subprocess.run_fg(cmd %
                          (os.path.join(test.bindir, "autotest", "tests"),
                           tarred_test_path, test_name), timeout=30)

    # Check if we need to copy autotest.tar.bz2
    copy = False
    output = session.get_command_output("ls -l autotest.tar.bz2")
    if "such file" in output:
        copy = True
    else:
        size = int(output.split()[4])
        if size != os.path.getsize(tarred_autotest_path):
            copy = True
    # Perform the copy
    if copy:
        logging.info("Copying autotest.tar.bz2 to guest"
                     " (file is missing or has a different size)...")
        if not vm.copy_files_to(tarred_autotest_path, ""):
            raise error.TestFail("Could not copy autotest.tar.bz2 to guest")

    # Check if we need to copy <test_name>.tar.bz2
    copy = False
    output = session.get_command_output("ls -l %s.tar.bz2" % test_name)
    if "such file" in output:
        copy = True
    else:
        size = int(output.split()[4])
        if size != os.path.getsize(tarred_test_path):
            copy = True
    # Perform the copy
    if copy:
        logging.info("Copying %s.tar.bz2 to guest (file is missing or has a"
                     " different size)..." % test_name)
        if not vm.copy_files_to(tarred_test_path, ""):
            raise error.TestFail("Could not copy %s.tar.bz2 to guest" %
                                 test_name)

    # Extract autotest.tar.bz2
    logging.info("Extracting autotest.tar.bz2...")
    status = session.get_command_status("tar xvfj autotest.tar.bz2")
    if status != 0:
        raise error.TestFail("Could not extract autotest.tar.bz2")

    # mkdir autotest/tests
    session.sendline("mkdir autotest/tests")

    # Extract <test_name>.tar.bz2 into autotest/tests
    logging.info("Extracting %s.tar.bz2..." % test_name)
    status = session.get_command_status("tar xvfj %s.tar.bz2 -C "
                                        "autotest/tests" % test_name)
    if status != 0:
        raise error.TestFail("Could not extract %s.tar.bz2" % test_name)

    # Cleaning up old remaining results
    session.sendline("rm -rf autotest/results/*")
    # Copying the selected control file (located inside
    # test.bindir/autotest_control to the autotest dir
    control_file_path = os.path.join(test.bindir, "autotest_control",
                                     test_control_file)
    if not vm.copy_files_to(control_file_path, "autotest/control"):
        raise error.TestFail("Could not copy the test control file to guest")
    # Run the test
    logging.info("Running test '%s'..." % test_name)
    session.sendline("cd autotest")
    session.sendline("rm -f control.state")
    session.read_up_to_prompt()
    session.sendline("bin/autotest control")
    logging.info("---------------- Test output ----------------")
    match = session.read_up_to_prompt(timeout=test_timeout,
                                      print_func=logging.info)[0]
    logging.info("---------------- End of test output ----------------")
    if not match:
        raise error.TestFail("Timeout elapsed while waiting for test to "
                             "complete")
    # Get the results generated by autotest
    output = session.get_command_output("cat results/*/status")

    # Parse test results
    result_list = scan_results.parse_results(output)

    # Report test results and check for FAIL/ERROR status
    logging.info("Results (test, status, duration, info):")
    status_error = False
    status_fail = False
    if result_list == []:
        status_fail = True
        message_fail = ("Test '%s' did not produce any recognizable "
                        "results" % test_name)
    for result in result_list:
        logging.info(str(result))
        if result[1] == "FAIL":
            status_fail = True
            message_fail = ("Test '%s' ended with FAIL "
                            "(info: '%s')" % (result[0], result[3]))
        if result[1] == "ERROR":
            status_error = True
            message_error = ("Test '%s' ended with ERROR "
                             "(info: '%s')" % (result[0], result[3]))
        if result[1] == "ABORT":
            status_error = True
            message_error = ("Test '%s' ended with ABORT "
                             "(info: '%s')" % (result[0], result[3]))

    # Copy test results to the local bindir/guest_results
    logging.info("Copying results back from guest...")
    guest_results_dir = os.path.join(test.outputdir, "guest_results")
    if not os.path.exists(guest_results_dir):
        os.mkdir(guest_results_dir)
    if not vm.copy_files_from("autotest/results/default/*", guest_results_dir):
        logging.error("Could not copy results back from guest")

    # Fail the test if necessary
    if status_fail:
        raise error.TestFail(message_fail)
    elif status_error:
        raise error.TestError(message_error)


def internal_yum_update(session, command, prompt, timeout):
    """
    Helper function to perform the yum update test.

    @param session: shell session stablished to the host
    @param command: Command to be sent to the shell session
    @param prompt: Machine prompt
    @param timeout: How long to wait until we get an appropriate output from
            the shell session.
    """
    session.sendline(command)
    end_time = time.time() + timeout
    while time.time() < end_time:
        (match, text) = session.read_until_last_line_matches(
                        ["[Ii]s this [Oo][Kk]", prompt], timeout=timeout)
        if match == 0:
            logging.info("Got 'Is this ok'; sending 'y'")
            session.sendline("y")
        elif match == 1:
            logging.info("Got shell prompt")
            return True
        else:
            logging.info("Timeout or process exited")
            return False


def run_yum_update(test, params, env):
    """
    Runs yum update and yum update kernel on the remote host (yum enabled
    hosts only).

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = kvm_utils.env_get_vm(env, params.get("main_vm"))
    if not vm:
        message = "VM object not found in environment"
        logging.error(message)
        raise error.TestError(message)
    if not vm.is_alive():
        message = "VM seems to be dead; Test requires a living VM"
        logging.error(message)
        raise error.TestError(message)

    logging.info("Logging into guest...")

    session = kvm_utils.wait_for(vm.remote_login, 240, 0, 2)
    if not session:
        message = "Could not log into guest"
        logging.error(message)
        raise error.TestFail(message)

    logging.info("Logged in")

    internal_yum_update(session, "yum update", params.get("shell_prompt"), 600)
    internal_yum_update(session, "yum update kernel",
                        params.get("shell_prompt"), 600)

    session.close()


def run_linux_s3(test, params, env):
    """
    Suspend a guest Linux OS to memory.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = kvm_utils.env_get_vm(env, params.get("main_vm"))
    if not vm:
        raise error.TestError("VM object not found in environment")
    if not vm.is_alive():
        raise error.TestError("VM seems to be dead; Test requires a living VM")

    logging.info("Waiting for guest to be up...")

    session = kvm_utils.wait_for(vm.remote_login, 240, 0, 2)
    if not session:
        raise error.TestFail("Could not log into guest")

    logging.info("Logged in")
    logging.info("Checking that VM supports S3")

    status = session.get_command_status("grep -q mem /sys/power/state")
    if status == None:
        logging.error("Failed to check if S3 exists")
    elif status != 0:
        raise error.TestFail("Guest does not support S3")

    logging.info("Waiting for a while for X to start")
    time.sleep(10)

    src_tty = session.get_command_output("fgconsole").strip()
    logging.info("Current virtual terminal is %s" % src_tty)
    if src_tty not in map(str, range(1,10)):
        raise error.TestFail("Got a strange current vt (%s)" % src_tty)

    dst_tty = "1"
    if src_tty == "1":
        dst_tty = "2"

    logging.info("Putting VM into S3")
    command = "chvt %s && echo mem > /sys/power/state && chvt %s" % (dst_tty,
                                                                     src_tty)
    status = session.get_command_status(command, timeout=120)
    if status != 0:
        raise error.TestFail("Suspend to mem failed")

    logging.info("VM resumed after S3")

    session.close()


def run_stress_boot(tests, params, env):
    """
    Boots VMs until one of them becomes unresponsive, and records the maximum
    number of VMs successfully started:
    1) boot the first vm
    2) boot the second vm cloned from the first vm, check whether it boots up
       and all booted vms respond to shell commands
    3) go on until cannot create VM anymore or cannot allocate memory for VM

    @param test:   kvm test object
    @param params: Dictionary with the test parameters
    @param env:    Dictionary with test environment.
    """
    # boot the first vm
    vm = kvm_utils.env_get_vm(env, params.get("main_vm"))
    if not vm:
        raise error.TestError("VM object not found in environment")
    if not vm.is_alive():
        raise error.TestError("VM seems to be dead; Test requires a living VM")

    logging.info("Waiting for first guest to be up...")

    session = kvm_utils.wait_for(vm.remote_login, 240, 0, 2)
    if not session:
        raise error.TestFail("Could not log into first guest")

    num = 2
    sessions = [session]
    address_index = int(params.get("clone_address_index_base", 10))

    # boot the VMs
    while num <= int(params.get("max_vms")):
        try:
            vm_name = "vm" + str(num)

            # clone vm according to the first one
            vm_params = vm.get_params().copy()
            vm_params["address_index"] = str(address_index)
            curr_vm = vm.clone(vm_name, vm_params)
            kvm_utils.env_register_vm(env, vm_name, curr_vm)
            params['vms'] += " " + vm_name

            logging.info("Booting guest #%d" % num)
            if not curr_vm.create():
                raise error.TestFail("Cannot create VM #%d" % num)

            curr_vm_session = kvm_utils.wait_for(curr_vm.remote_login, 240, 0, 2)
            if not curr_vm_session:
                raise error.TestFail("Could not log into guest #%d" % num)

            logging.info("Guest #%d boots up successfully" % num)
            sessions.append(curr_vm_session)

            # check whether all previous shell sessions are responsive
            for i, se in enumerate(sessions):
                if se.get_command_status(params.get("alive_test_cmd")) != 0:
                    raise error.TestFail("Session #%d is not responsive" % i)
            num += 1
            address_index += 1

        except (error.TestFail, OSError):
            for se in sessions:
                se.close()
            logging.info("Total number booted: %d" % (num - 1))
            raise
    else:
        for se in sessions:
            se.close()
        logging.info("Total number booted: %d" % (num -1))


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

    vm = kvm_utils.env_get_vm(env, params.get("main_vm"))
    if not vm:
        raise error.TestError("VM object not found in environment")
    if not vm.is_alive():
        raise error.TestError("VM seems to be dead; Test requires a living VM")

    logging.info("Waiting for guest to be up...")

    session = kvm_utils.wait_for(vm.remote_login, 240, 0, 2)
    if not session:
        raise error.TestFail("Could not log into guest")

    logging.info("Logged in")

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
            # Set the CPU affinity of the shell running the load process
            pid = host_load_sessions[-1].get_shell_pid()
            set_cpu_affinity(pid, cpu_mask)
            # Try setting the CPU affinity of the load process itself
            pid = host_load_sessions[-1].get_pid()
            if pid:
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


def run_autoit(test, params, env):
    """
    A wrapper for AutoIt scripts.

    1) Log into a guest.
    2) Run AutoIt script.
    3) Wait for script execution to complete.
    4) Pass/fail according to exit status of script.

    @param test: KVM test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = kvm_utils.env_get_vm(env, params.get("main_vm"))
    if not vm:
        raise error.TestError("VM object not found in environment")
    if not vm.is_alive():
        raise error.TestError("VM seems to be dead; Test requires a living VM")

    logging.info("Waiting for guest to be up...")

    session = kvm_utils.wait_for(vm.remote_login, 240, 0, 2)
    if not session:
        raise error.TestFail("Could not log into guest")

    try:
        logging.info("Logged in; starting script...")

        # Collect test parameters
        binary = params.get("autoit_binary")
        script = params.get("autoit_script")
        script_params = params.get("autoit_script_params", "")
        timeout = float(params.get("autoit_script_timeout", 600))

        # Send AutoIt script to guest (this code will be replaced once we
        # support sending files to Windows guests)
        session.sendline("del script.au3")
        file = open(kvm_utils.get_path(test.bindir, script))
        for line in file.readlines():
            # Insert a '^' before each character
            line = "".join("^" + c for c in line.rstrip())
            if line:
                # Append line to the file
                session.sendline("echo %s>>script.au3" % line)
        file.close()

        session.read_up_to_prompt()

        command = "cmd /c %s script.au3 %s" % (binary, script_params)

        logging.info("---------------- Script output ----------------")
        status = session.get_command_status(command,
                                            print_func=logging.info,
                                            timeout=timeout)
        logging.info("---------------- End of script output ----------------")

        if status is None:
            raise error.TestFail("Timeout expired before script execution "
                                 "completed (or something weird happened)")
        if status != 0:
            raise error.TestFail("Script execution failed")

    finally:
        session.close()
