import logging, time, os, re
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
    4) Use dd and tmpfs to make fragement in memory
    5) Use libhugetlbfs to allocated huge page before start defrag
    6) Set the khugepaged do defrag
    7) Use libhugetlbfs to allocated huge page compare the value

    @param test: KVM test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    def get_mem_stat(param):
        """
        Get the memory size for a given memory param.

        @param param: Memory parameter.
        """
        for line in file('/proc/meminfo', 'r').readlines():
            if line.startswith("%s" % param):
                output = re.split('\s+', line)[1]
        return int(output)


    def set_libhugetlbfs(number):
        """
        Set the number of hugepages on the system.

        @param number: Number of pages (either string or numeric).
        """
        logging.info("Trying to setup %d hugepages on host", number)
        f = file("/proc/sys/vm/nr_hugepages", "w+")
        pre_ret = f.read()
        logging.debug("Number of huge pages on libhugetlbfs (pre-write): %s" %
                      pre_ret.strip())
        f.write(str(number))
        f.seek(0)
        ret = f.read()
        logging.debug("Number of huge pages on libhugetlbfs: (post-write): %s" %
                      ret.strip())
        return int(ret)


    def change_feature_status(status, feature_path, test_config):
        """
        Turn on/off feature functionality.

        @param status: String representing status, may be 'on' or 'off'.
        @param relative_path: Path of the feature relative to THP config base.
        @param test_config: Object that keeps track of THP config state.

        @raise: error.TestFail, if can't change feature status
        """
        feature_path = os.path.join(test_config.thp_path, feature_path)
        feature_file = open(feature_path, 'r')
        feature_file_contents = feature_file.read()
        feature_file.close()
        possible_values = test_config.value_listed(feature_file_contents)

        if 'yes' in possible_values:
            on_action = 'yes'
            off_action = 'no'
        elif 'always' in possible_values:
            on_action = 'always'
            off_action = 'never'
        elif '1' in possible_values or '0' in possible_values:
            on_action = '1'
            off_action = '0'
        else:
            raise ValueError("Uknown possible values for file %s: %s" %
                             (test_config.thp_path, possible_values))

        if status == 'on':
            action = on_action
        elif status == 'off':
            action = off_action

        try:
            feature_file = open(feature_path, 'w')
            feature_file.write(action)
            feature_file.close()
        except IOError, e:
            raise error.TestFail("Error writing %s to %s: %s" %
                                 (action, feature_path, e))
        time.sleep(1)


    def fragment_host_memory(mem_path):
        """
        Attempt to fragment host memory.

        It accomplishes that goal by spawning a large number of dd processes
        on a tmpfs mount.

        @param mem_path: tmpfs mount point.
        """
        error.context("Fragmenting host memory")
        try:
            logging.info("Prepare tmpfs in host")
            if not os.path.isdir(mem_path):
                os.makedirs(mem_path)
            utils.run("mount -t tmpfs none %s" % mem_path)
            logging.info("Start using dd to fragment memory in guest")
            cmd = ("for i in `seq 262144`; do dd if=/dev/urandom of=%s/$i "
                   "bs=4K count=1 & done" % mem_path)
            utils.run(cmd)
        finally:
            utils.run("umount %s" % mem_path)


    test_config = virt_test_setup.TransparentHugePageConfig(test, params)
    logging.info("Defrag test start")
    login_timeout = float(params.get("login_timeout", 360))
    mem_path = os.path.join("/tmp", "thp_space")

    try:
        test_config.setup()
        error.context("deactivating khugepaged defrag functionality")
        change_feature_status("off", "khugepaged/defrag", test_config)
        change_feature_status("off", "defrag", test_config)

        vm = virt_test_utils.get_living_vm(env, params.get("main_vm"))
        session = virt_test_utils.wait_for_login(vm, timeout=login_timeout)

        fragment_host_memory(mem_path)

        total = get_mem_stat('MemTotal')
        hugepagesize = get_mem_stat('Hugepagesize')
        nr_full = int(0.8 * (total / hugepagesize))

        nr_hp_before = set_libhugetlbfs(nr_full)

        error.context("activating khugepaged defrag functionality")
        change_feature_status("on", "khugepaged/defrag", test_config)
        change_feature_status("on", "defrag", test_config)

        sleep_time = 10
        logging.debug("Sleeping %s s to settle things out" % sleep_time)
        time.sleep(sleep_time)

        nr_hp_after = set_libhugetlbfs(nr_full)

        if nr_hp_before >= nr_hp_after:
            raise error.TestFail("No memory defragmentation on host: "
                                 "%s huge pages before turning "
                                 "khugepaged defrag on, %s after it" %
                                 (nr_hp_before, nr_hp_after))
        logging.info("Defrag test succeeded")
        session.close()
    finally:
        logging.debug("Cleaning up libhugetlbfs on host")
        set_libhugetlbfs(0)
        test_config.cleanup()
