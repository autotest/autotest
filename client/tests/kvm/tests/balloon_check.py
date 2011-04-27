import re, logging, random, time
from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import kvm_monitor


def run_balloon_check(test, params, env):
    """
    Check Memory ballooning:
    1) Boot a guest
    2) Change the memory between 60% to 95% of memory of guest using ballooning
    3) check memory info

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    def check_ballooned_memory():
        """
        Verify the actual memory reported by monitor command info balloon. If
        the operation failed, increase the failure counter.

        @return: Number of failures occurred during operation.
        """
        fail = 0
        try:
            output = vm.monitor.info("balloon")
        except kvm_monitor.MonitorError, e:
            logging.error(e)
            fail += 1
            return 0
        return int(re.findall("\d+", output)[0]), fail


    def balloon_memory(new_mem):
        """
        Baloon memory to new_mem and verifies on both qemu monitor and
        guest OS if change worked.

        @param new_mem: New desired memory.
        @return: Number of failures occurred during operation.
        """
        fail = 0
        logging.info("Changing VM memory to %s", new_mem)
        # This should be replaced by proper monitor method call
        vm.monitor.cmd("balloon %s" % new_mem)
        time.sleep(20)

        ballooned_mem, cfail = check_ballooned_memory()
        fail += cfail
        # Verify whether the VM machine reports the correct new memory
        if ballooned_mem != new_mem:
            logging.error("Memory ballooning failed while changing memory "
                          "to %s", new_mem)
            fail += 1

        # Verify whether the guest OS reports the correct new memory
        current_mem_guest = vm.get_current_memory_size()

        # Current memory figures will allways be a little smaller than new
        # memory. If they are higher, ballooning failed on guest perspective
        if current_mem_guest > new_mem:
            logging.error("Guest OS reports %s of RAM, but new ballooned RAM "
                          "is %s", current_mem_guest, new_mem)
            fail += 1
        return fail


    fail = 0
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

    # Upper limit that we can raise the memory
    vm_assigned_mem = int(params.get("mem"))

    # Check memory size
    logging.info("Memory check")
    boot_mem = vm.get_memory_size()
    if boot_mem != vm_assigned_mem:
        logging.error("Memory size mismatch:")
        logging.error("    Assigned to VM: %s", vm_assigned_mem)
        logging.error("    Reported by guest OS at boot: %s", boot_mem)
        fail += 1

    # Check if info balloon works or not
    current_vm_mem, cfail = check_ballooned_memory()
    if cfail:
        fail += cfail
    if current_vm_mem:
        logging.info("Current VM memory according to ballooner: %s",
                     current_vm_mem)

    # Reduce memory to random size between 60% to 95% of max memory size
    percent = random.uniform(0.6, 0.95)
    new_mem = int(percent * vm_assigned_mem)
    fail += balloon_memory(new_mem)

    # Reset memory value to original memory assigned on qemu. This will ensure
    # we won't trigger guest OOM killer while running multiple iterations
    fail += balloon_memory(vm_assigned_mem)

    # Close stablished session
    session.close()
    # Check if any failures happen during the whole test
    if fail != 0:
        raise error.TestFail("Memory ballooning test failed")
