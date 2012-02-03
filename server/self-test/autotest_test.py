#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This module defines the unittests for the Autotest class
"""

__author__ = """stutsman@google.com (Ryan Stutsman)"""

import os
import sys
import unittest
import logging

import common

from autotest_lib.server import utils
from autotest_lib.server import autotest_remote
from autotest_lib.server import hosts
from autotest_lib.client.common_lib import global_config


_GLOBAL_CONFIG = global_config.global_config
_TOP_PATH = _GLOBAL_CONFIG.get_config_value('COMMON', 'autotest_top_path')

class AutotestTestCase(unittest.TestCase):
    def setUp(self):
        self.autotest = autotest_remote.Autotest()

    def tearDown(self):
        pass


    def testGetAutoDir(self):
        class MockInstallHost:
            def __init__(self):
                self.commands = []

            def run(self, command, ignore_status=False):
                self.commands.append(command)

            def wait_up(self, timeout):
                pass

            def get_autodir(self):
                pass

        host = MockInstallHost()
        self.assertEqual(_TOP_PATH,
                         autotest_remote.Autotest.get_installed_autodir(host))


    def testInstallFromDir(self):
        class MockInstallHost:
            def __init__(self):
                self.commands = []
                self.hostname = 'autotest-client.foo.com'

            def run(self, command, ignore_status=False):
                self.commands.append(command)

            def send_file(self, src, dst, delete_dest=False):
                self.commands.append("send_file: %s %s" % (src, dst))

            def wait_up(self, timeout):
                pass

            def get_autodir(self):
                pass

            def set_autodir(self, autodir):
                pass

            def setup(self):
                pass

        host = MockInstallHost()
        tmpdir = utils.get_tmp_dir()
        self.autotest.get(tmpdir)
        self.autotest.install(host)
        self.assertEqual(host.commands[0],
                         'test -x %s/bin/autotest' % _TOP_PATH)
        self.assertEqual(host.commands[1], 'test -w %s' % _TOP_PATH)
        self.assertEqual(host.commands[2], 'mkdir -p %s' % _TOP_PATH)
        self.assertTrue(host.commands[4].startswith('send_file: []'))
        self.assertTrue(host.commands[4].endswith(_TOP_PATH))


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(AutotestTestCase)

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
