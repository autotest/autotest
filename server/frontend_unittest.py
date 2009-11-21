#!/usr/bin/python
#
# Copyright Gregory P. Smith, Google Inc 2008
# Released under the GPL v2

"""Tests for server.frontend."""

from cStringIO import StringIO
import os, sys, unittest
import common
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.frontend.afe import rpc_client_lib
from autotest_lib.server import frontend

GLOBAL_CONFIG = global_config.global_config


class BaseRpcClientTest(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.god.mock_up(rpc_client_lib, 'rpc_client_lib')
        self.god.stub_function(utils, 'send_email')
        self._saved_environ = dict(os.environ)
        if 'AUTOTEST_WEB' in os.environ:
            del os.environ['AUTOTEST_WEB']


    def tearDown(self):
        self.god.unstub_all()
        os.environ.clear()
        os.environ.update(self._saved_environ)


class RpcClientTest(BaseRpcClientTest):
    def test_init(self):
        os.environ['LOGNAME'] = 'unittest-user'
        GLOBAL_CONFIG.override_config_value('SERVER', 'hostname', 'test-host')
        rpc_client_lib.get_proxy.expect_call(
                'http://test-host/path',
                headers={'AUTHORIZATION': 'unittest-user'})
        frontend.RpcClient('/path', None, None, None, None, None)
        self.god.check_playback()


class AFETest(BaseRpcClientTest):
    def test_result_notify(self):
        class fake_job(object):
            result = True
            name = 'nameFoo'
            id = 'idFoo'
            results_platform_map = {'NORAD' : {'Seeking_Joshua': ['WOPR']}}
        GLOBAL_CONFIG.override_config_value('SERVER', 'hostname', 'chess')
        rpc_client_lib.get_proxy.expect_call(
                'http://chess/afe/server/noauth/rpc/',
                headers={'AUTHORIZATION': 'david'})
        self.god.stub_function(utils, 'send_email')
        utils.send_email.expect_any_call()

        my_afe = frontend.AFE(user='david')

        fake_stdout = StringIO()
        self.god.stub_with(sys, 'stdout', fake_stdout)
        my_afe.result_notify(fake_job, 'userA', 'userB')
        self.god.unstub(sys, 'stdout')
        fake_stdout = fake_stdout.getvalue()

        self.god.check_playback()

        self.assert_('PASSED' in fake_stdout)
        self.assert_('WOPR' in fake_stdout)
        self.assert_('http://chess/tko/compose_query.cgi?' in fake_stdout)
        self.assert_('columns=test' in fake_stdout)
        self.assert_('rows=machine_group' in fake_stdout)
        self.assert_("condition=tag~'idFoo-%25'" in fake_stdout)
        self.assert_('title=Report' in fake_stdout)
        self.assert_('Sending email' in fake_stdout)



if __name__ == '__main__':
    unittest.main()
