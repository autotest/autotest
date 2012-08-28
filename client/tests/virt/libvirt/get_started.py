#!/usr/bin/python
"""
Program to help setup libvirt test environment

@copyright: Red Hat 2011
"""
import os, sys
import common
from virttest import utils_misc

test_name = "libvirt"
test_dir = os.path.dirname(sys.modules[__name__].__file__)
test_dir = os.path.abspath(test_dir)
base_dir = "/tmp/libvirt_autotest_root"
default_userspace_paths = ["/usr/bin/virt-install"]
check_modules = None
online_docs_url = None

if __name__ == "__main__":
    utils_misc.virt_test_assistant(test_name, test_dir, base_dir,
                                   default_userspace_paths, check_modules,
                                   online_docs_url)
