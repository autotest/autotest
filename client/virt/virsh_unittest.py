#!/usr/bin/python

import unittest
import common

class module_load_test(unittest.TestCase):

    from autotest.client.virt import virsh


class constants_test(module_load_test):

    def test_module_load(self):
        self.assertTrue(hasattr(self.virsh, 'VIRSH_PROPERTIES'))
        self.assertTrue(hasattr(self.virsh, 'VIRSH_SESSION_PROPS'))
        self.assertTrue(hasattr(self.virsh, 'VIRSH_EXEC'))


class DArgMangler_test(module_load_test):

    def setUp(self):
        self.testparent = {'foo':'bar'}
        self.d1 = self.virsh.DArgMangler({})
        self.d2 = self.virsh.DArgMangler(self.testparent)

    def test_length_parent(self):
        self.assertEqual(len(self.d1), 0)
        self.assertEqual(len(self.d2), 0)

    def test_comparison(self):
        self.assertEqual(self.d1, self.d2)

    def test_bool_parent(self):
        self.assertFalse(self.d1)
        self.assertFalse(self.d2)

    def test_parent_lookup(self):
        key = self.testparent.keys()[0]
        self.assertEqual(self.d2[key], self.testparent[key])

    def test_init(self):
        self.assertRaises(ValueError, self.virsh.DArgMangler, None)


class class_constructors_test(module_load_test):

    def test_VirshBase(self):
        vb = self.virsh.VirshBase()


    def test_Virsh(self):
        v = self.virsh.Virsh()


    def test_VirshPersistent(self):
        vp = self.virsh.VirshPersistent()


    def test_DArgMangler(self):
        dm = self.virsh.DArgMangler({})


class virsh_has_help_command_test(module_load_test):

    def test_false_command(self):
        self.assertFalse(self.virsh.has_help_command('print'))
        self.assertFalse(self.virsh.has_help_command('Commands:'))
        self.assertFalse(self.virsh.has_help_command('dom'))
        self.assertFalse(self.virsh.has_help_command('pool'))


    def test_true_command(self):
        self.assertTrue(self.virsh.has_help_command('uri'))
        self.assertTrue(self.virsh.has_help_command('help'))
        self.assertTrue(self.virsh.has_help_command('list'))


    def test_no_cache(self):
        self.virsh.VIRSH_COMMAND_CACHE = None
        self.assertTrue(self.virsh.has_help_command('uri'))
        self.virsh.VIRSH_COMMAND_CACHE = []
        self.assertTrue(self.virsh.has_help_command('uri'))


class virsh_help_command_test(module_load_test):

    def test_cache_command(self):
        l1 = self.virsh.help_command(cache=True)
        l2 = self.virsh.help_command()
        l3 = self.virsh.help_command()
        self.assertEqual(l1, l2)
        self.assertEqual(l2,l3)
        self.assertEqual(l3,l1)


class virsh_class_has_help_command_test(virsh_has_help_command_test):

    def setUp(self):
        self.virsh = self.virsh.Virsh(debug=True)

class virsh_persistent_class_has_help_command_test(virsh_has_help_command_test):

    def setUp(self):
        self.virsh = self.virsh.VirshPersistent(debug=True)

if __name__ == '__main__':
    unittest.main()
