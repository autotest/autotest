#!/usr/bin/python

import unittest, logging, time, sys, os, shelve
import common
from autotest.client.virt import virt_utils
from autotest.client import utils
from autotest.client.shared.test_utils import mock
from autotest.client.shared import cartesian_config

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

class test_PropCan(unittest.TestCase):

    def test_empty_len(self):
        pc = virt_utils.PropCan()
        self.assertEqual(len(pc), 0)

class test_VirtIface(unittest.TestCase):

    VirtIface = virt_utils.VirtIface

    def setUp(self):
        virt_utils.VirtIface.LASTBYTE = -1 # Restart count at zero

    def loop_assert(self, virtiface, test_keys, what_func, string_val):
        for propertea in test_keys:
            attr_access_value = getattr(virtiface, propertea)
            can_access_value = virtiface[propertea]
            get_access_value = virtiface.get(propertea, None)
            expected_value = what_func(propertea)
            self.assertEqual(attr_access_value, can_access_value)
            self.assertEqual(can_access_value, expected_value)
            self.assertEqual(get_access_value, expected_value)
        self.assertEqual(str(virtiface), string_val)

    def test_empty_set(self):
        virtiface = self.VirtIface({})
        self.assertEqual(str(virtiface), "{}")
        virtiface.set_if_none('nic_name', 'foobar')
        self.assertEqual(virtiface.nic_name, 'foobar')

    def test_half_set(self):
        half_prop_end = (len(self.VirtIface.__slots__) / 2) + 1
        props = {}
        for propertea in self.VirtIface.__slots__[0:half_prop_end]:
            props[propertea] = virt_utils.generate_random_string(16)
        virtiface = self.VirtIface(props)
        what_func = lambda propertea:props[propertea]
        self.loop_assert(virtiface, props.keys(), what_func, str(props))

    def test_full_set(self):
        props = {}
        for propertea in self.VirtIface.__slots__:
            props[propertea] = virt_utils.generate_random_string(16)
        virtiface = self.VirtIface(props)
        what_func = lambda propertea:props[propertea]
        self.loop_assert(virtiface, props.keys(), what_func, str(props))

    def test_apendex_set(self):
        """
        Verify container ignores unknown key names
        """
        props = {}
        for propertea in self.VirtIface.__slots__:
            props[propertea] = virt_utils.generate_random_string(16)        
        more_props = {}
        for idx in xrange(0,16):
            more_props[virt_utils.generate_random_string(
                16)] = virt_utils.generate_random_string(16)
        #Keep seperated for testing
        apendex_set = {}
        apendex_set.update(props)
        apendex_set.update(more_props)
        virtiface = self.VirtIface(apendex_set)
        what_func = lambda propertea:props[propertea]
        # str(props) guarantees apendex set wasn't incorporated
        self.loop_assert(virtiface, props.keys(), what_func, str(props))

    def test_mac_completer(self):
        for test_mac in ['9a', '01:02:03:04:05:06', '00', '1:2:3:4:5:6',
                         '0a:0b:0c:0d:0e:0f', 'A0:B0:C0:D0:E0:F0',
                         "01:02:03:04:05:", "01:02:03:04::", "01:02::::",
                         "00:::::::::::::::::::", ":::::::::::::::::::",
                         ":"]:
            result_mac = self.VirtIface.complete_mac_address(test_mac)
        self.assertRaises(TypeError, self.VirtIface.complete_mac_address,
                          '01:f0:0:ba:r!:00')
        self.assertRaises(TypeError, self.VirtIface.complete_mac_address,
                        "01:02:03::05:06")

class test_KVMIface(test_VirtIface):

    def setUp(self):
        self.VirtIface = virt_utils.KVMIface

class test_LibvirtIface(test_VirtIface):

    def setUp(self):
        self.VirtIface = virt_utils.LibvirtIface

class test_VMNetStyle(unittest.TestCase):

    def get_a_map(self, vm_type, driver_type):
        return virt_utils.VMNetStyle.get_style(vm_type, driver_type)

    def test_default_default(self):
        map = self.get_a_map(virt_utils.generate_random_string(16), 
                             virt_utils.generate_random_string(16))
        self.assertEqual(map['mac_prefix'], '9a')
        self.assertEqual(map['container_class'], virt_utils.KVMIface)
        self.assert_(issubclass(map['container_class'], virt_utils.VirtIface))

    def test_libvirt(self):
        map = self.get_a_map('libvirt',
                             virt_utils.generate_random_string(16))
        self.assertEqual(map['container_class'], virt_utils.LibvirtIface)
        self.assert_(issubclass(map['container_class'], virt_utils.VirtIface))


class test_VMNet(unittest.TestCase):

    def setUp(self):
        virt_utils.VirtIface.LASTBYTE = -1 # Restart count at zero

    def test_string_container(self):
        self.assertRaises(TypeError, virt_utils.VMNet, str, ["Foo"])

    def test_VirtIface_container(self):
        test_data = [
            {'nic_name':'nic1', 
             'mac':'0a'},
            {'nic_name':''}, #test data index 1
            {'foo':'bar', 
             'nic_name':'nic2'},
            {'nic_name':'nic3',
             'mac':'01:02:03:04:05:06'}
        ]
        self.assertRaises(virt_utils.VMNetError,
                          virt_utils.VMNet,
                            virt_utils.VirtIface, test_data)
        del test_data[1]
        vmnet = virt_utils.VMNet(virt_utils.VirtIface, test_data)
        self.assertEqual(vmnet[0].nic_name, test_data[0]['nic_name'])
        self.assertEqual(vmnet['nic1'].__class__, virt_utils.VirtIface)
        self.assertEqual(False, hasattr(vmnet['nic1'], 'mac'))
        self.assertEqual(False, 'mac' in vmnet['nic1'].keys())
        self.assertEqual(vmnet.nic_name_list(), ['nic1', 'nic2', 'nic3'])
        self.assertEqual(vmnet.nic_name_index('nic2'), 1)
        self.assertRaises(TypeError, vmnet.nic_name_index, 0)
        self.assertEqual(True, hasattr(vmnet[2], 'mac'))
        self.assertEqual(test_data[2]['mac'], vmnet[2]['mac'])

class test_VMNet_Subclasses(unittest.TestCase):

    nettests_cartesian = ("""
    variants:
        - onevm:
            vms=vm1
        - twovms:
            vms=vm1 vm2
        - threevms:
            vms=vm1 vm2 vm3 vm4

    variants:
        - typeundefined:
        - libvirt:
            vm_type = libvirt
            variants:
                - unsetdrivertype:
                - xen:
                    driver_type = xen
                - qemu:
                    driver_type = qemu
                - kvm:
                    driver_type = kvm
        - kvm:
            vm_type = kvm
            variants:
                - unsetdrivertype:
                - kvm:
                    driver_type = kvm
                - qemu:
                    driver_type = qemu

    variants:
        - nicsundefined:
        - onenic:
            nics=nic1
        - twonics:
            nics=nic1 nic2
        - threenics:
            nics=nic1 nic2 nic3
        - fournics:
            nics=nic1 nic2 nic3 nic4

    variants:
        - nicsmapundefined:
        - onezero:
            nics(_.*) =
        - oneone:
            nics(_.*) = nic1
        - onetwo:
            nics(_.*) = nic1 nic2
        - onethree:
            nics(_.*) = nic1 nic2 nic3
        - onefour:
            nics(_.*) = nic1 nic2 nic3 nic4
        - twotwo:
            nics(_.*) = nic2 nic3 nic4
        - threetwo:
            nics(_.*) = nic3 nic4
        - fourtwo:
            nics(_.*) = nic4 nic2

    variants:
        -propsundefined:
        e-defaultprops:
            mac = 9a
            nic_model = virtio
            nettype = bridge
            netdst = virbr0
            vlan = 0
        -mixedpropsone:
            mac_nic1 = 9a:01
            nic_model_nic1 = rtl8139
            nettype_nic1 = bridge
            netdst_nic1 = virbr1
            vlan_nic1 = 1
            ip_nic1 = 192.168.122.101 
            netdev_nic1 = foobar 
        -mixedpropstwo:
            mac_nic2 = 9a:02
            nic_model_nic2 = e1000
            nettype_nic2 = network
            netdst_nic2 = eth2
            vlan_nic2 = 2
            ip_nic2 = 192.168.122.102
            netdev_nic2 = barfoo
        -mixedpropsthree:
            mac_nic1 = 01:02:03:04:05:06
            mac_nic2 = 07:08:09:0a:0b:0c
            mac_nic4 = 0d:0e:0f:10:11:12
        -mixedpropsthree:
            nettype_nic3 = bridge
            netdst_nic3 = virbr3
            netdev_nic3 = qwerty
    """)

    mac_prefix="01:02:03:04:05:"
    db_filename = '/tmp/UnitTest_AddressPool'
    db_item_count = 0
    counter = 0 # for printing dots

    def setUp(self):
        """
        Runs before every test
        """
        # MAC generator produces from incrementing byte list
        # make sure it starts counting at zero before every test
        virt_utils.VirtIface.LASTBYTE = -1
        parser = cartesian_config.Parser()
        parser.parse_string(self.nettests_cartesian)
        self.CartesianResult = []
        for d in parser.get_dicts():
            params = virt_utils.Params(d)
            self.CartesianResult.append(params)
            for vm_name in params.objects('vms'):
                vm = params.object_params(vm_name)
                nics = vm.get('nics')
                if nics and len(nics.split()) > 0:
                    self.db_item_count += 1

    class FakeVm(object):
        def __init__(self, vm_name, params):
            self.name = vm_name
            self.params = params
            self.get_params = lambda :self.params
            self.vm_type = self.params.get('vm_type')
            self.driver_type = self.params.get('driver_type')
            self.instance = ( "%s-%s" % (
                time.strftime("%Y%m%d-%H%M%S"),
                virt_utils.generate_random_string(16)) )

    def fakevm_generator(self):
        for params in self.CartesianResult:
            for vm_name in params.get('vms').split():
                # Return iterator covering all types of vms
                # in exactly the same order each time. For more info, see:
                # http://docs.python.org/reference/simple_stmts.html#yield
                yield self.FakeVm(vm_name, params)

    def zero_counter(self, increment = 100):
        # rough total, doesn't include the number of vms
        self.increment = increment
        self.counter = 0
        sys.stdout.write(".")
        sys.stdout.flush()

    def print_and_inc(self):
            self.counter += 1
            if self.counter >= self.increment:
                self.counter = 0
                sys.stdout.write(".")
                sys.stdout.flush()

    def test_01_Params(self):
        """
        Load Cartesian combinatorial result verifies against all styles of VM.

        Note: There are some cases where the key should NOT be set, in this
              case an exception is caught prior to verifying
        """
        self.zero_counter()
        for fakevm in self.fakevm_generator():
            test_params = fakevm.get_params()
            virtnet = virt_utils.ParamsNet(test_params,
                                           fakevm.name)
            self.assert_(virtnet.container_class)
            self.assert_(virtnet.mac_prefix)
            self.assert_( issubclass(virtnet.__class__, list) )
            # Assume params actually came from CartesianResult because
            # Checking this takes a very long time across all combinations
            param_nics = test_params.object_params(fakevm.name).get(
                         "nics", test_params.get('nics', "") ).split()
            # Size of list should match number of nics configured
            self.assertEqual(len(param_nics), len(virtnet))
            # Test each interface data
            for virtnet_index in xrange(0, len(virtnet)):
                # index correspondence already established/asserted
                virtnet_nic = virtnet[virtnet_index]
                params_nic = param_nics[virtnet_index]
                self.assert_( issubclass(virtnet_nic.__class__,
                                         virt_utils.PropCan))
                self.assertEqual(virtnet_nic.nic_name, params_nic,
                                    "%s != %s" % (virtnet_nic.nic_name,
                                    params_nic))
                # __slots__ functionality established/asserted elsewhere
                props_to_check = list(virt_utils.VirtIface.__slots__)
                # other tests check mac address handling
                del props_to_check[props_to_check.index('mac')]
                for propertea in props_to_check:
                    params_propertea = test_params.object_params(params_nic
                                                    ).get(propertea)
                    # Double-verify dual-mode access works
                    try:
                        virtnet_propertea1 = getattr(virtnet_nic, propertea)
                        virtnet_propertea2 = virtnet_nic[propertea]
                    except KeyError:
                        # This style may not support all properties, skip
                        continue
                    # Only check stuff cartesian config actually set
                    if params_propertea:
                        self.assertEqual(params_propertea, virtnet_propertea1)
                        self.assertEqual(virtnet_propertea1, virtnet_propertea2)
            self.print_and_inc()


    def test_02_db(self):
        """
        Load Cartesian combinatorial result from params into database
        """
        try:
            os.unlink(self.db_filename)
        except OSError:
            pass
        self.zero_counter()
        for fakevm in self.fakevm_generator():
            test_params = fakevm.get_params()
            virtnet = virt_utils.DbNet(test_params, self.db_filename,
                                                        fakevm.instance)
            self.assert_(hasattr(virtnet, 'container_class'))
            self.assert_(hasattr(virtnet, 'mac_prefix'))
            self.assert_(not hasattr(virtnet, 'lock'))
            self.assert_(not hasattr(virtnet, 'db'))
            vm_name_params = test_params.object_params(fakevm.name)
            nic_name_list = vm_name_params.objects('nics')
            for nic_name in nic_name_list:
                # nic name is only in params scope
                nic_dict = {'nic_name':nic_name}
                nic_params = test_params.object_params(nic_name)
                # avoid processing unsupported properties
                proplist = list(virtnet.container_class.__slots__)
                # name was already set, remove from __slots__ list copy
                del proplist[proplist.index('nic_name')]
                for propertea in proplist:
                    nic_dict[propertea] = nic_params.get(propertea)
                virtnet.append(nic_dict)
            virtnet.update_db()
            # db shouldn't store empty items
            self.print_and_inc()


    def test_03_db(self):
        """
        Load from database created in test_02_db, verify data against params
        """
        # Verify on-disk data matches dummy data just written
        self.zero_counter()
        db = shelve.open(self.db_filename)
        db_keys = db.keys()
        self.assertEqual(len(db_keys), self.db_item_count)
        for key in db_keys:
            db_value = eval(db[key], {}, {})
            self.assert_(isinstance(db_value, list))
            self.assert_(len(db_value) > 0)
            self.assert_(isinstance(db_value[0], dict))
            for nic in db_value:
                mac = nic.get('mac')
                if mac:
                    # Another test already checked mac_is_valid behavior
                    self.assert_(virt_utils.VirtIface.mac_is_valid(mac))
            self.print_and_inc()
        db.close()

    def test_04_VirtNet(self):
        """
        Populate database with max - 1 mac addresses
        """
        try:
            os.unlink(self.db_filename)
        except OSError:
            pass
        self.zero_counter(25)
        for lastbyte in xrange(0, 0xFF):
            # test_07_VirtNet demands last byte in name and mac match
            vm_name = "vm%d" % lastbyte
            if lastbyte < 16:
                mac = "%s0%X" % (self.mac_prefix,lastbyte)
            else:
                mac = "%s%X" % (self.mac_prefix,lastbyte)
            params = virt_utils.Params({
                "nics":"nic1",
                "vms":vm_name,
                "mac_nic1":mac,
            })
            virtnet = virt_utils.VirtNet(params, vm_name,
                                         vm_name, self.db_filename)
            virtnet.mac_prefix = self.mac_prefix
            self.assertEqual(virtnet['nic1'].mac, mac)
            self.assertEqual(virtnet.get_mac_address(0), mac)
            self.assertEqual(virtnet.mac_list(), [mac] )
            self.print_and_inc()


    def test_05_VirtNet(self):
        """
        Load max - 1 entries from db, overriding params.
        """
        self.zero_counter(25)
        # second loop forces db load from disk
        # also confirming params merge with db data
        for lastbyte in xrange(0, 0xFF):
            vm_name = "vm%d" % lastbyte
            params = virt_utils.Params({
                "nics":"nic1",
                "vms":vm_name
            })
            virtnet = virt_utils.VirtNet(params, vm_name,
                                         vm_name, self.db_filename)
            if lastbyte < 16:
                mac = "%s0%X" % (self.mac_prefix,lastbyte)
            else:
                mac = "%s%X" % (self.mac_prefix,lastbyte)
            self.assertEqual(virtnet['nic1'].mac, mac)
            self.assertEqual(virtnet.get_mac_address(0), mac)
            self.print_and_inc()


    def test_06_VirtNet(self):
        """
        Generate last possibly mac and verify value.
        """
        self.zero_counter(25)
        # test two nics, second mac generation should fail (pool exhausted)
        params = virt_utils.Params({
            "nics":"nic1 nic2",
            "vms":"vm255"
        })
        virtnet = virt_utils.VirtNet(params, 'vm255',
                                     'vm255', self.db_filename)
        virtnet.mac_prefix = self.mac_prefix
        self.assertRaises(virt_utils.PropCanKeyError,
                          virtnet.get_mac_address, 'nic1')
        mac = mac = "%s%X" % (self.mac_prefix,255)
        # This will grab the last available address
        # only try 300 times, guarantees LASTBYTE counter will loop once
        self.assertEqual(virtnet.generate_mac_address(0, 300), mac)
        # This will fail allocation
        self.assertRaises(virt_utils.NetError,
                            virtnet.generate_mac_address, 1, 300)


    def test_07_VirtNet(self):
        """
        Release mac from beginning, midle, and end, re-generate + verify value
        """
        self.zero_counter(1)
        beginning_params = virt_utils.Params({
            "nics":"nic1 nic2",
            "vms":"vm0"
        })
        middle_params = virt_utils.Params({
            "nics":"nic1 nic2",
            "vms":"vm127"
        })
        end_params = virt_utils.Params({
            "nics":"nic1 nic2",
            "vms":"vm255",
        })
        for params in (beginning_params,middle_params,end_params):
            vm_name = params['vms']
            virtnet = virt_utils.VirtNet(params, vm_name,
                                         vm_name, self.db_filename)
            virtnet.mac_prefix = self.mac_prefix
            iface = virtnet['nic1']
            last_db_mac_byte = iface.mac_str_to_int_list(iface.mac)[-1]
            last_vm_name_byte = int(vm_name[2:])
            # Sequential generation from test_04_VirtNet guarantee
            self.assertEqual(last_db_mac_byte, last_vm_name_byte)
            # only try 300 times, guarantees LASTBYTE counter will loop once
            self.assertRaises(virt_utils.NetError,
                              virtnet.generate_mac_address, 1, 300)
            virtnet.free_mac_address(0)
            virtnet.free_mac_address(1)
            # generate new on nic1 to verify mac_index generator catches it
            # and to signify database updated after generation
            mac = virtnet.generate_mac_address(1,300)
            last_db_mac_byte = virtnet['nic2'].mac_str_to_int_list(
                virtnet['nic2'].mac)[-1]
            self.assertEqual(last_db_mac_byte, last_vm_name_byte)
            self.assertEqual(virtnet.get_mac_address(1), virtnet[1].mac)
            self.print_and_inc()

    def test_08_ifname(self):
        for fakevm in self.fakevm_generator():
            # only need to test kvm instance
            if fakevm.vm_type != 'kvm':
                continue
            test_params = fakevm.get_params()
            virtnet = virt_utils.VirtNet(test_params,
                                           fakevm.name,
                                           fakevm.name)
            for virtnet_index in xrange(0, len(virtnet)):
                result = virtnet.generate_ifname(virtnet_index)
                self.assertEqual(result, virtnet[virtnet_index].ifname)
                # assume less than 10 nics
                self.assertEqual(14, len(result))
            if len(virtnet) == 2:
                break # no need to test every possible combination

    def test_99_ifname(self):
        # cleanup
        try:
            os.unlink(self.db_filename)
        except OSError:
            pass

if __name__ == '__main__':
    unittest.main()
