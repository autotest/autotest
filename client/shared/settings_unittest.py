#!/usr/bin/python

import os
import types
import unittest

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.client.shared import settings
from autotest.client.shared import autotemp


settings_ini_contents = """
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
    global_temp = autotemp.tempfile("global", ".ini",
                                    text=True)
    os.write(global_temp.fd, settings_ini_contents)

    shadow_temp = autotemp.tempfile("shadow", ".ini",
                                    text=True)
    fd = shadow_temp.fd
    os.write(shadow_temp.fd, shadow_config_ini_contents)

    return (global_temp, shadow_temp)


class settings_test(unittest.TestCase):
    # grab the singelton
    conf = settings.settings

    def setUp(self):
        # set the config files to our test files
        (self.global_temp, self.shadow_temp) = create_config_files()

        self.conf.set_config_files(self.global_temp.name, self.shadow_temp.name)

    def tearDown(self):
        self.shadow_temp.clean()
        self.global_temp.clean()
        self.conf.set_config_files(settings.DEFAULT_CONFIG_FILE,
                                   settings.DEFAULT_SHADOW_FILE)

    def test_float(self):
        val = self.conf.get_value("SECTION_A", "value_1", float)
        self.assertEquals(type(val), types.FloatType)
        self.assertEquals(val, 6.0)

    def test_int(self):
        val = self.conf.get_value("SECTION_B", "value_1", int)
        self.assertEquals(type(val), types.IntType)
        self.assertTrue(val < 0)
        val = self.conf.get_value("SECTION_B", "value_3", int)
        self.assertEquals(val, 0)
        val = self.conf.get_value("SECTION_B", "value_4", int)
        self.assertTrue(val > 0)

    def test_string(self):
        val = self.conf.get_value("SECTION_A", "value_2")
        self.assertEquals(type(val), types.StringType)
        self.assertEquals(val, "hello")

    def test_override(self):
        val = self.conf.get_value("SECTION_C", "value_1")
        self.assertEquals(val, "somebody@remotehost")

    def test_exception(self):
        error = 0
        try:
            val = self.conf.get_value("SECTION_B",
                                      "value_2", int)
        except Exception:
            error = 1
        self.assertEquals(error, 1)

    def test_boolean(self):
        val = self.conf.get_value("SECTION_A", "value_3", bool)
        self.assertEquals(val, True)
        val = self.conf.get_value("SECTION_A", "value_4", bool)
        self.assertEquals(val, False)
        val = self.conf.get_value("SECTION_A", "value_5", bool)
        self.assertEquals(val, True)
        val = self.conf.get_value("SECTION_A", "value_6", bool)
        self.assertEquals(val, False)

    def test_defaults(self):
        val = self.conf.get_value("MISSING", "foo", float, 3.6)
        self.assertEquals(val, 3.6)
        val = self.conf.get_value("SECTION_A", "novalue", str,
                                  "default")
        self.assertEquals(val, "default")


# this is so the test can be run in standalone mode
if __name__ == '__main__':
    unittest.main()
