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
    login_timeout = int(params.get("login_timeout", 360))

    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm, timeout=login_timeout)

    try:
        logging.info("Starting script...")

        # Collect test parameters
        binary = params.get("autoit_binary")
        script = params.get("autoit_script")
        autoit_entry = params.get("autoit_entry", "script.au3")
        script_params = params.get("autoit_script_params", "")
        timeout = float(params.get("autoit_script_timeout", 600))

        # Download the script resource from a remote server, or
        # prepare the script using rss?
        if params.get("download") == "yes":
            download_cmd = params.get("download_cmd")
            rsc_server = params.get("rsc_server")
            rsc_dir = os.path.basename(rsc_server)
            dst_rsc_dir = params.get("dst_rsc_dir")

            # Change dir to dst_rsc_dir, and remove 'autoit' there,
            rm_cmd = "cd %s && (rmdir /s /q %s || del /s /q %s)" % \
                     (dst_rsc_dir, rsc_dir, rsc_dir)
            if session.get_command_status(rm_cmd, timeout=timeout) != 0:
                raise error.TestFail("Remove %s failed." % rsc_dir)
            logging.debug("Clean directory succeeded.")

            # then download the resource.
            rsc_cmd = "cd %s && %s %s" %(dst_rsc_dir, download_cmd, rsc_server)
            if session.get_command_status(rsc_cmd, timeout=timeout) != 0:
                raise error.TestFail("Download test resource failed.")
            logging.info("Download resource finished.")
        else:
            # Send AutoIt script to guest (this code will be replaced once we
            # support sending files to Windows guests)
            session.get_command_output("del script.au3", internal_timeout=0)
            file = open(kvm_utils.get_path(test.bindir, script))
            for line in file.readlines():
                # Insert a '^' before each character
                line = "".join("^" + c for c in line.rstrip())
                if line:
                    # Append line to the file
                    session.get_command_output("echo %s>>script.au3" % line,
                                               internal_timeout=0)
            file.close()

        command = "cmd /c %s %s %s" % (binary, autoit_entry, script_params)

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
