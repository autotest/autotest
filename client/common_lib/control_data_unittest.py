#!/usr/bin/python

import os, sys, unittest
import common
from autotest_lib.client.common_lib import control_data, autotemp

ControlData = control_data.ControlData

CONTROL = """
AUTHOR = 'Author'
DEPENDENCIES = "console, power"
DOC = \"\"\"\
doc stuff\"\"\"
# EXPERIMENTAL should implicitly be False
NAME = 'nA' "mE"
RUN_VERIFY = False
SYNC_COUNT = 2
TIME='short'
TEST_CLASS=u'Kernel'
TEST_CATEGORY='Stress'
TEST_TYPE='client'
"""


class ParseControlTest(unittest.TestCase):
    def setUp(self):
        self.control_tmp = autotemp.tempfile(unique_id='control_unit',
                                             text=True)
        os.write(self.control_tmp.fd, CONTROL)
        os.close(self.control_tmp.fd)


    def tearDown(self):
        self.control_tmp.clean()


    def test_parse_control(self):
        cd = control_data.parse_control(self.control_tmp.name, True)
        self.assertEquals(cd.author, "Author")
        self.assertEquals(cd.dependencies, set(['console', 'power']))
        self.assertEquals(cd.doc, "doc stuff")
        self.assertEquals(cd.experimental, False)
        self.assertEquals(cd.name, "nAmE")
        self.assertEquals(cd.run_verify, False)
        self.assertEquals(cd.sync_count, 2)
        self.assertEquals(cd.time, "short")
        self.assertEquals(cd.test_class, "kernel")
        self.assertEquals(cd.test_category, "stress")
        self.assertEquals(cd.test_type, "client")


class SetMethodTests(unittest.TestCase):
    def setUp(self):
        self.required_vars = control_data.REQUIRED_VARS
        control_data.REQUIRED_VARS = set()


    def tearDown(self):
        control_data.REQUIRED_VARS = self.required_vars


    def test_bool(self):
        cd = ControlData({}, 'filename')
        cd._set_bool('foo', 'False')
        self.assertEquals(cd.foo, False)
        cd._set_bool('foo', True)
        self.assertEquals(cd.foo, True)
        cd._set_bool('foo', 'FALSE')
        self.assertEquals(cd.foo, False)
        cd._set_bool('foo', 'true')
        self.assertEquals(cd.foo, True)
        self.assertRaises(ValueError, cd._set_bool, 'foo', '')
        self.assertRaises(ValueError, cd._set_bool, 'foo', 1)
        self.assertRaises(ValueError, cd._set_bool, 'foo', [])
        self.assertRaises(ValueError, cd._set_bool, 'foo', None)


    def test_int(self):
        cd = ControlData({}, 'filename')
        cd._set_int('foo', 0)
        self.assertEquals(cd.foo, 0)
        cd._set_int('foo', '0')
        self.assertEquals(cd.foo, 0)
        cd._set_int('foo', '-1', min=-2, max=10)
        self.assertEquals(cd.foo, -1)
        self.assertRaises(ValueError, cd._set_int, 'foo', 0, min=1)
        self.assertRaises(ValueError, cd._set_int, 'foo', 1, max=0)
        self.assertRaises(ValueError, cd._set_int, 'foo', 'x')
        self.assertRaises(ValueError, cd._set_int, 'foo', '')
        self.assertRaises(TypeError, cd._set_int, 'foo', None)


    def test_set(self):
        cd = ControlData({}, 'filename')
        cd._set_set('foo', 'a')
        self.assertEquals(cd.foo, set(['a']))
        cd._set_set('foo', 'a,b,c')
        self.assertEquals(cd.foo, set(['a', 'b', 'c']))
        cd._set_set('foo', ' a , b , c     ')
        self.assertEquals(cd.foo, set(['a', 'b', 'c']))
        cd._set_set('foo', None)
        self.assertEquals(cd.foo, set(['None']))


    def test_string(self):
        cd = ControlData({}, 'filename')
        cd._set_string('foo', 'a')
        self.assertEquals(cd.foo, 'a')
        cd._set_string('foo', 'b')
        self.assertEquals(cd.foo, 'b')
        cd._set_string('foo', 'B')
        self.assertEquals(cd.foo, 'B')
        cd._set_string('foo', 1)
        self.assertEquals(cd.foo, '1')
        cd._set_string('foo', None)
        self.assertEquals(cd.foo, 'None')
        cd._set_string('foo', [])
        self.assertEquals(cd.foo, '[]')


    def test_option(self):
        options = ['a', 'b']
        cd = ControlData({}, 'filename')
        cd._set_option('foo', 'a', options)
        self.assertEquals(cd.foo, 'a')
        cd._set_option('foo', 'b', options)
        self.assertEquals(cd.foo, 'b')
        cd._set_option('foo', 'B', options)
        self.assertEquals(cd.foo, 'B')
        self.assertRaises(ValueError, cd._set_option,
                          'foo', 'x', options)
        self.assertRaises(ValueError, cd._set_option,
                          'foo', 1, options)
        self.assertRaises(ValueError, cd._set_option,
                          'foo', [], options)
        self.assertRaises(ValueError, cd._set_option,
                          'foo', None, options)


# this is so the test can be run in standalone mode
if __name__ == '__main__':
    unittest.main()
