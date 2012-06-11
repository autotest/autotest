#!/usr/bin/python
"""
Program to help setup kvm test environment

@copyright: Red Hat 2010
"""
import os, sys
try:
    import autotest.common as common
except ImportError:
    import common
from autotest.client.virt import virt_utils

test_name = "kvm"
test_dir = os.path.dirname(sys.modules[__name__].__file__)
test_dir = os.path.abspath(test_dir)
base_dir = "/tmp/kvm_autotest_root"
default_userspace_paths = ["/usr/bin/qemu-kvm", "/usr/bin/qemu-img"]
check_modules = ["kvm", "kvm-%s" % virt_utils.get_cpu_vendor(verbose=False)]
online_docs_url = "https://github.com/autotest/autotest/wiki/KVMAutotest-GetStartedClient"

if __name__ == "__main__":
    virt_utils.virt_test_assistant(test_name, test_dir, base_dir,
                                   default_userspace_paths, check_modules,
                                   online_docs_url)
