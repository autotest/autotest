#
# Copyright 2008 Google Inc. All Rights Reserved.
#

import os, getpass
from autotest_lib.frontend.afe import rpc_client_lib
from autotest_lib.frontend.afe.json_rpc import proxy
from autotest_lib.client.common_lib import global_config

GLOBAL_CONFIG = global_config.global_config
DEFAULT_SERVER = 'autotest'
AFE_RPC_PATH = '/afe/server/noauth/rpc/'
TKO_RPC_PATH = '/new_tko/server/noauth/rpc/'


def get_autotest_server(web_server=None):
    if not web_server:
        if 'AUTOTEST_WEB' in os.environ:
            web_server = os.environ['AUTOTEST_WEB']
        else:
            web_server = 'http://' + GLOBAL_CONFIG.get_config_value(
                    'SERVER', 'hostname', default=DEFAULT_SERVER)

    # if the name doesn't start with http://,
    # nonexistant hosts get an obscure error
    if not web_server.startswith('http://'):
        web_server = 'http://' + web_server

    return web_server


class rpc_comm(object):
    """Shared AFE/TKO RPC class stuff"""
    def __init__(self, web_server, rpc_path, username):
        self.username = username
        self.web_server = get_autotest_server(web_server)
        self.proxy = self._connect(rpc_path)


    def _connect(self, rpc_path):
        # This does not fail even if the address is wrong.
        # We need to wait for an actual RPC to fail
        if self.username:
            username = self.username
        elif 'AUTOTEST_USER' in os.environ:
            username = os.environ['AUTOTEST_USER']
        else:
            username = getpass.getuser()
        headers = {'AUTHORIZATION' : username}
        rpc_server = self.web_server + rpc_path
        return rpc_client_lib.get_proxy(rpc_server, headers=headers)


    def run(self, op, *args, **data):
        if 'AUTOTEST_CLI_DEBUG' in os.environ:
            print self.web_server, op, args, data
        function = getattr(self.proxy, op)
        result = function(*args, **data)
        if 'AUTOTEST_CLI_DEBUG' in os.environ:
            print 'result:', result
        return result


class afe_comm(rpc_comm):
    """Handles the AFE setup and communication through RPC"""
    def __init__(self, web_server=None, rpc_path=AFE_RPC_PATH, username=None):
        super(afe_comm, self).__init__(web_server, rpc_path, username)


class tko_comm(rpc_comm):
    """Handles the TKO setup and communication through RPC"""
    def __init__(self, web_server=None, rpc_path=TKO_RPC_PATH, username=None):
        super(tko_comm, self).__init__(web_server, rpc_path, username)
