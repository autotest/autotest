#!/usr/bin/python

import os, sys, tempfile, unittest, types
import common
from autotest_lib.client.common_lib import global_config


global_config_ini_contents = """
[SECTION_A]
value_1: 6.0
value_2: hello
value_3: true
value_4: FALSE
value_5: tRuE
value_6: falsE

[SECTION_B]
value_1: -5
value_2: 2.3
value_3: 0
value_4: 7

[SECTION_C]
value_1: nobody@localhost
"""

shadow_config_ini_contents = """
[SECTION_C]
value_1: somebody@remotehost
"""


def create_config_files():
    (fp, global_file) = tempfile.mkstemp(".ini", text=True)
    os.write(fp, global_config_ini_contents)
    os.close(fp)

    (fp, shadow_file) = tempfile.mkstemp(".ini", text=True)
    os.write(fp, shadow_config_ini_contents)
    os.close(fp)

    return (global_file, shadow_file)


class global_config_test(unittest.TestCase):
    # grab the singelton
    conf = global_config.global_config

    def setUp(self):
        # set the config files to our test files
        (self.global_file, self.shadow_file) = create_config_files()
        self.conf.set_config_files(self.global_file, self.shadow_file)


    def tearDown(self):
        os.remove(self.global_file)
        os.remove(self.shadow_file)
        self.conf.set_config_files(global_config.DEFAULT_CONFIG_FILE,
                                global_config.DEFAULT_SHADOW_FILE)


    def test_float(self):
        val = self.conf.get_config_value("SECTION_A", "value_1", float)
        self.assertEquals(type(val), types.FloatType)
        self.assertEquals(val, 6.0)


    def test_int(self):
        val = self.conf.get_config_value("SECTION_B", "value_1", int)
        self.assertEquals(type(val), types.IntType)
        self.assertTrue(val < 0)
        val = self.conf.get_config_value("SECTION_B", "value_3", int)
        self.assertEquals(val, 0)
        val = self.conf.get_config_value("SECTION_B", "value_4", int)
        self.assertTrue(val > 0)


    def test_string(self):
        val = self.conf.get_config_value("SECTION_A", "value_2")
        self.assertEquals(type(val),types.StringType)
        self.assertEquals(val, "hello")


    def test_override(self):
        val = self.conf.get_config_value("SECTION_C", "value_1")
        self.assertEquals(val, "somebody@remotehost")


    def test_exception(self):
        error = 0
        try:
            val = self.conf.get_config_value("SECTION_B",
                                            "value_2", int)
        except:
            error = 1
        self.assertEquals(error, 1)


    def test_boolean(self):
        val = self.conf.get_config_value("SECTION_A", "value_3", bool)
        self.assertEquals(val, True)
        val = self.conf.get_config_value("SECTION_A", "value_4", bool)
        self.assertEquals(val, False)
        val = self.conf.get_config_value("SECTION_A", "value_5", bool)
        self.assertEquals(val, True)
        val = self.conf.get_config_value("SECTION_A", "value_6", bool)
        self.assertEquals(val, False)


    def test_defaults(self):
        val = self.conf.get_config_value("MISSING", "foo", float, 3.6)
        self.assertEquals(val, 3.6)
        val = self.conf.get_config_value("SECTION_A", "novalue", str,
                                                "default")
        self.assertEquals(val, "default")


# this is so the test can be run in standalone mode
if __name__ == '__main__':
    unittest.main()
