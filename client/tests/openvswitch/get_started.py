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
from autotest.client.tests.virt.virttest import utils_misc

test_name = "openvswitch"
test_dir = os.path.dirname(sys.modules[__name__].__file__)
test_dir = os.path.abspath(test_dir)
base_dir = "/tmp/kvm_autotest_root"
default_userspace_paths = ["/usr/bin/qemu-kvm", "/usr/bin/qemu-img"]
check_modules = ["openvswitch"]
online_docs_url = "https://github.com/autotest/autotest/wiki/OpenVSwitch"

if __name__ == "__main__":
    utils_misc.virt_test_assistant(test_name, test_dir, base_dir,
                                   default_userspace_paths, check_modules,
                                   online_docs_url)
