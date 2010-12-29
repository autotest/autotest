import re, commands, logging, os
from autotest_lib.client.common_lib import error
import kvm_subprocess, kvm_test_utils, kvm_utils

def run_module_probe(test, params, env):
    """
    load/unload kvm modules several times.

    Module load/unload Test:
    1) check host cpu module
    2) get module info
    3) unload modules if they exist, else load them

    @param test: Kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """

    def module_probe(name_list, arg=""):
        for name in name_list:
            cmd = "modprobe %s %s" % (arg, name)
            logging.debug(cmd)
            s, o = commands.getstatusoutput(cmd)
            if s != 0:
                logging.error("Failed to load/unload modules %s" % o)
                return False
        return True

    #Check host cpu module
    flags = file("/proc/cpuinfo").read()
    arch_check = re.findall("%s\s" % "vmx", flags)
    if arch_check:
        arch = "kvm_intel"
    else:
        arch = "kvm_amd"

    #Check whether ksm module exist
    mod_str = ""
    if os.path.exists("/sys/module/ksm"):
        mod_str = "ksm,"
    mod_str += "%s, kvm" % arch

    mod_str = params.get("mod_list", mod_str)
    mod_list = re.split(",", mod_str)
    logging.debug(mod_list)
    load_count = int(params.get("load_count", 100))

    try:
        for i in range(load_count):
            if not module_probe(mod_list):
                raise error.TestFail("Failed to load module %s" % mod_list)
            if not module_probe(mod_list, "-r"):
                raise error.TestFail("Failed to remove module %s" % mod_list)
    finally:
        module_probe(mod_list)
