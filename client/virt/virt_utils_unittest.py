#!/usr/bin/python

import unittest
import common
from autotest_lib.client.virt import virt_utils

class virt_utils_test(unittest.TestCase):


    def test_cpu_vendor_intel(self):
        flags = ['fpu', 'vme', 'de', 'pse', 'tsc', 'msr', 'pae', 'mce',
                 'cx8', 'apic', 'sep', 'mtrr', 'pge', 'mca', 'cmov',
                 'pat', 'pse36', 'clflush', 'dts', 'acpi', 'mmx', 'fxsr',
                 'sse', 'sse2', 'ss', 'ht', 'tm', 'pbe', 'syscall', 'nx',
                 'lm', 'constant_tsc', 'arch_perfmon', 'pebs', 'bts',
                 'rep_good', 'aperfmperf', 'pni', 'dtes64', 'monitor',
                 'ds_cpl', 'vmx', 'smx', 'est', 'tm2', 'ssse3', 'cx16',
                 'xtpr', 'pdcm', 'sse4_1', 'xsave', 'lahf_lm', 'ida',
                 'tpr_shadow', 'vnmi', 'flexpriority']
        vendor = virt_utils.get_cpu_vendor(flags, False)
        self.assertEqual(vendor, 'intel')


    def test_cpu_vendor_amd(self):
        flags = ['fpu', 'vme', 'de', 'pse', 'tsc', 'msr', 'pae', 'mce',
                 'cx8', 'apic', 'mtrr', 'pge', 'mca', 'cmov', 'pat',
                 'pse36', 'clflush', 'mmx', 'fxsr', 'sse', 'sse2',
                 'ht', 'syscall', 'nx', 'mmxext', 'fxsr_opt', 'pdpe1gb',
                 'rdtscp', 'lm', '3dnowext', '3dnow', 'constant_tsc',
                 'rep_good', 'nonstop_tsc', 'extd_apicid', 'aperfmperf',
                 'pni', 'monitor', 'cx16', 'popcnt', 'lahf_lm',
                 'cmp_legacy', 'svm', 'extapic', 'cr8_legacy', 'abm',
                 'sse4a', 'misalignsse', '3dnowprefetch', 'osvw', 'ibs',
                 'skinit', 'wdt', 'cpb', 'npt', 'lbrv', 'svm_lock',
                 'nrip_save']
        vendor = virt_utils.get_cpu_vendor(flags, False)
        self.assertEqual(vendor, 'amd')


    def test_vendor_unknown(self):
        flags = ['non', 'sense', 'flags']
        vendor = virt_utils.get_cpu_vendor(flags, False)
        self.assertEqual(vendor, 'unknown')


    def test_get_archive_tarball_name(self):
        tarball_name = virt_utils.get_archive_tarball_name('/tmp',
                                                           'tmp-archive',
                                                           'bz2')
        self.assertEqual(tarball_name, 'tmp-archive.tar.bz2')


    def test_get_archive_tarball_name_absolute(self):
        tarball_name = virt_utils.get_archive_tarball_name('/tmp',
                                                           '/var/tmp/tmp',
                                                           'bz2')
        self.assertEqual(tarball_name, '/var/tmp/tmp.tar.bz2')


    def test_get_archive_tarball_name_from_dir(self):
        tarball_name = virt_utils.get_archive_tarball_name('/tmp',
                                                           None,
                                                           'bz2')
        self.assertEqual(tarball_name, 'tmp.tar.bz2')


if __name__ == '__main__':
    unittest.main()
