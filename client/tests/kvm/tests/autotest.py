import os, logging
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
import kvm_subprocess, kvm_utils, kvm_test_utils, scan_results


def run_autotest(test, params, env):
    """
    Run an autotest test inside a guest.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    # Helper functions
    def copy_if_size_differs(vm, local_path, remote_path):
        """
        Copy a file to a guest if it doesn't exist or if its size differs.

        @param vm: VM object
        @param local_path: Local path
        @param remote_path: Remote path
        """
        copy = False
        basename = os.path.basename(local_path)
        output = session.get_command_output("ls -l %s" % remote_path)
        local_size = os.path.getsize(local_path)
        if "such file" in output:
            logging.info("Copying %s to guest (remote file is missing)" %
                         basename)
            copy = True
        else:
            remote_size = int(output.split()[4])
            if remote_size != local_size:
                logging.info("Copying %s to guest due to size mismatch"
                             "(remote size %s, local size %s)" % (basename,
                                                                  remote_size,
                                                                  local_size))
                copy = True

        if copy:
            if not vm.copy_files_to(local_path, remote_path):
                raise error.TestFail("Could not copy %s to guest" % local_path)


    def extract(vm, remote_path, dest_dir="."):
        """
        Extract a .tar.bz2 file on the guest.

        @param vm: VM object
        @param remote_path: Remote file path
        @param dest_dir: Destination dir for the contents
        """
        basename = os.path.basename(remote_path)
        logging.info("Extracting %s..." % basename)
        (status, output) = session.get_command_status_output(
                                  "tar xjvf %s -C %s" % (remote_path, dest_dir))
        if status != 0:
            raise error.TestFail("Could not extract %s, command output: %s" %
                                 (basename, output))

    vm = kvm_test_utils.get_living_vm(env, params.get("main_vm"))
    session = kvm_test_utils.wait_for_login(vm)

    # Collect test parameters
    test_name = params.get("test_name")
    test_timeout = int(params.get("test_timeout", 300))
    test_control_file = params.get("test_control_file", "control")

    tarred_autotest_path = "/tmp/autotest.tar.bz2"
    tarred_test_path = "/tmp/%s.tar.bz2" % test_name

    # To avoid problems, let's make the test use the current AUTODIR
    # (autotest client path) location
    autotest_path = os.environ['AUTODIR']
    tests_path = os.path.join(autotest_path, 'tests')
    test_path = os.path.join(tests_path, test_name)

    # tar the contents of bindir/autotest
    cmd = "tar cvjf %s %s/*" % (tarred_autotest_path, autotest_path)
    cmd += " --exclude=%s/tests" % autotest_path
    cmd += " --exclude=%s/results" % autotest_path
    cmd += " --exclude=%s/tmp" % autotest_path
    cmd += " --exclude=%s/control" % autotest_path
    cmd += " --exclude=*.pyc"
    cmd += " --exclude=*.svn"
    cmd += " --exclude=*.git"
    utils.run(cmd)

    # tar the contents of bindir/autotest/tests/<test_name>
    cmd = "tar cvjf %s %s/*" % (tarred_test_path, test_path)
    cmd += " --exclude=*.pyc"
    cmd += " --exclude=*.svn"
    cmd += " --exclude=*.git"
    utils.run(cmd)

    # Copy autotest.tar.bz2
    copy_if_size_differs(vm, tarred_autotest_path, tarred_autotest_path)

    # Copy <test_name>.tar.bz2
    copy_if_size_differs(vm, tarred_test_path, tarred_test_path)

    # Extract autotest.tar.bz2
    extract(vm, tarred_autotest_path, "/")

    # mkdir autotest/tests
    session.get_command_output("mkdir -p %s" % tests_path)

    # Extract <test_name>.tar.bz2 into autotest/tests
    extract(vm, tarred_test_path, "/")

    # Copy the selected control file (located inside
    # test.bindir/autotest_control) to the autotest dir
    control_file_path = os.path.join(test.bindir, "autotest_control",
                                     test_control_file)
    if not vm.copy_files_to(control_file_path,
                            os.path.join(autotest_path, 'control')):
        raise error.TestFail("Could not copy the test control file to guest")

    # Run the test
    logging.info("Running test '%s'..." % test_name)
    session.get_command_output("cd %s" % autotest_path)
    session.get_command_output("rm -f control.state")
    session.get_command_output("rm -rf results/*")
    logging.info("---------------- Test output ----------------")
    status = session.get_command_status("bin/autotest control",
                                        timeout=test_timeout,
                                        print_func=logging.info)
    logging.info("---------------- End of test output ----------------")
    if status is None:
        raise error.TestFail("Timeout elapsed while waiting for test to "
                             "complete")

    # Get the results generated by autotest
    output = session.get_command_output("cat results/*/status")
    results = scan_results.parse_results(output)
    session.close

    # Copy test results to the local bindir/guest_results
    logging.info("Copying results back from guest...")
    guest_results_dir = os.path.join(test.outputdir, "guest_results")
    if not os.path.exists(guest_results_dir):
        os.mkdir(guest_results_dir)
    if not vm.copy_files_from("%s/results/default/*" % autotest_path,
                              guest_results_dir):
        logging.error("Could not copy results back from guest")

    # Report test results
    logging.info("Results (test, status, duration, info):")
    for result in results:
        logging.info(str(result))

    # Make a list of FAIL/ERROR/ABORT results (make sure FAIL results appear
    # before ERROR results, and ERROR results appear before ABORT results)
    bad_results = [r for r in results if r[1] == "FAIL"]
    bad_results += [r for r in results if r[1] == "ERROR"]
    bad_results += [r for r in results if r[1] == "ABORT"]

    # Fail the test if necessary
    if not results:
        raise error.TestFail("Test '%s' did not produce any recognizable "
                             "results" % test_name)
    if bad_results:
        result = bad_results[0]
        raise error.TestFail("Test '%s' ended with %s (reason: '%s')"
                             % (result[0], result[1], result[3]))
