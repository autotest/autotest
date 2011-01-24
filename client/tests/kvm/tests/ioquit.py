import logging, time, random


def run_ioquit(test, params, env):
    """
    Emulate the poweroff under IO workload(dd so far) using kill -9.

    @param test: Kvm test object
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    login_timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=login_timeout)
    session2 = vm.wait_for_login(timeout=login_timeout)
    try:
        bg_cmd = params.get("background_cmd")
        logging.info("Add IO workload for guest OS.")
        session.cmd_output(bg_cmd, timeout=60)
        check_cmd = params.get("check_cmd")
        session2.cmd(check_cmd, timeout=60)

        logging.info("Sleep for a while")
        time.sleep(random.randrange(30, 100))
        session2.cmd(check_cmd, timeout=60)
        logging.info("Kill the virtual machine")
        vm.process.close()
    finally:
        session.close()
        session2.close()
