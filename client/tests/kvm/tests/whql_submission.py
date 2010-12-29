import logging, time, os, re
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils, kvm_utils, rss_file_transfer


def run_whql_submission(test, params, env):
    """
    WHQL submission test:
    1) Log into the guest (the client machine) and into a DTM server machine
    2) Copy the automation program binary (dsso_test_binary) to the server machine
    3) Run the automation program
    4) Pass the program all relevant parameters (e.g. device_data)
    5) Wait for the program to terminate
    6) Parse and report job results
    (logs and HTML reports are placed in test.bindir)

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm, 0, 240)

    # Collect parameters
    server_address = params.get("server_address")
    server_shell_port = int(params.get("server_shell_port"))
    server_file_transfer_port = int(params.get("server_file_transfer_port"))
    server_studio_path = params.get("server_studio_path", "%programfiles%\\ "
                                    "Microsoft Driver Test Manager\\Studio")
    dsso_test_binary = params.get("dsso_test_binary",
                                  "deps/whql_submission_15.exe")
    dsso_test_binary = kvm_utils.get_path(test.bindir, dsso_test_binary)
    test_device = params.get("test_device")
    job_filter = params.get("job_filter", ".*")
    test_timeout = float(params.get("test_timeout", 600))
    wtt_services = params.get("wtt_services")

    # Restart WTT service(s) on the client
    logging.info("Restarting WTT services on client")
    for svc in wtt_services.split():
        kvm_test_utils.stop_windows_service(session, svc)
    for svc in wtt_services.split():
        kvm_test_utils.start_windows_service(session, svc)

    # Run whql_pre_command
    if params.get("whql_pre_command"):
        session.cmd(params.get("whql_pre_command"),
                    int(params.get("whql_pre_command_timeout", 600)))

    # Copy dsso_test_binary to the server
    rss_file_transfer.upload(server_address, server_file_transfer_port,
                             dsso_test_binary, server_studio_path, timeout=60)

    # Open a shell session with the server
    server_session = kvm_utils.remote_login("nc", server_address,
                                            server_shell_port, "", "",
                                            session.prompt, session.linesep)
    server_session.set_status_test_command(session.status_test_command)

    # Get the computer names of the server and client
    cmd = "echo %computername%"
    server_name = server_session.cmd_output(cmd).strip()
    client_name = session.cmd_output(cmd).strip()
    session.close()

    # Run the automation program on the server
    server_session.cmd("cd %s" % server_studio_path)
    cmd = "%s %s %s %s %s %s" % (os.path.basename(dsso_test_binary),
                                 server_name,
                                 client_name,
                                 "%s_pool" % client_name,
                                 "%s_submission" % client_name,
                                 test_timeout)
    server_session.sendline(cmd)

    # Helper function: wait for a given prompt and raise an exception if an
    # error occurs
    def find_prompt(prompt):
        m, o = server_session.read_until_last_line_matches(
            [prompt, server_session.prompt], print_func=logging.info,
            timeout=600)
        if m != 0:
            errors = re.findall("^Error:.*$", o, re.I | re.M)
            if errors:
                raise error.TestError(errors[0])
            else:
                raise error.TestError("Error running automation program: "
                                      "could not find '%s' prompt" % prompt)

    # Tell the automation program which device to test
    find_prompt("Device to test:")
    server_session.sendline(test_device)

    # Tell the automation program which jobs to run
    find_prompt("Jobs to run:")
    server_session.sendline(job_filter)

    # Give the automation program all the device data supplied by the user
    find_prompt("DeviceData name:")
    for dd in kvm_utils.get_sub_dict_names(params, "device_data"):
        dd_params = kvm_utils.get_sub_dict(params, dd)
        if dd_params.get("dd_name") and dd_params.get("dd_data"):
            server_session.sendline(dd_params.get("dd_name"))
            server_session.sendline(dd_params.get("dd_data"))
    server_session.sendline()

    # Give the automation program all the descriptor information supplied by
    # the user
    find_prompt("Descriptor path:")
    for desc in kvm_utils.get_sub_dict_names(params, "descriptors"):
        desc_params = kvm_utils.get_sub_dict(params, desc)
        if desc_params.get("desc_path"):
            server_session.sendline(desc_params.get("desc_path"))
    server_session.sendline()

    # Wait for the automation program to terminate
    try:
        o = server_session.read_up_to_prompt(print_func=logging.info,
                                             timeout=test_timeout + 300)
        # (test_timeout + 300 is used here because the automation program is
        # supposed to terminate cleanly on its own when test_timeout expires)
        done = True
    except kvm_subprocess.ExpectError, e:
        o = e.output
        done = False
    server_session.close()

    # Look for test results in the automation program's output
    result_summaries = re.findall(r"---- \[.*?\] ----", o, re.DOTALL)
    if not result_summaries:
        raise error.TestError("The automation program did not return any "
                              "results")
    results = result_summaries[-1].strip("-")
    results = eval("".join(results.splitlines()))

    # Download logs and HTML reports from the server
    for i, r in enumerate(results):
        if "report" in r:
            try:
                rss_file_transfer.download(server_address,
                                           server_file_transfer_port,
                                           r["report"], test.debugdir)
            except rss_file_transfer.FileTransferNotFoundError:
                pass
        if "logs" in r:
            try:
                rss_file_transfer.download(server_address,
                                           server_file_transfer_port,
                                           r["logs"], test.debugdir)
            except rss_file_transfer.FileTransferNotFoundError:
                pass
            else:
                try:
                    # Create symlinks to test log dirs to make it easier
                    # to access them (their original names are not human
                    # readable)
                    link_name = "logs_%s" % r["report"].split("\\")[-1]
                    link_name = link_name.replace(" ", "_")
                    link_name = link_name.replace("/", "_")
                    os.symlink(r["logs"].split("\\")[-1],
                               os.path.join(test.debugdir, link_name))
                except (KeyError, OSError):
                    pass

    # Print result summary
    logging.info("")
    logging.info("Result summary:")
    name_length = max(len(r.get("job", "")) for r in results)
    fmt = "%%-6s %%-%ds %%-15s %%-8s %%-8s %%-8s %%-15s" % name_length
    logging.info(fmt % ("ID", "Job", "Status", "Pass", "Fail", "NotRun",
                        "NotApplicable"))
    logging.info(fmt % ("--", "---", "------", "----", "----", "------",
                        "-------------"))
    for r in results:
        logging.info(fmt % (r.get("id"), r.get("job"), r.get("status"),
                            r.get("pass"), r.get("fail"), r.get("notrun"),
                            r.get("notapplicable")))
    logging.info("(see logs and HTML reports in %s)" % test.debugdir)

    # Kill the VM and fail if the automation program did not terminate on time
    if not done:
        vm.destroy()
        raise error.TestFail("The automation program did not terminate "
                             "on time")

    # Fail if there are failed or incomplete jobs (kill the VM if there are
    # incomplete jobs)
    failed_jobs = [r.get("job") for r in results
                   if r.get("status", "").lower() == "investigate"]
    running_jobs = [r.get("job") for r in results
                    if r.get("status", "").lower() == "inprogress"]
    errors = []
    if failed_jobs:
        errors += ["Jobs failed: %s." % failed_jobs]
    if running_jobs:
        vm.destroy()
        errors += ["Jobs did not complete on time: %s." % running_jobs]
    if errors:
        raise error.TestFail(" ".join(errors))
