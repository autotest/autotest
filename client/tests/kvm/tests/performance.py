import logging, time, os, re, commands, glob, string, sys, shutil
from autotest.client.shared import error
from autotest.client import utils
from autotest.client.virt import virt_test_utils
from autotest.client.virt.virt_test_utils import aton


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

    prefix = test.outputdir.split(".performance.")[0]
    summary_results = params.get("summary_results")
    guest_ver = session.cmd_output("uname -r").strip()

    if summary_results:
        if params.get("test") == "ffsb":
            ffsb_sum(os.path.dirname(test.outputdir), prefix, params, guest_ver,
                     test.resultsdir)
        session.close()
        return

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

def ffsb_sum(topdir, prefix, params, guest_ver, resultsdir):
    marks = ["Transactions per Second",  "Read Throughput", "Write Throughput"]
    matrix = []
    sum_thro = 0
    sum_hostcpu = 0

    cmd = 'find %s|grep "%s.*guest_results/guest_result"|grep -v prepare|sort' \
          % (topdir, prefix)
    for guest_result_file in commands.getoutput(cmd).split():
        sub_dir = os.path.dirname(guest_result_file)
        content = open(guest_result_file, "r").readlines()
        linestr = []
        readthro = 0
        writethro = 0

        for line in content:
            if marks[0] in line:
                iops = "%8s" % re.split("\s+", line)[0]
            elif marks[1] in line:
                substr = re.findall("\d+(?:\.\d+)*", line)[0]
                readthro = aton("%.2f" % float(substr))
            elif marks[2] in line:
                substr = re.findall("\d+(?:\.\d+)*", line)[0]
                writethro = aton("%.2f" % float(substr))
                break

        throughput = readthro + writethro
        linestr.append(iops)
        linestr.append(throughput)
        sum_thro += throughput

        file = glob.glob(os.path.join(sub_dir, "guest_monitor_result*.sum"))[0]
        str = open(file, "r").readlines()
        linestr.append("%8.2f" % (100 - aton(str[1].split()[3])))
        linestr.append("%8.2f" % (100 - aton(str[2].split()[3])))

        file = glob.glob(os.path.join(sub_dir, "host_monitor_result*.sum"))[0]
        str = open(file, "r").readlines()
        hostcpu = 100 - aton(str[-1].split()[3])
        linestr.append(hostcpu)
        sum_hostcpu += hostcpu
        linestr.append("%.2f" % (throughput/hostcpu))
        matrix.append(linestr)

    headstr = "threads|    IOPS|   Thro(MBps)|   Vcpu1|   Vcpu2|   Hostcpu|" \
              " MBps/Hostcpu%"
    categories = params.get("categories").split('|')
    threads = params.get("threads").split()
    kvm_ver = commands.getoutput(params.get('ver_cmd', "rpm -q qemu-kvm"))

    fd = open("%s/ffsb-result.RHS" % resultsdir, "w")
    fd.write("#ver# %s\n#ver# host kernel: %s\n#ver# guest kernel:%s\n" % (
             kvm_ver, os.uname()[2], guest_ver))

    desc = """#desc# The Flexible Filesystem Benchmark(FFSB) is a cross-platform
#desc# filesystem performance measurement tool. It uses customizable profiles
#desc# to measure of different workloads, and it supports multiple groups of
#desc# threads across multiple filesystems.
#desc# How to read the results:
#desc# - The Throughput is measured in MBps/sec.
#desc# - IOPS (Input/Output Operations Per Second, pronounced eye-ops)
#desc# - Usage of Vcpu, Hostcpu are all captured
#desc#
"""
    fd.write(desc)
    fd.write("SUM\n   None|    MBps|      Hostcpu|MBps/Hostcpu%\n")
    fd.write("      0|%8.2f|%13.2f|%8.2f\n" % (sum_thro, sum_hostcpu,
                                               (sum_thro/sum_hostcpu)))
    idx = 0
    for i in range(len(matrix)):
        if i % 3 == 0:
            fd.write("%s\n%s\n" % (categories[idx], headstr))
            idx += 1
        fd.write("%7s|%8s|%13s|%8s|%8s|%10s|%14s\n" % (threads[i%3],
                 matrix[i][0], matrix[i][1], matrix[i][2], matrix[i][3],
                 matrix[i][4], matrix[i][5]))
    fd.close()
