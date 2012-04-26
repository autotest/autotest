#!/usr/bin/python

import unittest, logging
import common
from autotest.client.tests.virt import virt_utils
from autotest.client import utils
from autotest.client.shared.test_utils import mock
from autotest.client.tests.virt import cartesian_config

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


    def test_git_repo_param_helper(self):
        config = """git_repo_foo_uri = git://git.foo.org/foo.git
git_repo_foo_branch = next
git_repo_foo_lbranch = local
git_repo_foo_commit = bc732ad8b2ed8be52160b893735417b43a1e91a8
"""
        config_parser = cartesian_config.Parser()
        config_parser.parse_string(config)
        params = config_parser.get_dicts().next()

        h = virt_utils.GitRepoParamHelper(params, 'foo', '/tmp/foo')
        self.assertEqual(h.name, 'foo')
        self.assertEqual(h.branch, 'next')
        self.assertEqual(h.lbranch, 'local')
        self.assertEqual(h.commit, 'bc732ad8b2ed8be52160b893735417b43a1e91a8')


class FakeCmd(object):
    def __init__(self, cmd):
        self.fake_cmds = [
{"cmd": "numactl --hardware",
"stdout": """
available: 1 nodes (0)
node 0 cpus: 0 1 2 3 4 5 6 7
node 0 size: 18431 MB
node 0 free: 17186 MB
node distances:
node   0
  0:  10
"""},
{"cmd": "ps -eLf | awk '{print $4}'",
"stdout": """
1230
1231
1232
1233
1234
1235
1236
1237
"""},
{"cmd": "taskset -p 0x1 1230", "stdout": ""},
{"cmd": "taskset -p 0x2 1231", "stdout": ""},
{"cmd": "taskset -p 0x4 1232", "stdout": ""},
{"cmd": "taskset -p 0x8 1233", "stdout": ""},
{"cmd": "taskset -p 0x10 1234", "stdout": ""},
{"cmd": "taskset -p 0x20 1235", "stdout": ""},
{"cmd": "taskset -p 0x40 1236", "stdout": ""},
{"cmd": "taskset -p 0x80 1237", "stdout": ""},

]

        self.stdout = self.get_stdout(cmd)


    def get_stdout(self, cmd):
        for fake_cmd in self.fake_cmds:
            if fake_cmd['cmd'] == cmd:
                return fake_cmd['stdout']
        raise ValueError("Could not locate locate '%s' on fake cmd db" % cmd)


def utils_run(cmd):
    return FakeCmd(cmd)


class TestNumaNode(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god(ut=self)
        self.god.stub_with(utils, 'run', utils_run)
        self.numa_node = virt_utils.NumaNode(-1)


    def test_get_node_num(self):
        self.assertEqual(self.numa_node.get_node_num(), '1')


    def test_get_node_cpus(self):
        self.assertEqual(self.numa_node.get_node_cpus(0), '0 1 2 3 4 5 6 7')


    def test_pin_cpu(self):
        self.assertEqual(self.numa_node.pin_cpu("1230"), "0")
        self.assertEqual(self.numa_node.dict["0"], "1230")

        self.assertEqual(self.numa_node.pin_cpu("1231"), "1")
        self.assertEqual(self.numa_node.dict["1"], "1231")

        self.assertEqual(self.numa_node.pin_cpu("1232"), "2")
        self.assertEqual(self.numa_node.dict["2"], "1232")

        self.assertEqual(self.numa_node.pin_cpu("1233"), "3")
        self.assertEqual(self.numa_node.dict["3"], "1233")

        self.assertEqual(self.numa_node.pin_cpu("1234"), "4")
        self.assertEqual(self.numa_node.dict["4"], "1234")

        self.assertEqual(self.numa_node.pin_cpu("1235"), "5")
        self.assertEqual(self.numa_node.dict["5"], "1235")

        self.assertEqual(self.numa_node.pin_cpu("1236"), "6")
        self.assertEqual(self.numa_node.dict["6"], "1236")

        self.assertEqual(self.numa_node.pin_cpu("1237"), "7")
        self.assertEqual(self.numa_node.dict["7"], "1237")

        self.assertTrue("free" not in self.numa_node.dict.values())


    def test_free_cpu(self):
        self.assertEqual(self.numa_node.pin_cpu("1230"), "0")
        self.assertEqual(self.numa_node.dict["0"], "1230")

        self.assertEqual(self.numa_node.pin_cpu("1231"), "1")
        self.assertEqual(self.numa_node.dict["1"], "1231")

        self.numa_node.free_cpu("0")
        self.assertEqual(self.numa_node.dict["0"], "free")
        self.assertEqual(self.numa_node.dict["1"], "1231")


    def tearDown(self):
        self.god.unstub_all()


if __name__ == '__main__':
    unittest.main()
