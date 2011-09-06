#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This module defines the unittests for the Autotest class
"""

__author__ = """stutsman@google.com (Ryan Stutsman)"""

import os
import sys
import unittest

import common

from autotest_lib.server import utils
from autotest_lib.server import autotest
from autotest_lib.server import hosts


class AutotestTestCase(unittest.TestCase):
    def setUp(self):
        self.autotest = autotest.Autotest()

    def tearDown(self):
        pass


    def testGetAutoDir(self):
        class MockInstallHost:
            def __init__(self):
                self.commands = []
                self.result = "autodir='/stuff/autotest'\n"

            def run(self, command):
                if command == "grep autodir= /etc/autotest.conf":
                    result = hosts.CmdResult()
                    result.stdout = self.result
                    return result
                else:
                    self.commands.append(command)

        host = MockInstallHost()
        self.assertEqual('/stuff/autotest',
                         autotest.Autotest.get_installed_autodir(host))
        host.result = "autodir=/stuff/autotest\n"
        self.assertEqual('/stuff/autotest',
                         autotest.Autotest.get_installed_autodir(host))
        host.result = 'autodir="/stuff/auto test"\n'
        self.assertEqual('/stuff/auto test',
                         autotest.Autotest.get_installed_autodir(host))


    def testInstallFromDir(self):
        class MockInstallHost:
            def __init__(self):
                self.commands = []

            def run(self, command):
                if command == "grep autodir= /etc/autotest.conf":
                    result= hosts.CmdResult()
                    result.stdout = "autodir=/usr/local/autotest\n"
                    return result
                else:
                    self.commands.append(command)

            def send_file(self, src, dst):
                self.commands.append("send_file: %s %s" % (src,
                                                           dst))

        host = MockInstallHost()
        tmpdir = utils.get_tmp_dir()
        self.autotest.get(tmpdir)
        self.autotest.install(host)
        self.assertEqual(host.commands[0],
                         'mkdir -p /usr/local/autotest')
        self.assertTrue(host.commands[1].startswith('send_file: /tmp/'))
        self.assertTrue(host.commands[1].endswith(
                '/ /usr/local/autotest'))




    def testInstallFromSVN(self):
        class MockInstallHost:
            def __init__(self):
                self.commands = []

            def run(self, command):
                if command == "grep autodir= /etc/autotest.conf":
                    result= hosts.CmdResult()
                    result.stdout = "autodir=/usr/local/autotest\n"
                    return result
                else:
                    self.commands.append(command)

        host = MockInstallHost()
        self.autotest.install(host)
        self.assertEqual(host.commands,
                         ['svn checkout '
                          + autotest.AUTOTEST_SVN + ' '
                          + "/usr/local/autotest"])


    def testFirstInstallFromSVNFails(self):
        class MockFirstInstallFailsHost:
            def __init__(self):
                self.commands = []

            def run(self, command):
                if command == "grep autodir= /etc/autotest.conf":
                    result= hosts.CmdResult()
                    result.stdout = "autodir=/usr/local/autotest\n"
                    return result
                else:
                    self.commands.append(command)
                    first = ('svn checkout ' +
                        autotest.AUTOTEST_SVN + ' ' +
                        "/usr/local/autotest")
                    if (command == first):
                        raise autotest.AutoservRunError(
                                "svn not found")

        host = MockFirstInstallFailsHost()
        self.autotest.install(host)
        self.assertEqual(host.commands,
                         ['svn checkout ' + autotest.AUTOTEST_SVN +
                          ' ' + "/usr/local/autotest",
                          'svn checkout ' + autotest.AUTOTEST_HTTP +
                          ' ' + "/usr/local/autotest"])


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(AutotestTestCase)

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
