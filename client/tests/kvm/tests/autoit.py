import os, logging
from autotest_lib.client.common_lib import error
import kvm_utils, kvm_test_utils


def run_autoit(test, params, env):
    """
    A wrapper for AutoIt scripts.

    1) Log into a guest.
    2) Run AutoIt script.
    3) Wait for script execution to complete.
    4) Pass/fail according to exit status of script.

    @param test: KVM test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm)

    try:
        logging.info("Starting script...")

        # Collect test parameters
        binary = params.get("autoit_binary")
        script = params.get("autoit_script")
        script_params = params.get("autoit_script_params", "")
        timeout = float(params.get("autoit_script_timeout", 600))

        # Send AutoIt script to guest (this code will be replaced once we
        # support sending files to Windows guests)
        session.sendline("del script.au3")
        file = open(kvm_utils.get_path(test.bindir, script))
        for line in file.readlines():
            # Insert a '^' before each character
            line = "".join("^" + c for c in line.rstrip())
            if line:
                # Append line to the file
                session.sendline("echo %s>>script.au3" % line)
        file.close()

        session.read_up_to_prompt()

        command = "cmd /c %s script.au3 %s" % (binary, script_params)

        logging.info("---------------- Script output ----------------")
        status = session.get_command_status(command,
                                            print_func=logging.info,
                                            timeout=timeout)
        logging.info("---------------- End of script output ----------------")

        if status is None:
            raise error.TestFail("Timeout expired before script execution "
                                 "completed (or something weird happened)")
        if status != 0:
            raise error.TestFail("Script execution failed")

    finally:
        session.close()
