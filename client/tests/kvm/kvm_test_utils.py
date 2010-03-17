"""
High-level KVM test utility functions.

This module is meant to reduce code size by performing common test procedures.
Generally, code here should look like test code.
More specifically:
    - Functions in this module should raise exceptions if things go wrong
      (unlike functions in kvm_utils.py and kvm_vm.py which report failure via
      their returned values).
    - Functions in this module may use logging.info(), in addition to
      logging.debug() and logging.error(), to log messages the user may be
      interested in (unlike kvm_utils.py and kvm_vm.py which use
      logging.debug() for anything that isn't an error).
    - Functions in this module typically use functions and classes from
      lower-level modules (e.g. kvm_utils.py, kvm_vm.py, kvm_subprocess.py).
    - Functions in this module should not be used by lower-level modules.
    - Functions in this module should be used in the right context.
      For example, a function should not be used where it may display
      misleading or inaccurate info or debug messages.

@copyright: 2008-2009 Red Hat Inc.
"""

import time, os, logging, re, commands
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
import kvm_utils, kvm_vm, kvm_subprocess, scan_results


def get_living_vm(env, vm_name):
    """
    Get a VM object from the environment and make sure it's alive.

    @param env: Dictionary with test environment.
    @param vm_name: Name of the desired VM object.
    @return: A VM object.
    """
    vm = kvm_utils.env_get_vm(env, vm_name)
    if not vm:
        raise error.TestError("VM '%s' not found in environment" % vm_name)
    if not vm.is_alive():
        raise error.TestError("VM '%s' seems to be dead; test requires a "
                              "living VM" % vm_name)
    return vm


def wait_for_login(vm, nic_index=0, timeout=240, start=0, step=2):
    """
    Try logging into a VM repeatedly.  Stop on success or when timeout expires.

    @param vm: VM object.
    @param nic_index: Index of NIC to access in the VM.
    @param timeout: Time to wait before giving up.
    @return: A shell session object.
    """
    logging.info("Trying to log into guest '%s', timeout %ds", vm.name, timeout)
    session = kvm_utils.wait_for(lambda: vm.remote_login(nic_index=nic_index),
                                 timeout, start, step)
    if not session:
        raise error.TestFail("Could not log into guest '%s'" % vm.name)
    logging.info("Logged into guest '%s'" % vm.name)
    return session


def reboot(vm, session, method="shell", sleep_before_reset=10, nic_index=0,
           timeout=240):
    """
    Reboot the VM and wait for it to come back up by trying to log in until
    timeout expires.

    @param vm: VM object.
    @param session: A shell session object.
    @param method: Reboot method.  Can be "shell" (send a shell reboot
            command) or "system_reset" (send a system_reset monitor command).
    @param nic_index: Index of NIC to access in the VM, when logging in after
            rebooting.
    @param timeout: Time to wait before giving up (after rebooting).
    @return: A new shell session object.
    """
    if method == "shell":
        # Send a reboot command to the guest's shell
        session.sendline(vm.get_params().get("reboot_command"))
        logging.info("Reboot command sent. Waiting for guest to go down")
    elif method == "system_reset":
        # Sleep for a while before sending the command
        time.sleep(sleep_before_reset)
        # Send a system_reset monitor command
        vm.send_monitor_cmd("system_reset")
        logging.info("Monitor command system_reset sent. Waiting for guest to "
                     "go down")
    else:
        logging.error("Unknown reboot method: %s", method)

    # Wait for the session to become unresponsive and close it
    if not kvm_utils.wait_for(lambda: not session.is_responsive(timeout=30),
                              120, 0, 1):
        raise error.TestFail("Guest refuses to go down")
    session.close()

    # Try logging into the guest until timeout expires
    logging.info("Guest is down. Waiting for it to go up again, timeout %ds",
                 timeout)
    session = kvm_utils.wait_for(lambda: vm.remote_login(nic_index=nic_index),
                                 timeout, 0, 2)
    if not session:
        raise error.TestFail("Could not log into guest after reboot")
    logging.info("Guest is up again")
    return session


def migrate(vm, env=None):
    """
    Migrate a VM locally and re-register it in the environment.

    @param vm: The VM to migrate.
    @param env: The environment dictionary.  If omitted, the migrated VM will
            not be registered.
    @return: The post-migration VM.
    """
    # Helper functions
    def mig_finished():
        s, o = vm.send_monitor_cmd("info migrate")
        return s == 0 and not "Migration status: active" in o

    def mig_succeeded():
        s, o = vm.send_monitor_cmd("info migrate")
        return s == 0 and "Migration status: completed" in o

    def mig_failed():
        s, o = vm.send_monitor_cmd("info migrate")
        return s == 0 and "Migration status: failed" in o

    # See if migration is supported
    s, o = vm.send_monitor_cmd("help info")
    if not "info migrate" in o:
        raise error.TestError("Migration is not supported")

    # Clone the source VM and ask the clone to wait for incoming migration
    dest_vm = vm.clone()
    if not dest_vm.create(for_migration=True):
        raise error.TestError("Could not create dest VM")

    try:
        # Define the migration command
        cmd = "migrate -d tcp:localhost:%d" % dest_vm.migration_port
        logging.debug("Migrating with command: %s" % cmd)

        # Migrate
        s, o = vm.send_monitor_cmd(cmd)
        if s:
            logging.error("Migration command failed (command: %r, output: %r)"
                          % (cmd, o))
            raise error.TestFail("Migration command failed")

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
        if env is not None:
            kvm_utils.env_register_vm(env, vm.name, dest_vm)

        # Return the new cloned VM
        return dest_vm

    except:
        dest_vm.destroy()
        raise


def get_time(session, time_command, time_filter_re, time_format):
    """
    Return the host time and guest time.  If the guest time cannot be fetched
    a TestError exception is raised.

    Note that the shell session should be ready to receive commands
    (i.e. should "display" a command prompt and should be done with all
    previous commands).

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
    if not match:
        raise error.TestError("Could not get guest time")
    s = re.findall(time_filter_re, s)[0]
    guest_time = time.mktime(time.strptime(s, time_format))
    return (host_time, guest_time)


def get_memory_info(lvms):
    """
    Get memory information from host and guests in format:
    Host: memfree = XXXM; Guests memsh = {XXX,XXX,...}

    @params lvms: List of VM objects
    @return: String with memory info report
    """
    if not isinstance(lvms, list):
        raise error.TestError("Invalid list passed to get_stat: %s " % lvms)

    try:
        meminfo = "Host: memfree = "
        meminfo += str(int(utils.freememtotal()) / 1024) + "M; "
        meminfo += "swapfree = "
        mf = int(utils.read_from_meminfo("SwapFree")) / 1024
        meminfo += str(mf) + "M; "
    except Exception, e:
        raise error.TestFail("Could not fetch host free memory info, "
                             "reason: %s" % e)

    meminfo += "Guests memsh = {"
    for vm in lvms:
        shm = vm.get_shared_meminfo()
        if shm is None:
            raise error.TestError("Could not get shared meminfo from "
                                  "VM %s" % vm)
        meminfo += "%dM; " % shm
    meminfo = meminfo[0:-2] + "}"

    return meminfo


def run_autotest(vm, session, control_path, timeout, test_name, outputdir):
    """
    Run an autotest control file inside a guest (linux only utility).

    @param vm: VM object.
    @param session: A shell session on the VM provided.
    @param control: An autotest control file.
    @param timeout: Timeout under which the autotest test must complete.
    @param test_name: Autotest client test name.
    @param outputdir: Path on host where we should copy the guest autotest
            results to.
    """
    def copy_if_size_differs(vm, local_path, remote_path):
        """
        Copy a file to a guest if it doesn't exist or if its size differs.

        @param vm: VM object.
        @param local_path: Local path.
        @param remote_path: Remote path.
        """
        copy = False
        basename = os.path.basename(local_path)
        local_size = os.path.getsize(local_path)
        output = session.get_command_output("ls -l %s" % remote_path)
        if "such file" in output:
            logging.info("Copying %s to guest (remote file is missing)" %
                         basename)
            copy = True
        else:
            try:
                remote_size = output.split()[4]
                remote_size = int(remote_size)
            except IndexError, ValueError:
                logging.error("Check for remote path size %s returned %s. "
                              "Cannot process.", remote_path, output)
                raise error.TestFail("Failed to check for %s (Guest died?)" %
                                     remote_path)
            if remote_size != local_size:
                logging.debug("Copying %s to guest due to size mismatch"
                              "(remote size %s, local size %s)" %
                              (basename, remote_size, local_size))
                copy = True

        if copy:
            if not vm.copy_files_to(local_path, remote_path):
                raise error.TestFail("Could not copy %s to guest" % local_path)


    def extract(vm, remote_path, dest_dir="."):
        """
        Extract a .tar.bz2 file on the guest.

        @param vm: VM object
        @param remote_path: Remote file path
        @param dest_dir: Destination dir for the contents
        """
        basename = os.path.basename(remote_path)
        logging.info("Extracting %s..." % basename)
        (status, output) = session.get_command_status_output(
                                  "tar xjvf %s -C %s" % (remote_path, dest_dir))
        if status != 0:
            logging.error("Uncompress output:\n%s" % output)
            raise error.TestFail("Could not extract % on guest")

    if not os.path.isfile(control_path):
        raise error.TestError("Invalid path to autotest control file: %s" %
                              control_path)

    tarred_autotest_path = "/tmp/autotest.tar.bz2"
    tarred_test_path = "/tmp/%s.tar.bz2" % test_name

    # To avoid problems, let's make the test use the current AUTODIR
    # (autotest client path) location
    autotest_path = os.environ['AUTODIR']
    tests_path = os.path.join(autotest_path, 'tests')
    test_path = os.path.join(tests_path, test_name)

    # tar the contents of bindir/autotest
    cmd = "tar cvjf %s %s/*" % (tarred_autotest_path, autotest_path)
    cmd += " --exclude=%s/tests" % autotest_path
    cmd += " --exclude=%s/results" % autotest_path
    cmd += " --exclude=%s/tmp" % autotest_path
    cmd += " --exclude=%s/control" % autotest_path
    cmd += " --exclude=*.pyc"
    cmd += " --exclude=*.svn"
    cmd += " --exclude=*.git"
    utils.run(cmd)

    # tar the contents of bindir/autotest/tests/<test_name>
    cmd = "tar cvjf %s %s/*" % (tarred_test_path, test_path)
    cmd += " --exclude=*.pyc"
    cmd += " --exclude=*.svn"
    cmd += " --exclude=*.git"
    utils.run(cmd)

    # Copy autotest.tar.bz2
    copy_if_size_differs(vm, tarred_autotest_path, tarred_autotest_path)

    # Copy <test_name>.tar.bz2
    copy_if_size_differs(vm, tarred_test_path, tarred_test_path)

    # Extract autotest.tar.bz2
    extract(vm, tarred_autotest_path, "/")

    # mkdir autotest/tests
    session.get_command_output("mkdir -p %s" % tests_path)

    # Extract <test_name>.tar.bz2 into autotest/tests
    extract(vm, tarred_test_path, "/")

    if not vm.copy_files_to(control_path,
                            os.path.join(autotest_path, 'control')):
        raise error.TestFail("Could not copy the test control file to guest")

    # Run the test
    logging.info("Running test '%s'..." % test_name)
    session.get_command_output("cd %s" % autotest_path)
    session.get_command_output("rm -f control.state")
    session.get_command_output("rm -rf results/*")
    logging.info("---------------- Test output ----------------")
    status = session.get_command_status("bin/autotest control",
                                        timeout=timeout,
                                        print_func=logging.info)
    logging.info("--------------End of test output ------------")
    if status is None:
        raise error.TestFail("Timeout elapsed while waiting for autotest to "
                             "complete")

    # Get the results generated by autotest
    output = session.get_command_output("cat results/*/status")
    results = scan_results.parse_results(output)
    session.close

    # Copy test results to the local bindir/guest_results
    logging.info("Copying results back from guest...")
    guest_results_dir = os.path.join(outputdir, "guest_autotest_results")
    if not os.path.exists(guest_results_dir):
        os.mkdir(guest_results_dir)
    if not vm.copy_files_from("%s/results/default/*" % autotest_path,
                              guest_results_dir):
        logging.error("Could not copy results back from guest")

    # Report test results
    logging.info("Results (test, status, duration, info):")
    for result in results:
        logging.info(str(result))

    # Make a list of FAIL/ERROR/ABORT results (make sure FAIL results appear
    # before ERROR results, and ERROR results appear before ABORT results)
    bad_results = [r for r in results if r[1] == "FAIL"]
    bad_results += [r for r in results if r[1] == "ERROR"]
    bad_results += [r for r in results if r[1] == "ABORT"]

    # Fail the test if necessary
    if not results:
        raise error.TestFail("Test '%s' did not produce any recognizable "
                             "results" % test_name)
    if bad_results:
        result = bad_results[0]
        raise error.TestFail("Test '%s' ended with %s (reason: '%s')"
                             % (result[0], result[1], result[3]))
