import django.http
from new_tko.tko import rpc_interface, graphing_utils
from autotest_lib.frontend.afe import rpc_handler

rpc_handler_obj = rpc_handler.RpcHandler((rpc_interface,),
                                         document_module=rpc_interface)


def handle_rpc(request):
    return rpc_handler_obj.handle_rpc_request(request)


def handle_plot(request):
    id = request.GET['id']
    max_age = request.GET['max_age']
    return django.http.HttpResponse(
        graphing_utils.handle_plot_request(id, max_age), mimetype='image/png')
