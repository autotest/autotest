"""
Utilities useful to client control files that test KVM.
"""

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

def get_kvm_arch():
    """
    Determines the kvm architecture kernel module that should be loaded.

    @return: "kvm_amd", "kvm_intel", or raise TestError exception
    """
    arch_type = ""
    for line in open("/proc/cpuinfo"):
        if arch_type == "":
            if "AuthenticAMD" in line:
                arch_type = "kvm_amd"
            elif "GenuineIntel" in line:
                arch_type = "kvm_intel"
        elif "flags" in line:
            if arch_type == "kvm_amd" and "svm" in line:
                return arch_type
            if arch_type == "kvm_intel" and "vmx" in line:
                return arch_type
    raise error.TestError("CPU Must be AMD or Intel, and must be KVM ready.")


def load_kvm():
    """
    Loads the appropriate KVM kernel modules
    """
    kvm_status = utils.system('modprobe kvm')
    kvm_amdintel_status = utils.system("modprobe " + kvm_arch)
    if kvm_status:
        return kvm_status
    else:
        return kvm_amdintel_status

def unload_kvm():
    """
    Unloads the appropriate KVM kernel modules
    """
    kvm_amdintel_status = utils.system("rmmod " + kvm_arch)
    kvm_status = utils.system('rmmod kvm')
    if kvm_status:
        return kvm_status
    else:
        return kvm_amdintel_status


kvm_arch = get_kvm_arch()
