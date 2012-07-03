import os, commands, glob
from autotest.client import utils
from autotest.client.shared import error
from autotest.client.virt import virt_test_utils


def run_perf_kvm(test, params, env):
    """
    run perf tool to get kvm events info

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()

    test_timeout = int(params.get("test_timeout", 240))
    login_timeout = int(params.get("login_timeout", 360))
    transfer_timeout = int(params.get("transfer_timeout", 240))
    perf_record_timeout = int(params.get("perf_record_timeout", 240))
    vm_kallsyms_path = "/tmp/guest_kallsyms"
    vm_modules_path = "/tmp/guest_modules"

    # Prepare test environment in guest
    session = vm.wait_for_login(timeout=login_timeout)

    session.cmd("cat /proc/kallsyms > %s" % vm_kallsyms_path)
    session.cmd("cat /proc/modules > %s" % vm_modules_path)

    vm.copy_files_from("/tmp/guest_kallsyms", "/tmp", timeout=transfer_timeout)
    vm.copy_files_from("/tmp/guest_modules", "/tmp", timeout=transfer_timeout)

    perf_record_cmd = "perf kvm --host --guest --guestkallsyms=%s" % vm_kallsyms_path
    perf_record_cmd += " --guestmodules=%s record -a -o /tmp/perf.data sleep %s " % (vm_modules_path, perf_record_timeout)
    perf_report_cmd = "perf kvm --host --guest --guestkallsyms=%s" % vm_kallsyms_path
    perf_report_cmd += " --guestmodules=%s report -i /tmp/perf.data --force " % vm_modules_path

    utils.system(perf_record_cmd)
    utils.system(perf_report_cmd)

    session.close()
