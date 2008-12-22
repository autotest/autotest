#!/usr/bin/python
#
# Copyright 2008 Google Inc. All Rights Reserved.

"""Test for the rpc proxy class."""

import unittest, os
import common
from autotest_lib.cli import rpc
from autotest_lib.client.common_lib import global_config
from autotest_lib.frontend.afe import rpc_client_lib
from autotest_lib.frontend.afe.json_rpc import proxy

GLOBAL_CONFIG = global_config.global_config


class rpc_unittest(unittest.TestCase):
    def setUp(self):
        self.old_environ = os.environ.copy()
        if 'AUTOTEST_WEB' in os.environ:
            del os.environ['AUTOTEST_WEB']


    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_environ)


    def test_get_autotest_server_specific(self):
        self.assertEqual('http://foo', rpc.get_autotest_server('foo'))


    def test_get_autotest_server_none(self):
        GLOBAL_CONFIG.override_config_value('SERVER', 'hostname', 'Prince')
        self.assertEqual('http://Prince', rpc.get_autotest_server(None))


    def test_get_autotest_server_environ(self):
        os.environ['AUTOTEST_WEB'] = 'foo-dev'
        self.assertEqual('http://foo-dev', rpc.get_autotest_server(None))
        del os.environ['AUTOTEST_WEB']


    def test_get_autotest_server_environ_precedence(self):
        os.environ['AUTOTEST_WEB'] = 'foo-dev'
        self.assertEqual('http://foo', rpc.get_autotest_server('foo'))
        del os.environ['AUTOTEST_WEB']


if __name__ == '__main__':
    unittest.main()
