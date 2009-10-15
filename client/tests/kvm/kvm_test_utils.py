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
from autotest_lib.client.common_lib import utils, error
import kvm_utils, kvm_vm, kvm_subprocess


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
    logging.info("Trying to log into guest '%s'..." % vm.name)
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
        logging.info("Reboot command sent; waiting for guest to go down...")
    elif method == "system_reset":
        # Sleep for a while before sending the command
        time.sleep(sleep_before_reset)
        # Send a system_reset monitor command
        vm.send_monitor_cmd("system_reset")
        logging.info("system_reset monitor command sent; waiting for guest to "
                     "go down...")
    else:
        logging.error("Unknown reboot method: %s" % method)

    # Wait for the session to become unresponsive and close it
    if not kvm_utils.wait_for(lambda: not session.is_responsive(), 120, 0, 1):
        raise error.TestFail("Guest refuses to go down")
    session.close()

    # Try logging into the guest until timeout expires
    logging.info("Guest is down; waiting for it to go up again...")
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
    dest_vm.create(for_migration=True)

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
