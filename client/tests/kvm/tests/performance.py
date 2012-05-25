import logging, time, os, re, commands, shutil
from autotest.client.shared import error
from autotest.client import utils
from autotest.client.virt import virt_test_utils


def run_performance(test, params, env):
    """
    KVM performance test:

    The idea is similar to 'client/tests/kvm/tests/autotest.py',
    but we can implement some special requests for performance
    testing.

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()

    test_timeout = int(params.get("test_timeout", 240))
    monitor_cmd = params.get("monitor_cmd")
    login_timeout = int(params.get("login_timeout", 360))
    test_cmd = params.get("test_cmd")
    guest_path = params.get("result_path", "/tmp/guest_result")
    test_src = params.get("test_src")
    test_patch = params.get("test_patch")

    # Prepare test environment in guest
    session = vm.wait_for_login(timeout=login_timeout)
    guest_launcher = os.path.join(test.virtdir, "scripts/cmd_runner.py")
    vm.copy_files_to(guest_launcher, "/tmp")
    md5value = params.get("md5value")

    tarball = utils.unmap_url_cache(test.tmpdir, test_src, md5value)
    test_src = re.split("/", test_src)[-1]
    vm.copy_files_to(tarball, "/tmp")

    session.cmd("rm -rf /tmp/src*")
    session.cmd("mkdir -p /tmp/src_tmp")
    session.cmd("tar -xf /tmp/%s -C %s" % (test_src, "/tmp/src_tmp"))

    # Find the newest file in src tmp directory
    cmd =  "ls -rt /tmp/src_tmp"
    s, o = session.cmd_status_output(cmd)
    if len(o) > 0:
        new_file = re.findall("(.*)\n", o)[-1]
    else:
       raise error.TestError("Can not decompress test file in guest")
    session.cmd("mv /tmp/src_tmp/%s /tmp/src" % new_file)

    if test_patch:
        test_patch_path = os.path.join(test.srcdir, 'examples', test_patch)
        vm.copy_files_to(test_patch_path, "/tmp/src")
        session.cmd("cd /tmp/src && patch -p1 < /tmp/src/%s" % test_patch)

    compile_cmd = params.get("compile_cmd")
    if compile_cmd:
        session.cmd("cd /tmp/src && %s" % compile_cmd)

    prepare_cmd = params.get("prepare_cmd")
    if prepare_cmd:
        s, o = session.cmd_status_output(prepare_cmd, test_timeout)
        if s != 0:
            raise error.TestError("Fail to prepare test env in guest")

    cmd = "cd /tmp/src && python /tmp/cmd_runner.py \"%s &> " % monitor_cmd
    cmd += "/tmp/guest_result_monitor\"  \"/tmp/src/%s" % test_cmd
    cmd += " &> %s \" \"/tmp/guest_result\""
    cmd += " %s" % int(test_timeout)

    test_cmd = cmd
    # Run guest test with monitor
    tag = virt_test_utils.cmd_runner_monitor(vm, monitor_cmd, test_cmd,
                                     guest_path, timeout = test_timeout)

    # Result collecting
    result_list = ["/tmp/guest_result_%s" % tag,
                   "/tmp/host_monitor_result_%s" % tag,
                   "/tmp/guest_monitor_result_%s" % tag]
    guest_results_dir = os.path.join(test.outputdir, "guest_results")
    if not os.path.exists(guest_results_dir):
        os.mkdir(guest_results_dir)
    ignore_pattern = params.get("ignore_pattern")
    head_pattern = params.get("head_pattern")
    row_pattern = params.get("row_pattern")
    for i in result_list:
        if re.findall("monitor_result", i):
            result = virt_test_utils.summary_up_result(i, ignore_pattern,
                                head_pattern, row_pattern)
            fd = open("%s.sum" % i, "w")
            sum_info = {}
            head_line = ""
            for keys in result:
                head_line += "\t%s" % keys
                for col in result[keys]:
                    col_sum = "line %s" % col
                    if col_sum in sum_info:
                        sum_info[col_sum] += "\t%s" % result[keys][col]
                    else:
                        sum_info[col_sum] = "%s\t%s" % (col, result[keys][col])
            fd.write("%s\n" % head_line)
            for keys in sum_info:
                fd.write("%s\n" % sum_info[keys])
            fd.close()
            shutil.copy("%s.sum" % i, guest_results_dir)
        shutil.copy(i, guest_results_dir)

    session.cmd("rm -rf /tmp/src")
    session.cmd("rm -rf guest_test*")
    session.cmd("rm -rf pid_file*")
    session.close()
