from new_tko.tko import rpc_interface
from autotest_lib.frontend.afe import rpc_handler

rpc_handler_obj = rpc_handler.RpcHandler((rpc_interface,),
                                         document_module=rpc_interface)


def handle_rpc(request):
    return rpc_handler_obj.handle_rpc_request(request)
