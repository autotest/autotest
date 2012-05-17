import logging
from autotest.client.virt import virt_vm, virt_utils

class VMCreateSuccess(Exception):
    def __str__(self):
        return "VM succeeded to create. This was not expected"

def run_negative_create(test, params, env):
    """
    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    @raise VMCreateSuccess: in case that vm.create() passed

    This test is designed to check if qemu exits on passed invalid
    argument values.

    E.g. -spice port=-1 or -spice port=hello
    """

    main_vm = env.get_vm(params["main_vm"])
    try:
        main_vm.create(params["main_vm"])
    except (virt_vm.VMError, virt_utils.NetError) as err:
        logging.debug("VM Failed to create. This was expected. Reason:\n%s",
                str(err))
    else:
        main_vm.destroy()
        raise VMCreateSuccess()
