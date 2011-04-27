import os, logging
from autotest_lib.client.virt import virt_utils


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

    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    if params.get("serial_login") == "yes":
        session = vm.wait_for_serial_login(timeout=login_timeout)
    else:
        session = vm.wait_for_login(timeout=login_timeout)

    if reboot == "yes":
        logging.debug("Rebooting guest before test ...")
        session = vm.reboot(session, timeout=login_timeout)

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
            session.cmd(rm_cmd, timeout=test_timeout)
            logging.debug("Clean directory succeeded.")

            # then download the resource.
            rsc_cmd = "cd %s && %s %s" % (dst_rsc_dir, download_cmd, rsc_server)
            session.cmd(rsc_cmd, timeout=test_timeout)
            logging.info("Download resource finished.")
        else:
            session.cmd_output("del %s" % dst_rsc_path, internal_timeout=0)
            script_path = virt_utils.get_path(test.bindir, script)
            vm.copy_files_to(script_path, dst_rsc_path, timeout=60)

        cmd = "%s %s %s" % (interpreter, dst_rsc_path, script_params)

        try:
            logging.info("------------ Script output ------------")
            session.cmd(cmd, print_func=logging.info, timeout=test_timeout)
        finally:
            logging.info("------------ End of script output ------------")

        if reboot == "yes":
            logging.debug("Rebooting guest after test ...")
            session = vm.reboot(session, timeout=login_timeout)

        logging.debug("guest test PASSED.")
    finally:
        session.close()
