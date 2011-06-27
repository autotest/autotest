import logging, time, commands, os, string, re
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
from autotest_lib.client.virt import virt_test_utils, virt_test_setup


@error.context_aware
def run_trans_hugepage_defrag(test, params, env):
    """
    KVM khugepage userspace side test:
    1) Verify that the host supports kernel hugepages.
        If it does proceed with the test.
    2) Verify that the kernel hugepages can be used in host.
    3) Verify that the kernel hugepages can be used in guest.
    4) Migrate guest while using hugepages.

    @param test: KVM test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    def get_mem_status(params):
        for line in file('/proc/meminfo', 'r').readlines():
            if line.startswith("%s" % params):
                output = re.split('\s+', line)[1]
        return output


    def set_libhugetlbfs(number):
        f = file("/proc/sys/vm/nr_hugepages", "w+")
        f.write(number)
        f.seek(0)
        ret = f.read()
        return int(ret)

    test_config = virt_test_setup.TransparentHugePageConfig(test, params)
    # Test the defrag
    logging.info("Defrag test start")
    login_timeout = float(params.get("login_timeout", 360))
    vm = virt_test_utils.get_living_vm(env, params.get("main_vm"))
    session = virt_test_utils.wait_for_login(vm, timeout=login_timeout)
    mem_path = os.path.join("/tmp", "thp_space")

    try:
        test_config.setup()
        error.context("Fragmenting guest memory")
        try:
            if not os.path.isdir(mem_path):
                os.makedirs(mem_path)
            if os.system("mount -t tmpfs none %s" % mem_path):
                raise error.TestError("Can not mount tmpfs")

            # Try to fragment the memory a bit
            cmd = ("for i in `seq 262144`; do dd if=/dev/urandom of=%s/$i "
                   "bs=4K count=1 & done" % mem_path)
            utils.run(cmd)
        finally:
            utils.run("umount %s" % mem_path)

        total = int(get_mem_status('MemTotal'))
        hugepagesize = int(get_mem_status('Hugepagesize'))
        nr_full = str(total / hugepagesize)

        error.context("activating khugepaged defrag functionality")
        # Allocate hugepages for libhugetlbfs before and after enable defrag,
        # and check out the difference.
        nr_hp_before = set_libhugetlbfs(nr_full)
        try:
            defrag_path = os.path.join(test_config.thp_path, 'khugepaged',
                                       'defrag')
            file(str(defrag_path), 'w').write('yes')
        except IOError, e:
            raise error.TestFail("Can not start defrag on khugepaged: %s" % e)
        # TODO: Is sitting an arbitrary amount of time appropriate? Aren't there
        # better ways to do this?
        time.sleep(1)
        nr_hp_after = set_libhugetlbfs(nr_full)

        if nr_hp_before >= nr_hp_after:
            raise error.TestFail("There was no memory defragmentation on host: "
                                 "%s huge pages allocated before turning "
                                 "khugepaged defrag on, %s allocated after it" %
                                 (nr_hp_before, nr_hp_after))
        logging.info("Defrag test succeeded")
        session.close()
    finally:
        test_config.cleanup()
