import logging, time
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils, kvm_utils, kvm_preprocessing


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
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))

    logging.info("Waiting for first guest to be up...")

    boot_timeout = float(params.get("boot_timeout", 240))
    session = kvm_utils.wait_for(vm.remote_login, boot_timeout, 0, 2)
    if not session:
        raise error.TestFail("Could not log into first guest")

    num = 2
    sessions = [session]
    address_index = int(params.get("clone_address_index_base", 10))

    # boot the VMs
    while num <= int(params.get("max_vms")):
        try:
            # clone vm according to the first one
            vm_name = "vm" + str(num)
            vm_params = vm.get_params().copy()
            vm_params["address_index"] = str(address_index)
            curr_vm = vm.clone(vm_name, vm_params)
            kvm_utils.env_register_vm(env, vm_name, curr_vm)
            logging.info("Booting guest #%d" % num)
            kvm_preprocessing.preprocess_vm(tests, vm_params, env, vm_name)
            params['vms'] += " " + vm_name

            curr_vm_session = kvm_utils.wait_for(curr_vm.remote_login,
                                                 boot_timeout, 0, 2)
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
