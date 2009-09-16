import django.http
from autotest_lib.new_tko.tko import rpc_interface, graphing_utils, csv_encoder
from autotest_lib.frontend.afe import rpc_handler, rpc_utils

rpc_handler_obj = rpc_handler.RpcHandler((rpc_interface,),
                                         document_module=rpc_interface)

def handle_rpc(request):
    return rpc_handler_obj.handle_rpc_request(request)


def handle_jsonp_rpc(request):
    return rpc_handler_obj.handle_jsonp_rpc_request(request)


def handle_csv(request):
    request_data = rpc_handler_obj.raw_request_data(request)
    decoded_request = rpc_handler_obj.decode_request(request_data)
    result = rpc_handler_obj.dispatch_request(decoded_request)['result']
    encoder = csv_encoder.encoder(decoded_request, result)
    return encoder.encode()


def rpc_documentation(request):
    return rpc_handler_obj.get_rpc_documentation()


def handle_plot(request):
    id = request.GET['id']
    max_age = request.GET['max_age']
    return django.http.HttpResponse(
        graphing_utils.handle_plot_request(id, max_age), mimetype='image/png')
