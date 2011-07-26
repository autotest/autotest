import time, logging
from autotest_lib.client.common_lib import error


@error.context_aware
def run_nmi_watchdog(test, params, env):
    """
    Test the function of nmi injection and verify the response of guest

    1) Log in the guest
    2) Add 'watchdog=1' to boot option
    2) Check if guest's NMI counter augment after injecting nmi

    @param test: kvm test object
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout=int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)
    get_nmi_cmd= params.get("get_nmi_cmd")
    kernel_version = session.get_command_output("uname -r").strip()
    nmi_watchdog_type = int(params.get("nmi_watchdog_type"))
    update_kernel_cmd = ("grubby --update-kernel=/boot/vmlinuz-%s "
                         "--args='nmi_watchdog=%d'" %
                         (kernel_version, nmi_watchdog_type))

    error.context("Add 'nmi_watchdog=%d' to guest kernel cmdline and reboot"
                  % nmi_watchdog_type)
    session.cmd(update_kernel_cmd)
    time.sleep(int(params.get("sleep_before_reset", 10)))
    session = vm.reboot(session, method='shell', timeout=timeout)
    try:
        error.context("Getting guest's number of vcpus")
        guest_cpu_num = session.cmd(params.get("cpu_chk_cmd"))

        error.context("Getting guest's NMI counter")
        output = session.cmd(get_nmi_cmd)
        logging.debug(output.strip())
        nmi_counter1 = output.split()[1:]

        logging.info("Waiting 60 seconds to see if guest's NMI counter "
                     "increases")
        time.sleep(60)

        error.context("Getting guest's NMI counter 2nd time")
        output = session.cmd(get_nmi_cmd)
        logging.debug(output.strip())
        nmi_counter2 = output.split()[1:]

        error.context("")
        for i in range(int(guest_cpu_num)):
            logging.info("vcpu: %s, nmi_counter1: %s, nmi_counter2: %s" %
                         (i, nmi_counter1[i], nmi_counter2[i]))
            if int(nmi_counter2[i]) <= int(nmi_counter1[i]):
                raise error.TestFail("Guest's NMI counter did not increase "
                                     "after 60 seconds")
    finally:
        session.close()
