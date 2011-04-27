import logging
from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import virt_utils


def run_kdump(test, params, env):
    """
    KVM reboot test:
    1) Log into a guest
    2) Check and enable the kdump
    3) For each vcpu, trigger a crash and check the vmcore

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
                            " --args=crashkernel=128M")
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

        logging.info("Triggering crash on vcpu %d ...", vcpu)
        crash_cmd = "taskset -c %d echo c > /proc/sysrq-trigger" % vcpu
        session.sendline(crash_cmd)

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
        except:
            logging.info("Crash kernel is not loaded. Trying to load it")
            session.cmd(kernel_param_cmd)
            session = vm.reboot(session, timeout=timeout)

        logging.info("Enabling kdump service...")
        # the initrd may be rebuilt here so we need to wait a little more
        session.cmd(kdump_enable_cmd, timeout=120)

        nvcpu = int(params.get("smp", 1))
        for i in range (nvcpu):
            crash_test(i)

    finally:
        session.close()
