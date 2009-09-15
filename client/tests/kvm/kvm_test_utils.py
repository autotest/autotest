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


def wait_for_login(vm, nic_index=0, timeout=240):
    """
    Try logging into a VM repeatedly.  Stop on success or when timeout expires.

    @param vm: VM object.
    @param nic_index: Index of NIC to access in the VM.
    @param timeout: Time to wait before giving up.
    @return: A shell session object.
    """
    logging.info("Waiting for guest '%s' to be up..." % vm.name)
    session = kvm_utils.wait_for(lambda: vm.remote_login(nic_index=nic_index),
                                 timeout, 0, 2)
    if not session:
        raise error.TestFail("Could not log into guest '%s'" % vm.name)
    logging.info("Logged in")
    return session
