import os, logging, re
from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import virt_test_utils


@error.context_aware
def run_cpu_hotplug(test, params, env):
    """
    Runs CPU hotplug test:

    1) Pick up a living guest
    2) Send the monitor command cpu_set [cpu id] for each cpu we wish to have
    3) Verify if guest has the additional CPUs showing up under
        /sys/devices/system/cpu
    4) Try to bring them online by writing 1 to the 'online' file inside that dir
    5) Run the CPU Hotplug test suite shipped with autotest inside guest

    @param test: KVM test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

    n_cpus_add = int(params.get("n_cpus_add", 1))
    current_cpus = int(params.get("smp", 1))
    onoff_iterations = int(params.get("onoff_iterations", 20))
    total_cpus = current_cpus + n_cpus_add

    error.context("getting guest dmesg before addition")
    dmesg_before = session.cmd("dmesg -c")

    error.context("Adding %d CPUs to guest" % n_cpus_add)
    for i in range(total_cpus):
        vm.monitor.cmd("cpu_set %s online" % i)

    output = vm.monitor.cmd("info cpus")
    logging.debug("Output of info cpus:\n%s", output)

    cpu_regexp = re.compile("CPU #(\d+)")
    total_cpus_monitor = len(cpu_regexp.findall(output))
    if total_cpus_monitor != total_cpus:
        raise error.TestFail("Monitor reports %s CPUs, when VM should have %s" %
                             (total_cpus_monitor, total_cpus))

    dmesg_after = session.cmd("dmesg -c")
    logging.debug("Guest dmesg output after CPU add:\n%s" % dmesg_after)

    # Verify whether the new cpus are showing up on /sys
    error.context("verifying if new CPUs are showing on guest's /sys dir")
    n_cmd = 'find /sys/devices/system/cpu/cpu[0-99] -maxdepth 0 -type d | wc -l'
    output = session.cmd(n_cmd)
    logging.debug("List of cpus on /sys:\n%s" % output)
    try:
        cpus_after_addition = int(output)
    except ValueError:
        logging.error("Output of '%s': %s", n_cmd, output)
        raise error.TestFail("Unable to get CPU count after CPU addition")

    if cpus_after_addition != total_cpus:
        raise error.TestFail("%s CPUs are showing up under "
                             "/sys/devices/system/cpu, was expecting %s" %
                             (cpus_after_addition, total_cpus))

    error.context("locating online files for guest's new CPUs")
    r_cmd = 'find /sys/devices/system/cpu/cpu[1-99]/online -maxdepth 0 -type f'
    online_files = session.cmd(r_cmd)
    logging.debug("CPU online files detected: %s", online_files)
    online_files = online_files.split().sort()

    if not online_files:
        raise error.TestFail("Could not find CPUs that can be "
                             "enabled/disabled on guest")

    for online_file in online_files:
        cpu_regexp = re.compile("cpu(\d+)", re.IGNORECASE)
        cpu_id = cpu_regexp.findall(online_file)[0]
        error.context("changing online status for CPU %s" % cpu_id)
        check_online_status = session.cmd("cat %s" % online_file)
        try:
            check_online_status = int(check_online_status)
        except ValueError:
            raise error.TestFail("Unable to get online status from CPU %s" %
                                 cpu_id)
        assert(check_online_status in [0, 1])
        if check_online_status == 0:
            error.context("Bringing CPU %s online" % cpu_id)
            session.cmd("echo 1 > %s" % online_file)

    # Now that all CPUs were onlined, let's execute the
    # autotest CPU Hotplug test
    control_path = os.path.join(test.bindir, "autotest_control",
                                "cpu_hotplug.control")

    timeout = int(params.get("cpu_hotplug_timeout"), 300)
    error.context("running cpu_hotplug autotest after cpu addition")
    virt_test_utils.run_autotest(vm, session, control_path, timeout,
                                 test.outputdir, params)

    # Last, but not least, let's offline/online the CPUs in the guest
    # several times
    irq = 15
    irq_mask = "f0"
    for i in xrange(onoff_iterations):
        session.cmd("echo %s > /proc/irq/%s/smp_affinity" % (irq_mask, irq))
        for online_file in online_files:
            session.cmd("echo 0 > %s" % online_file)
        for online_file in online_files:
            session.cmd("echo 1 > %s" % online_file)
