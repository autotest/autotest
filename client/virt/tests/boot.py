import time
import sys
import re

from autotest_lib.client.common_lib import error


def _get_function(func_name):
    """
    Find function with given name in this module.

    @param func_name: function name.

    @return funciton object.
    """
    if not func_name:
        return None

    import types
    items = sys.modules[__name__].__dict__.items()
    for key, value in items:
        if key == func_name and isinstance(value, types.FunctionType):
            return value

    return None


def check_usb_device(test, params, env):
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()

    o = vm.monitor.info("usb")
    if isinstance(o, dict):
        o = o.get("return")
    info_usb_name = params.get("info_usb_name")
    if info_usb_name and (info_usb_name not in o):
        raise error.TestFail("Could not find '%s' device, monitor "
                             "returns: \n%s" % (params.get("product"), o))

    timeout = float(params.get("login_timeout", 240))
    session = vm.wait_for_login(timeout=timeout)

    chk_list = ["%s:%s" % (params.get("vendor_id"), params.get("product_id"))]
    if params.get("vendor"):
        chk_list.append(params.get("vendor"))
    if params.get("product"):
        chk_list.append(params.get("product"))

    o = session.cmd("lsusb -v")
    for item in chk_list:
        if not re.findall(item, o):
            raise error.TestFail("Could not find item '%s' in guest, "
                                 "'lsusb -v' output:\n %s" % (item, o))


@error.context_aware
def run_boot(test, params, env):
    """
    KVM reboot test:
    1) Log into a guest
    2) Verify device(s) work well in guest (optional)
    3) Send a reboot command or a system_reset monitor command (optional)
    4) Wait until the guest is up again
    5) Log into the guest to verify it's up again
    6) Verify device(s) again after guest reboot (optional)

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """

    def _check_device(check_func):
        func = _get_function(check_func)
        if not func:
            raise error.TestError("Could not find function %s" % check_func)
        func(test, params, env)


    error.context("Try to log into guest.")
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = float(params.get("login_timeout", 240))
    session = vm.wait_for_login(timeout=timeout)

    check_func = params.get("check_func")
    if check_func:
        error.context("Verify device(s) before rebooting.")
        _check_device(check_func)

    if params.get("reboot_method"):
        error.context("Reboot guest.")
        if params["reboot_method"] == "system_reset":
            time.sleep(int(params.get("sleep_before_reset", 10)))
        session = vm.reboot(session, params["reboot_method"], 0, timeout)

        if check_func:
            error.context("Verify device(s) after rebooting.")
            _check_device(check_func)

    session.close()
