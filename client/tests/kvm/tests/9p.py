import os,logging
from autotest.client.shared import error
from autotest.client.virt import virt_test_utils


def run_9p(test, params, env):
    """
    Run an autotest test inside a guest.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

    mount_dir = params.get("9p_mount_dir")

    if mount_dir is None:
        logging.info("User Variable for mount dir is not set")
    else:
        mkdir = session.get_command_output("mkdir -p %s" % mount_dir)

        mount_option = " trans=virtio"

        p9_proto_version = params.get("9p_proto_version", "9p2000.L")
        mount_option += ",version=" + p9_proto_version

        guest_cache = params.get("9p_guest_cache")
        if guest_cache == "yes":
            mount_option += ",cache=loose"

        posix_acl = params.get("9p_posix_acl")
        if posix_acl == "yes":
            mount_option += ",posixacl"

        logging.info("Mounting 9p mount point with options %s" % mount_option)
        cmd = "mount -t 9p -o %s autotest_tag %s" % (mount_option, mount_dir)
        mount_status = session.get_command_status(cmd)

        if (mount_status != 0):
            logging.error("mount failed")
            raise error.TestFail('mount failed.')

        # Collect test parameters
        timeout = int(params.get("test_timeout", 14400))
        control_path = os.path.join(test.virtdir, "autotest_control",
                                    params.get("test_control_file"))

        outputdir = test.outputdir

        virt_test_utils.run_autotest(vm, session, control_path,
                                     timeout, outputdir, params)
