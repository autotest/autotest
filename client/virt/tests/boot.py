import time


def run_boot(test, params, env):
    """
    KVM reboot test:
    1) Log into a guest
    2) Send a reboot command or a system_reset monitor command (optional)
    3) Wait until the guest is up again
    4) Log into the guest to verify it's up again

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = float(params.get("login_timeout", 240))
    session = vm.wait_for_login(timeout=timeout)

    if params.get("reboot_method"):
        if params["reboot_method"] == "system_reset":
            time.sleep(int(params.get("sleep_before_reset", 10)))
        session = vm.reboot(session, params["reboot_method"], 0, timeout)

    session.close()
