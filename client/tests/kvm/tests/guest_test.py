import os, logging
from autotest_lib.client.common_lib import error
import kvm_utils, kvm_test_utils


def run_guest_test(test, params, env):
    """
    A wrapper for running customized tests in guests.

    1) Log into a guest.
    2) Run script.
    3) Wait for script execution to complete.
    4) Pass/fail according to exit status of script.

    @param test: KVM test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    login_timeout = int(params.get("login_timeout", 360))
    reboot = params.get("reboot", "no")

    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm, timeout=login_timeout)

    if reboot == "yes":
        logging.debug("Rebooting guest before test ...")
        session = kvm_test_utils.reboot(vm, session, timeout=login_timeout)

    try:
        logging.info("Starting script...")

        # Collect test parameters
        interpreter = params.get("interpreter")
        script = params.get("guest_script")
        dst_rsc_path = params.get("dst_rsc_path", "script.au3")
        script_params = params.get("script_params", "")
        test_timeout = float(params.get("test_timeout", 600))

        logging.debug("Starting preparing resouce files...")
        # Download the script resource from a remote server, or
        # prepare the script using rss?
        if params.get("download") == "yes":
            download_cmd = params.get("download_cmd")
            rsc_server = params.get("rsc_server")
            rsc_dir = os.path.basename(rsc_server)
            dst_rsc_dir = params.get("dst_rsc_dir")

            # Change dir to dst_rsc_dir, and remove the guest script dir there
            rm_cmd = "cd %s && (rmdir /s /q %s || del /s /q %s)" % \
                     (dst_rsc_dir, rsc_dir, rsc_dir)
            if session.get_command_status(rm_cmd, timeout=test_timeout) != 0:
                raise error.TestFail("Remove %s failed." % rsc_dir)
            logging.debug("Clean directory succeeded.")

            # then download the resource.
            rsc_cmd = "cd %s && %s %s" %(dst_rsc_dir, download_cmd, rsc_server)
            if session.get_command_status(rsc_cmd, timeout=test_timeout) != 0:
                raise error.TestFail("Download test resource failed.")
            logging.info("Download resource finished.")
        else:
            session.get_command_output("del %s" % dst_rsc_path,
                                       internal_timeout=0)
            script_path = kvm_utils.get_path(test.bindir, script)
            vm.copy_files_to(script_path, dst_rsc_path, timeout=60)

        command = "%s %s %s" %(interpreter, dst_rsc_path, script_params)

        logging.info("---------------- Script output ----------------")
        status = session.get_command_status(command,
                                            print_func=logging.info,
                                            timeout=test_timeout)
        logging.info("---------------- End of script output ----------------")

        if status is None:
            raise error.TestFail("Timeout expired before script execution "
                                 "completed (or something weird happened)")
        if status != 0:
            raise error.TestFail("Script execution failed")

        if reboot == "yes":
            logging.debug("Rebooting guest after test ...")
            session = kvm_test_utils.reboot(vm, session, timeout=login_timeout)

        logging.debug("guest test PASSED.")
    finally:
        session.close()
