import cgi
import sys
import traceback

import httplib2
from autotest.client.shared import utils
from autotest.frontend import views_common
from autotest.frontend.afe import models, rpc_handler, rpc_interface
from django.http import HttpResponse, HttpResponsePermanentRedirect
from django.http import HttpResponseServerError
from django.template import Context, loader

site_rpc_interface = utils.import_site_module(
    __file__, 'autotest.frontend.afe.site_rpc_interface',
    dummy=object())

# since site_rpc_interface is later in the list, its methods will override those
# of rpc_interface
rpc_handler_obj = rpc_handler.RpcHandler((rpc_interface, site_rpc_interface),
                                         document_module=rpc_interface)


def handle_rpc(request):
    return rpc_handler_obj.handle_rpc_request(request)


def rpc_documentation(request):
    return rpc_handler_obj.get_rpc_documentation()


def model_documentation(request):
    model_names = ('Label', 'Host', 'Test', 'User', 'AclGroup', 'Job',
                   'AtomicGroup')
    return views_common.model_documentation(models, model_names)


def redirect_with_extra_data(request, url, **kwargs):
    kwargs['getdata'] = request.GET.urlencode()
    kwargs['server_name'] = request.META['SERVER_NAME']
    return HttpResponsePermanentRedirect(url % kwargs)


GWT_SERVER = 'http://localhost:8888/'


def gwt_forward(request, forward_addr):
    url = GWT_SERVER + forward_addr
    if len(request.POST) == 0:
        headers, content = httplib2.Http().request(url, 'GET')
    else:
        headers, content = httplib2.Http().request(url, 'POST',
                                                   body=request.raw_post_data)
    http_response = HttpResponse(content)
    for header, value in headers.items():
        # remove components that could cause hop-by-hop errors
        if header not in ('connection', 'keep-alive', 'proxy-authenticate',
                          'proxy-authorization', 'te', 'trailers',
                          'transfer-encoding', 'upgrade',):
            http_response[header] = value
    return http_response


def handler500(request):
    t = loader.get_template('500.html')
    trace = traceback.format_exc()
    context = Context({
        'type': sys.exc_type,
        'value': sys.exc_value,
        'traceback': cgi.escape(trace)
    })
    return HttpResponseServerError(t.render(context))
