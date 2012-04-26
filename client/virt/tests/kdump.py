import logging
from autotest.client.shared import error
from autotest.client.virt import virt_utils


def run_kdump(test, params, env):
    """
    KVM reboot test:
    1) Log into a guest
    2) Check and enable the kdump
    3) Trigger a crash by 'sysrq-trigger' and check the vmcore for
       each vcpu, or only trigger one crash with nmi interrupt and
       check vmcore.

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = float(params.get("login_timeout", 240))
    crash_timeout = float(params.get("crash_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)
    def_kernel_param_cmd = ("grubby --update-kernel=`grubby --default-kernel`"
                            " --args=crashkernel=128M@16M")
    kernel_param_cmd = params.get("kernel_param_cmd", def_kernel_param_cmd)
    def_kdump_enable_cmd = "chkconfig kdump on && service kdump start"
    kdump_enable_cmd = params.get("kdump_enable_cmd", def_kdump_enable_cmd)
    def_crash_kernel_prob_cmd = "grep -q 1 /sys/kernel/kexec_crash_loaded"
    crash_kernel_prob_cmd = params.get("crash_kernel_prob_cmd",
                                       def_crash_kernel_prob_cmd)

    def crash_test(vcpu):
        """
        Trigger a crash dump through sysrq-trigger

        @param vcpu: vcpu which is used to trigger a crash
        """
        session = vm.wait_for_login(timeout=timeout)
        session.cmd_output("rm -rf /var/crash/*")

        if crash_cmd == "nmi":
            session.cmd("echo 1 > /proc/sys/kernel/unknown_nmi_panic")
            vm.monitor.cmd('nmi')
        else:
            logging.info("Triggering crash on vcpu %d ...", vcpu)
            session.sendline("taskset -c %d %s" % (vcpu, crash_cmd))

        if not virt_utils.wait_for(lambda: not session.is_responsive(), 240, 0,
                                  1):
            raise error.TestFail("Could not trigger crash on vcpu %d" % vcpu)

        logging.info("Waiting for kernel crash dump to complete")
        session = vm.wait_for_login(timeout=crash_timeout)

        logging.info("Probing vmcore file...")
        session.cmd("ls -R /var/crash | grep vmcore")
        logging.info("Found vmcore.")

        session.cmd_output("rm -rf /var/crash/*")

    try:
        logging.info("Checking the existence of crash kernel...")
        try:
            session.cmd(crash_kernel_prob_cmd)
        except Exception:
            logging.info("Crash kernel is not loaded. Trying to load it")
            session.cmd(kernel_param_cmd)
            session = vm.reboot(session, timeout=timeout)

        logging.info("Enabling kdump service...")
        # the initrd may be rebuilt here so we need to wait a little more
        session.cmd(kdump_enable_cmd, timeout=120)

        crash_cmd = params.get("crash_cmd", "echo c > /proc/sysrq-trigger")
        if crash_cmd == "nmi":
            crash_test(None)
        else:
            # trigger crash for each vcpu
            nvcpu = int(params.get("smp", 1))
            for i in range (nvcpu):
                crash_test(i)

    finally:
        session.close()
