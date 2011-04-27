import logging, os, re
from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import virt_utils, rss_client, aexpect


def run_whql_submission(test, params, env):
    """
    WHQL submission test:
    1) Log into the client machines and into a DTM server machine
    2) Copy the automation program binary (dsso_test_binary) to the server machine
    3) Run the automation program
    4) Pass the program all relevant parameters (e.g. device_data)
    5) Wait for the program to terminate
    6) Parse and report job results
    (logs and HTML reports are placed in test.debugdir)

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    # Log into all client VMs
    login_timeout = int(params.get("login_timeout", 360))
    vms = []
    sessions = []
    for vm_name in params.objects("vms"):
        vms.append(env.get_vm(vm_name))
        vms[-1].verify_alive()
        sessions.append(vms[-1].wait_for_login(timeout=login_timeout))

    # Make sure all NICs of all client VMs are up
    for vm in vms:
        nics = vm.params.objects("nics")
        for nic_index in range(len(nics)):
            s = vm.wait_for_login(nic_index, 600)
            s.close()

    # Collect parameters
    server_address = params.get("server_address")
    server_shell_port = int(params.get("server_shell_port"))
    server_file_transfer_port = int(params.get("server_file_transfer_port"))
    server_studio_path = params.get("server_studio_path", "%programfiles%\\ "
                                    "Microsoft Driver Test Manager\\Studio")
    dsso_test_binary = params.get("dsso_test_binary",
                                  "deps/whql_submission_15.exe")
    dsso_test_binary = virt_utils.get_path(test.bindir, dsso_test_binary)
    dsso_delete_machine_binary = params.get("dsso_delete_machine_binary",
                                            "deps/whql_delete_machine_15.exe")
    dsso_delete_machine_binary = virt_utils.get_path(test.bindir,
                                                    dsso_delete_machine_binary)
    test_timeout = float(params.get("test_timeout", 600))

    # Copy dsso binaries to the server
    for filename in dsso_test_binary, dsso_delete_machine_binary:
        rss_client.upload(server_address, server_file_transfer_port,
                                 filename, server_studio_path, timeout=60)

    # Open a shell session with the server
    server_session = virt_utils.remote_login("nc", server_address,
                                            server_shell_port, "", "",
                                            sessions[0].prompt,
                                            sessions[0].linesep)
    server_session.set_status_test_command(sessions[0].status_test_command)

    # Get the computer names of the server and clients
    cmd = "echo %computername%"
    server_name = server_session.cmd_output(cmd).strip()
    client_names = [session.cmd_output(cmd).strip() for session in sessions]

    # Delete all client machines from the server's data store
    server_session.cmd("cd %s" % server_studio_path)
    for client_name in client_names:
        cmd = "%s %s %s" % (os.path.basename(dsso_delete_machine_binary),
                            server_name, client_name)
        server_session.cmd(cmd, print_func=logging.debug)

    # Reboot the client machines
    sessions = virt_utils.parallel((vm.reboot, (session,))
                                  for vm, session in zip(vms, sessions))

    # Check the NICs again
    for vm in vms:
        nics = vm.params.objects("nics")
        for nic_index in range(len(nics)):
            s = vm.wait_for_login(nic_index, 600)
            s.close()

    # Run whql_pre_command and close the sessions
    if params.get("whql_pre_command"):
        for session in sessions:
            session.cmd(params.get("whql_pre_command"),
                        int(params.get("whql_pre_command_timeout", 600)))
            session.close()

    # Run the automation program on the server
    pool_name = "%s_pool" % client_names[0]
    submission_name = "%s_%s" % (client_names[0],
                                 params.get("submission_name"))
    cmd = "%s %s %s %s %s %s" % (os.path.basename(dsso_test_binary),
                                 server_name, pool_name, submission_name,
                                 test_timeout, " ".join(client_names))
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
    server_session.sendline(params.get("test_device"))

    # Tell the automation program which jobs to run
    find_prompt("Jobs to run:")
    server_session.sendline(params.get("job_filter", ".*"))

    # Set submission DeviceData
    find_prompt("DeviceData name:")
    for dd in params.objects("device_data"):
        dd_params = params.object_params(dd)
        if dd_params.get("dd_name") and dd_params.get("dd_data"):
            server_session.sendline(dd_params.get("dd_name"))
            server_session.sendline(dd_params.get("dd_data"))
    server_session.sendline()

    # Set submission descriptors
    find_prompt("Descriptor path:")
    for desc in params.objects("descriptors"):
        desc_params = params.object_params(desc)
        if desc_params.get("desc_path"):
            server_session.sendline(desc_params.get("desc_path"))
    server_session.sendline()

    # Set machine dimensions for each client machine
    for vm_name in params.objects("vms"):
        vm_params = params.object_params(vm_name)
        find_prompt(r"Dimension name\b.*:")
        for dp in vm_params.objects("dimensions"):
            dp_params = vm_params.object_params(dp)
            if dp_params.get("dim_name") and dp_params.get("dim_value"):
                server_session.sendline(dp_params.get("dim_name"))
                server_session.sendline(dp_params.get("dim_value"))
        server_session.sendline()

    # Set extra parameters for tests that require them (e.g. NDISTest)
    for vm_name in params.objects("vms"):
        vm_params = params.object_params(vm_name)
        find_prompt(r"Parameter name\b.*:")
        for dp in vm_params.objects("device_params"):
            dp_params = vm_params.object_params(dp)
            if dp_params.get("dp_name") and dp_params.get("dp_regex"):
                server_session.sendline(dp_params.get("dp_name"))
                server_session.sendline(dp_params.get("dp_regex"))
                # Make sure the prompt appears again (if the device isn't found
                # the automation program will terminate)
                find_prompt(r"Parameter name\b.*:")
        server_session.sendline()

    # Wait for the automation program to terminate
    try:
        o = server_session.read_up_to_prompt(print_func=logging.info,
                                             timeout=test_timeout + 300)
        # (test_timeout + 300 is used here because the automation program is
        # supposed to terminate cleanly on its own when test_timeout expires)
        done = True
    except aexpect.ExpectError, e:
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
                rss_client.download(server_address,
                                           server_file_transfer_port,
                                           r["report"], test.debugdir)
            except rss_client.FileTransferNotFoundError:
                pass
        if "logs" in r:
            try:
                rss_client.download(server_address,
                                           server_file_transfer_port,
                                           r["logs"], test.debugdir)
            except rss_client.FileTransferNotFoundError:
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

    # Print result summary (both to the regular logs and to a file named
    # 'summary' in test.debugdir)
    def print_summary_line(f, line):
        logging.info(line)
        f.write(line + "\n")
    if results:
        # Make sure all results have the required keys
        for r in results:
            r["id"] = str(r.get("id"))
            r["job"] = str(r.get("job"))
            r["status"] = str(r.get("status"))
            r["pass"] = int(r.get("pass", 0))
            r["fail"] = int(r.get("fail", 0))
            r["notrun"] = int(r.get("notrun", 0))
            r["notapplicable"] = int(r.get("notapplicable", 0))
        # Sort the results by failures and total test count in descending order
        results = [(r["fail"],
                    r["pass"] + r["fail"] + r["notrun"] + r["notapplicable"],
                    r) for r in results]
        results.sort(reverse=True)
        results = [r[-1] for r in results]
        # Print results
        logging.info("")
        logging.info("Result summary:")
        name_length = max(len(r["job"]) for r in results)
        fmt = "%%-6s %%-%ds %%-15s %%-8s %%-8s %%-8s %%-15s" % name_length
        f = open(os.path.join(test.debugdir, "summary"), "w")
        print_summary_line(f, fmt % ("ID", "Job", "Status", "Pass", "Fail",
                                     "NotRun", "NotApplicable"))
        print_summary_line(f, fmt % ("--", "---", "------", "----", "----",
                                     "------", "-------------"))
        for r in results:
            print_summary_line(f, fmt % (r["id"], r["job"], r["status"],
                                         r["pass"], r["fail"], r["notrun"],
                                         r["notapplicable"]))
        f.close()
        logging.info("(see logs and HTML reports in %s)", test.debugdir)

    # Kill the client VMs and fail if the automation program did not terminate
    # on time
    if not done:
        virt_utils.parallel(vm.destroy for vm in vms)
        raise error.TestFail("The automation program did not terminate "
                             "on time")

    # Fail if there are failed or incomplete jobs (kill the client VMs if there
    # are incomplete jobs)
    failed_jobs = [r["job"] for r in results
                   if r["status"].lower() == "investigate"]
    running_jobs = [r["job"] for r in results
                    if r["status"].lower() == "inprogress"]
    errors = []
    if failed_jobs:
        errors += ["Jobs failed: %s." % failed_jobs]
    if running_jobs:
        for vm in vms:
            vm.destroy()
        errors += ["Jobs did not complete on time: %s." % running_jobs]
    if errors:
        raise error.TestFail(" ".join(errors))
