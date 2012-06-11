import re, logging, random, time
from autotest.client.shared import error
from autotest.client.virt import kvm_monitor, virt_test_utils


def run_balloon_check(test, params, env):
    """
    Check Memory ballooning:
    1) Boot a guest
    2) Change the memory between MemFree to Assigned memory of memory
       of guest using ballooning
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
            return 0, fail
        return int(re.findall("\d+", str(output))[0]), fail

    def balloon_memory(new_mem, offset):
        """
        Baloon memory to new_mem and verifies on both qemu monitor and
        guest OS if change worked.

        @param new_mem: New desired memory.
        @return: Number of failures occurred during operation.
        """
        fail = 0
        cur_mem, fail = check_ballooned_memory()
        if params.get("monitor_type") == "qmp":
            new_mem = new_mem * 1024 * 1024
        logging.info("Changing VM memory to %s", new_mem)
        # This should be replaced by proper monitor method call
        vm.monitor.send_args_cmd("balloon value=%s" % new_mem)
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
        fail += cfail
        current_mem_guest = current_mem_guest + offset
        if params.get("monitor_type") == "qmp":
            current_mem_guest = current_mem_guest * 1024 * 1024
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
    balloon_chk_cmd = params.get("balloon_chk_cmd")

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
    # Get the offset of memory report by guest system
    guest_memory = vm.get_current_memory_size()
    offset = vm_assigned_mem - guest_memory

    # Reduce memory to random size between Free memory
    # to max memory size
    s, o = session.cmd_status_output("cat /proc/meminfo")
    if s != 0:
        raise error.TestError("Can not get guest memory information")

    vm_mem_free = int(re.findall('MemFree:\s+(\d+).*', o)[0]) / 1024

    new_mem = int(random.uniform(vm_assigned_mem - vm_mem_free, vm_assigned_mem))
    fail += balloon_memory(new_mem, offset)
    # Run option test after evict memory
    if params.has_key('sub_balloon_test_evict'):
        balloon_test = params['sub_balloon_test_evict']
        virt_test_utils.run_virt_sub_test(test, params, env, sub_type=balloon_test)
        if balloon_test == "shutdown" :
            logging.info("Guest shutdown normally after balloon")
            return
    # Reset memory value to original memory assigned on qemu. This will ensure
    # we won't trigger guest OOM killer while running multiple iterations
    fail += balloon_memory(vm_assigned_mem, offset)

    # Run sub test after enlarge memory
    if params.has_key('sub_balloon_test_enlarge'):
        balloon_test = params['sub_balloon_test_enlarge']
        virt_test_utils.run_virt_sub_test(test, params, env, sub_type=balloon_test)
        if balloon_test == "shutdown" :
            logging.info("Guest shutdown normally after balloon")
            return

    #Check memory after sub test running
    logging.info("Check memory after tests")
    boot_mem = vm.get_memory_size()
    if boot_mem != vm_assigned_mem:
        fail += 1
    # Check if info balloon works or not
    current_vm_mem, cfail = check_ballooned_memory()
    if params.get("monitor_type") == "qmp":
        current_vm_mem = current_vm_mem / 1024 / 1024
    if current_vm_mem != vm_assigned_mem:
        fail += 1
    logging.error("Memory size after tests:")
    logging.error("    Assigned to VM: %s", vm_assigned_mem)
    logging.error("    Reported by guest OS: %s", boot_mem)
    logging.error("    Reported by monitor: %s", current_vm_mem)

    # Close stablished session
    session.close()
    # Check if any failures happen during the whole test
    if fail != 0:
        raise error.TestFail("Memory ballooning test failed")
