import logging, time, commands, os, string, re
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.virt import virt_test_utils, aexpect, virt_test_setup


@error.context_aware
def run_trans_hugepage(test, params, env):
    """
    KVM kernel hugepages user side test:
    1) Smoke test
    2) Stress test

    @param test: KVM test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    def get_mem_status(params, type):
        if type == "host":
            info = utils.system_output("cat /proc/meminfo")
        else:
            info = session.cmd("cat /proc/meminfo")
        for h in re.split("\n+", info):
            if h.startswith("%s" % params):
                output = re.split('\s+', h)[1]
        return output

    dd_timeout = float(params.get("dd_timeout", 900))
    nr_ah = []
    mem = params['mem']
    failures = []

    debugfs_flag = 1
    debugfs_path = os.path.join(test.tmpdir, 'debugfs')
    mem_path = os.path.join("/tmp", 'thp_space')

    login_timeout = float(params.get("login_timeout", "3600"))

    error.context("smoke test setup")
    if not os.path.ismount(debugfs_path):
        if not os.path.isdir(debugfs_path):
            os.makedirs(debugfs_path)
        utils.run("mount -t debugfs none %s" % debugfs_path)

    test_config = virt_test_setup.TransparentHugePageConfig(test, params)
    vm = virt_test_utils.get_living_vm(env, params.get("main_vm"))
    session = virt_test_utils.wait_for_login(vm, timeout=login_timeout)

    try:
        # Check khugepage is used by guest
        test_config.setup()

        logging.info("Smoke test start")
        error.context("smoke test")

        nr_ah_before = get_mem_status('AnonHugePages', 'host')
        if nr_ah_before <= 0:
            e_msg = 'smoke: Host is not using THP'
            logging.error(e_msg)
            failures.append(e_msg)

        # Protect system from oom killer
        if int(get_mem_status('MemFree', 'guest')) / 1024 < mem :
            mem = int(get_mem_status('MemFree', 'guest')) / 1024

        session.cmd("mkdir -p %s" % mem_path)

        session.cmd("mount -t tmpfs -o size=%sM none %s" % (str(mem), mem_path))

        count = mem / 4
        session.cmd("dd if=/dev/zero of=%s/1 bs=4000000 count=%s" %
                    (mem_path, count), timeout=dd_timeout)

        nr_ah_after = get_mem_status('AnonHugePages', 'host')

        if nr_ah_after <= nr_ah_before:
            e_msg = ('smoke: Host did not use new THP during dd')
            logging.error(e_msg)
            failures.append(e_msg)

        if debugfs_flag == 1:
            if int(open('%s/kvm/largepages' % debugfs_path, 'r').read()) <= 0:
                e_msg = 'smoke: KVM is not using THP'
                logging.error(e_msg)
                failures.append(e_msg)

        logging.info("Smoke test finished")

        # Use parallel dd as stress for memory
        count = count / 3
        logging.info("Stress test start")
        error.context("stress test")
        cmd = "rm -rf %s/*; for i in `seq %s`; do dd " % (mem_path, count)
        cmd += "if=/dev/zero of=%s/$i bs=4000000 count=1& done;wait" % mem_path
        output = session.cmd_output(cmd, timeout=dd_timeout)

        if len(re.findall("No space", output)) > count * 0.05:
            e_msg = "stress: Too many dd instances failed in guest"
            logging.error(e_msg)
            failures.append(e_msg)

        try:
            output = session.cmd('pidof dd')
        except Exception:
            output = None

        if output is not None:
            for i in re.split('\n+', output):
                session.cmd('kill -9 %s' % i)

        session.cmd("umount %s" % mem_path)

        logging.info("Stress test finished")

    finally:
        error.context("all tests cleanup")
        if os.path.ismount(debugfs_path):
            utils.run("umount %s" % debugfs_path)
        if os.path.isdir(debugfs_path):
            os.removedirs(debugfs_path)
        session.close()
        test_config.cleanup()

    error.context("")
    if failures:
        raise error.TestFail("THP base test reported %s failures:\n%s" %
                             (len(failures), "\n".join(failures)))
