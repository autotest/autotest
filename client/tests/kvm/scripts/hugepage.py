#!/usr/bin/python
# -*- coding: utf-8 -*-
import os, sys, time

"""
Simple script to allocate enough hugepages for KVM testing purposes.
"""

class HugePageError(Exception):
    """
    Simple wrapper for the builtin Exception class.
    """
    pass


class HugePage:
    def __init__(self, hugepage_path=None):
        """
        Gets environment variable values and calculates the target number
        of huge memory pages.

        @param hugepage_path: Path where to mount hugetlbfs path, if not
                yet configured.
        """
        self.vms = len(os.environ['KVM_TEST_vms'].split())
        self.mem = int(os.environ['KVM_TEST_mem'])
        try:
            self.max_vms = int(os.environ['KVM_TEST_max_vms'])
        except KeyError:
            self.max_vms = 0

        if hugepage_path:
            self.hugepage_path = hugepage_path
        else:
            self.hugepage_path = '/mnt/kvm_hugepage'

        self.hugepage_size = self.get_hugepage_size()
        self.target_hugepages = self.get_target_hugepages()


    def get_hugepage_size(self):
        """
        Get the current system setting for huge memory page size.
        """
        meminfo = open('/proc/meminfo', 'r').readlines()
        huge_line_list = [h for h in meminfo if h.startswith("Hugepagesize")]
        try:
            return int(huge_line_list[0].split()[1])
        except ValueError, e:
            raise HugePageError("Could not get huge page size setting from "
                                "/proc/meminfo: %s" % e)


    def get_target_hugepages(self):
        """
        Calculate the target number of hugepages for testing purposes.
        """
        if self.vms < self.max_vms:
            self.vms = self.max_vms
        # memory of all VMs plus qemu overhead of 64MB per guest
        vmsm = (self.vms * self.mem) + (self.vms * 64)
        return int(vmsm * 1024 / self.hugepage_size)


    def set_hugepages(self):
        """
        Sets the hugepage limit to the target hugepage value calculated.
        """
        hugepage_cfg = open("/proc/sys/vm/nr_hugepages", "r+")
        hp = hugepage_cfg.readline()
        while int(hp) < self.target_hugepages:
            loop_hp = hp
            hugepage_cfg.write(str(self.target_hugepages))
            hugepage_cfg.flush()
            hugepage_cfg.seek(0)
            hp = int(hugepage_cfg.readline())
            if loop_hp == hp:
                raise HugePageError("Cannot set the kernel hugepage setting "
                                    "to the target value of %d hugepages." %
                                    self.target_hugepages)
        hugepage_cfg.close()


    def mount_hugepage_fs(self):
        """
        Verify if there's a hugetlbfs mount set. If there's none, will set up
        a hugetlbfs mount using the class attribute that defines the mount
        point.
        """
        if not os.path.ismount(self.hugepage_path):
            if not os.path.isdir(self.hugepage_path):
                os.makedirs(self.hugepage_path)
            cmd = "mount -t hugetlbfs none %s" % self.hugepage_path
            if os.system(cmd):
                raise HugePageError("Cannot mount hugetlbfs path %s" %
                                    self.hugepage_path)


    def setup(self):
        self.set_hugepages()
        self.mount_hugepage_fs()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        huge_page = HugePage()
    else:
        huge_page = HugePage(sys.argv[1])

    huge_page.setup()
