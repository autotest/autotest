"""
Utilities useful to client control files that test KVM.
"""


from autotest.client import utils
from autotest.client.base_utils import cpu_has_flags, get_cpu_vendor_name
from autotest.client.shared import error


def get_kvm_arch():
    """
    Determines the kvm architecture kernel module that should be loaded.
    @return: "kvm_amd", "kvm_intel", or raise TestError exception
    """
    flags = {
        'kvm_amd': "svm",
        'kvm_intel': "vmx"
    }

    vendor_name = get_cpu_vendor_name()
    if not vendor_name:
        raise error.TestError("CPU Must be AMD, Intel or Power7")

    arch_type = 'kvm_%s' % vendor_name
    cpu_flag = flags.get(arch_type, None)

    if not cpu_flag and vendor_name in ('power7', ):
        return arch_type

    if not cpu_has_flags(cpu_flag):
        raise error.TestError("%s CPU architecture must have %s "
                              "flag active and must be KVM ready" %
                              (arch_type, cpu_flag))
    return arch_type


def load_kvm():
    """
    Loads the appropriate KVM kernel modules
    @return: 0 on success, 1 on failure
    """
    kvm_arch = get_kvm_arch()

    def load_module(mod='kvm'):
        return utils.system('modprobe %s' % mod)

    loaded = load_module()
    if not loaded:
        loaded = load_module(mod=kvm_arch)
    return loaded


def unload_kvm():
    """
    Unloads the appropriate KVM kernel modules
    """
    kvm_arch = get_kvm_arch()

    def unload_module(mod):
        return utils.system('rmmod %s' % mod)

    unloaded = unload_module(kvm_arch)

    if not unloaded:
        unloaded = unload_module('kvm')

    return unloaded
