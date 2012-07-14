import re, logging
from autotest.client.shared import error
from autotest.client.virt import virt_utils


@error.context_aware
def run_seabios(test, params, env):
    """
    KVM Seabios test:
    1) Start guest with sga bios
    2) Display and check the boot menu order
    3) Start guest from the specified boot entry
    4) Log into the guest to verify it's up

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    error.context("Start guest with sga bios")
    vm = env.get_vm(params["main_vm"])
    # Since the seabios is displayed in the beginning of guest boot,
    # booting guest here so that we can check all of sgabios/seabios
    # info, especially the correct time of sending boot menu key.
    vm.create()

    timeout = float(params.get("login_timeout", 240))
    boot_menu_key = params.get("boot_menu_key", 'f12')
    boot_menu_hint = params.get("boot_menu_hint")
    boot_device = params.get("boot_device", "")

    error.context("Display and check the boot menu order")

    f = lambda: re.search(boot_menu_hint, vm.serial_console.get_output())
    if not (boot_menu_hint and virt_utils.wait_for(f, timeout, 1)):
        raise error.TestFail("Could not get boot menu message.")

    # Send boot menu key in monitor.
    vm.send_key(boot_menu_key)

    _ = vm.serial_console.get_output()
    boot_list = re.findall("^\d+\. (.*)\s", _, re.M)

    if not boot_list:
        raise error.TestFail("Could not get boot entries list.")

    logging.info("Got boot menu entries: '%s'", boot_list)
    for i, v in enumerate(boot_list, start=1):
        if re.search(boot_device, v, re.I):
            error.context("Start guest from boot entry '%s'" % v,
                          logging.info)
            vm.send_key(str(i))
            break
    else:
        raise error.TestFail("Could not get any boot entry match "
                             "pattern '%s'" % boot_device)

    error.context("Log into the guest to verify it's up")
    session = vm.wait_for_login(timeout=timeout)
    session.close()
