import logging
from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import virt_env_process


@error.context_aware
def run_stress_boot(test, params, env):
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
    error.base_context("waiting for the first guest to be up", logging.info)
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    login_timeout = float(params.get("login_timeout", 240))
    session = vm.wait_for_login(timeout=login_timeout)

    num = 2
    sessions = [session]

    # Boot the VMs
    try:
        while num <= int(params.get("max_vms")):
            # Clone vm according to the first one
            error.base_context("booting guest #%d" % num, logging.info)
            vm_name = "vm%d" % num
            vm_params = vm.params.copy()
            curr_vm = vm.clone(vm_name, vm_params)
            env.register_vm(vm_name, curr_vm)
            virt_env_process.preprocess_vm(test, vm_params, env, vm_name)
            params["vms"] += " " + vm_name

            sessions.append(curr_vm.wait_for_login(timeout=login_timeout))
            logging.info("Guest #%d booted up successfully", num)

            # Check whether all previous shell sessions are responsive
            for i, se in enumerate(sessions):
                error.context("checking responsiveness of guest #%d" % (i + 1),
                              logging.debug)
                se.cmd(params.get("alive_test_cmd"))
            num += 1
    finally:
        for se in sessions:
            se.close()
        logging.info("Total number booted: %d" % (num -1))
