import logging, os
from autotest.client.shared import error
from autotest.client import utils
from autotest.client.virt import virt_test_utils
from autotest.client.virt import virt_utils

CLIENT_TEST = "kernelinstall"

@error.context_aware
def run_kernel_install(test, params, env):
    """
    KVM kernel install test:
    1) Log into a guest
    2) Save current default kernel information
    3) Fetch necessary files for guest kernel installation
    4) Generate contol file for kernelinstall test
    5) Launch kernel installation (kernelinstall) test in guest
    6) Reboot guest after kernel is installed (optional)
    7) Do sub tests in guest with new kernel (optional)
    8) Restore grub and reboot guest (optional)

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    sub_test_path = os.path.join(test.bindir, "../%s" % CLIENT_TEST)
    _tmp_file_list = []
    _tmp_params_dict = {}

    def _copy_file_to_test_dir(file_path):
        if utils.is_url(file_path):
            return file_path
        file_abs_path = os.path.join(test.bindir, file_path)
        dest = os.path.join(sub_test_path, os.path.basename(file_abs_path))
        return os.path.basename(utils.get_file(file_path, dest))


    def _save_bootloader_config(session):
        """
        Save bootloader's config, in most case, it's grub
        """
        default_kernel = ""
        try:
            default_kernel = session.cmd_output("grubby --default-kernel")
        except Exception, e:
            logging.warn("Save grub config failed: '%s'" % e)

        return default_kernel


    def _restore_bootloader_config(session, default_kernel):
        error.context("Restore the grub to old version")

        if not default_kernel:
            logging.warn("Could not get previous grub config, do noting.")
            return

        cmd = "grubby --set-default=%s" % default_kernel.strip()
        try:
            session.cmd(cmd)
        except Exception, e:
            raise error.TestWarn("Restore grub failed: '%s'" % e)


    def _clean_up_tmp_files(file_list):
        for f in file_list:
            try:
                os.unlink(f)
            except Exception, e:
                logging.warn("Could remove tmp file '%s', error message: '%s'",
                             f, e)


    def _build_params(param_str, default_value=""):
        param = _tmp_params_dict.get(param_str)
        if param:
            return {param_str: param}
        param = params.get(param_str)
        if param:
            return {param_str: param}
        return {param_str: default_value}


    error.context("Log into a guest")
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = float(params.get("login_timeout", 240))
    session = vm.wait_for_login(timeout=timeout)

    error.context("Save current default kernel information")
    default_kernel = _save_bootloader_config(session)

    # Check if there is local file in params, move local file to
    # client test (kernelinstall) directory.
    file_checklist = params.get("file_checklist", "")
    for i in file_checklist.split():
        var_list = map(_copy_file_to_test_dir, params.get(i, "").split())
        _tmp_params_dict[i] = " ".join(var_list)

    # Env preparation for test.
    install_type = params.get("install_type", "brew")
    sub_test_params = {}
    # rpm
    sub_test_params.update(_build_params("kernel_rpm_path"))
    sub_test_params.update(_build_params("kernel_deps_rpms"))

    # koji
    if params.get("kernel_koji_tag"):
        koji_tag = "kernel_koji_tag"
    else:
        # Try to get brew tag if not set "kernel_koji_tag" parameter
        koji_tag = "brew_tag"

    sub_test_params.update(_build_params(koji_tag))
    sub_test_params.update(_build_params("kernel_dep_pkgs"))

    # git
    sub_test_params.update(_build_params('kernel_git_repo'))
    sub_test_params.update(_build_params('kernel_git_repo_base'))
    sub_test_params.update(_build_params('kernel_git_branch'))
    sub_test_params.update(_build_params('kernel_git_commit'))
    sub_test_params.update(_build_params('kernel_patch_list'))
    sub_test_params.update(_build_params('kernel_config'))
    sub_test_params.update(_build_params("kernel_config_list"))

    # src
    sub_test_params.update(_build_params("kernel_src_pkg"))
    sub_test_params.update(_build_params("kernel_config", "tests_rsc/config"))
    sub_test_params.update(_build_params("kernel_patch_list"))

    tag = params.get("kernel_tag")

    error.context("Generate contol file for kernelinstall test")
    #Generate control file from parameters
    control_base = "params = %s\n"
    control_base += "job.run_test('kernelinstall'"
    control_base += ", install_type='%s'" % install_type
    control_base += ", params=params"
    if install_type == "tar" and tag:
        control_base += ", tag='%s'" % tag
    control_base += ")"

    virt_dir = os.path.dirname(virt_utils.__file__)
    test_control_file = "kernel_install.control"
    test_control_path = os.path.join(virt_dir, "autotest_control",
                                     test_control_file)

    control_str = control_base % sub_test_params
    try:
        fd = open(test_control_path, "w")
        fd.write(control_str)
        fd.close()
        _tmp_file_list.append(os.path.abspath(test_control_path))
    except IOError, e:
        _clean_up_tmp_files(_tmp_file_list)
        raise error.TestError("Fail to Generate control file,"
                              " error message:\n '%s'" % e)

    params["test_control_file_install"] = test_control_file

    error.context("Launch kernel installation test in guest")
    virt_test_utils.run_virt_sub_test(test, params, env, sub_type="autotest",
                                      tag="install")

    if params.get("need_reboot", "yes") == "yes":
        error.context("Reboot guest after kernel is installed")
        session.close()
        try:
            vm.reboot()
        except Exception:
            _clean_up_tmp_files(_tmp_file_list)
            raise error.TestFail("Could not login guest after install kernel")

    # Run Subtest in guest with new kernel
    if params.has_key("sub_test"):
        error.context("Run sub test in guest with new kernel")
        sub_test = params.get("sub_test")
        tag = params.get("sub_test_tag", "run")
        try:
            virt_test_utils.run_virt_sub_test(test, params, env,
                                         sub_type=sub_test, tag=tag)
        except Exception, e:
            logging.error("Fail to run sub_test '%s', error message: '%s'",
                          sub_test, e)

    if params.get("restore_defaut_kernel", "no") == "yes":
        # Restore grub
        error.context("Restore grub and reboot guest")
        try:
            session = vm.wait_for_login(timeout=timeout)
            _restore_bootloader_config(session, default_kernel)
        except Exception, e:
            _clean_up_tmp_files(_tmp_file_list)
            session.close()
            raise error.TestFail("Fail to restore to default kernel,"
                                 " error message:\n '%s'" % e)
        vm.reboot()

    # Finally, let me clean up the tmp files.
    _clean_up_tmp_files(_tmp_file_list)
