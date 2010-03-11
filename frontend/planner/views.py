import urllib2, sys, traceback, cgi

import common
from autotest_lib.frontend import views_common
from autotest_lib.frontend.afe import rpc_handler
from autotest_lib.frontend.planner import models, rpc_interface

rpc_handler_obj = rpc_handler.RpcHandler((rpc_interface,),
                                         document_module=rpc_interface)


def handle_rpc(request):
    return rpc_handler_obj.handle_rpc_request(request)


def rpc_documentation(request):
    return rpc_handler_obj.get_rpc_documentation()


def model_documentation(request):
    model_names = ('Plan', 'Host', 'ControlFile', 'TestConfig', 'Job', 'Bug',
                   'TestRun', 'DataType', 'History', 'SavedObject', 'KeyVal',
                   'AutoProcess')
    return views_common.model_documentation(models, model_names)
