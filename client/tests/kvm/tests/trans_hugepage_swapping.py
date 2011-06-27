import logging, time, commands, os, string, re
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
from autotest_lib.client.virt import virt_utils, virt_test_utils
from autotest_lib.client.virt import virt_test_setup, virt_env_process


@error.context_aware
def run_trans_hugepage_swapping(test, params, env):
    """
    KVM khugepage user side test:
    1) Verify that the hugepages can be swapped in/out.

    @param test: KVM test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    def get_args(args_list):
        """
        Get the memory arguments from system
        """
        args_list_tmp = args_list.copy()
        for line in file('/proc/meminfo', 'r').readlines():
            for key in args_list_tmp.keys():
                if line.startswith("%s" % args_list_tmp[key]):
                    args_list_tmp[key] = int(re.split('\s+', line)[1])
        return args_list_tmp

    test_config = virt_test_setup.TransparentHugePageConfig(test, params)
    try:
        test_config.setup()
        # Swapping test
        logging.info("Swapping test start")
        # Parameters of memory information
        # @total: Memory size
        # @free: Free memory size
        # @swap_size: Swap size
        # @swap_free: Free swap size
        # @hugepage_size: Page size of one hugepage
        # @page_size: The biggest page size that app can ask for
        args_dict_check = {"free" : "MemFree", "swap_size" : "SwapTotal",
                           "swap_free" : "SwapFree", "total" : "MemTotal",
                           "hugepage_size" : "Hugepagesize",}
        args_dict = get_args(args_dict_check)
        swap_free = []
        total = int(args_dict['total']) / 1024
        free = int(args_dict['free']) / 1024
        swap_size = int(args_dict['swap_size']) / 1024
        swap_free.append(int(args_dict['swap_free'])/1024)
        hugepage_size = int(args_dict['hugepage_size']) / 1024
        dd_timeout = float(params.get("dd_timeout", 900))
        login_timeout = float(params.get("login_timeout", 360))
        check_cmd_timeout = float(params.get("check_cmd_timeout", 900))
        mem_path = os.path.join(test.tmpdir, 'thp_space')
        tmpfs_path = "/space"

        # If swap is enough fill all memory with dd
        if swap_free > (total - free):
            count = total / hugepage_size
            tmpfs_size = total
        else:
            count = free / hugepage_size
            tmpfs_size = free

        if swap_size <= 0:
            raise logging.info("Host does not have swap enabled")
        session = None
        try:
            if not os.path.isdir(mem_path):
                os.makedirs(mem_path)
            utils.run("mount -t tmpfs  -o size=%sM none %s" % (tmpfs_size,
                                                               mem_path))

            # Set the memory size of vm
            # To ignore the oom killer set it to the free swap size
            vm = virt_test_utils.get_living_vm(env, params.get("main_vm"))
            if int(params['mem']) > swap_free[0]:
                vm.destroy()
                vm_name = 'vmsw'
                vm0 =  params.get("main_vm")
                vm0_key = virt_utils.env_get_vm(env, vm0)
                params['vms'] = params['vms'] + " " + vm_name
                params['mem'] = str(swap_free[0])
                vm_key = vm0_key.clone(vm0, params)
                virt_utils.env_register_vm(env, vm_name, vm_key)
                virt_env_process.preprocess_vm(test, params, env, vm_name)
                vm_key.create()
                session = virt_utils.wait_for(vm_key.remote_login,
                                              timeout=login_timeout)
            else:
                session = virt_test_utils.wait_for_login(vm,
                                                        timeout=login_timeout)

            error.context("making guest to swap memory")
            cmd = ("dd if=/dev/zero of=%s/zero bs=%s000000 count=%s" %
                   (mem_path, hugepage_size, count))
            utils.run(cmd)

            args_dict = get_args(args_dict_check)
            swap_free.append(int(args_dict['swap_free'])/1024)

            if swap_free[1] - swap_free[0] >= 0:
                raise error.TestFail("No data was swapped to memory")

            # Try harder to make guest memory to be swapped
            session.cmd("find / -name \"*\"", timeout=check_cmd_timeout)
        finally:
            if session is not None:
                utils.run("umount %s" % mem_path)

        logging.info("Swapping test succeed")

    finally:
        session.close()
        test_config.cleanup()
