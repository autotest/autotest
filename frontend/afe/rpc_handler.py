"""\
RPC request handler Django.  Exposed RPC interface functions should be
defined in rpc_interface.py.
"""

__author__ = 'showard@google.com (Steve Howard)'

import traceback, pydoc, re, urllib
import django.http

from frontend.afe.json_rpc import serviceHandler
from frontend.afe import rpc_utils


class RpcMethodHolder(object):
    'Dummy class to hold RPC interface methods as attributes.'


class RpcHandler(object):
    def __init__(self, rpc_interface_modules, document_module=None):
        self._rpc_methods = RpcMethodHolder()
        self._dispatcher = serviceHandler.ServiceHandler(self._rpc_methods)

        # store all methods from interface modules
        for module in rpc_interface_modules:
            self._grab_methods_from(module)

        # get documentation for rpc_interface we can send back to the
        # user
        if document_module is None:
            document_module = rpc_interface_modules[0]
        self.html_doc = pydoc.html.document(document_module)


    def _raw_response(self, response_data, content_type=None):
        response = django.http.HttpResponse(response_data)
        response['Content-length'] = str(len(response.content))
        if content_type:
            response['Content-Type'] = content_type
        return response


    def get_rpc_documentation(self):
        return self._raw_response(self.html_doc)


    def _raw_request_data(self, request):
        if request.method == 'POST':
            return request.raw_post_data
        return urllib.unquote(request.META['QUERY_STRING'])


    def handle_rpc_request(self, request):
        request_data = self._raw_request_data(request)
        result = self._dispatcher.handleRequest(request_data)
        return self._raw_response(result)


    def handle_jsonp_rpc_request(self, request):
        request_data = request.GET['request']
        callback_name = request.GET['callback']
        # callback_name must be a simple identifier
        assert re.search(r'^\w+$', callback_name)

        result = self._dispatcher.handleRequest(request_data)
        padded_result = '%s(%s)' % (callback_name, result)
        return self._raw_response(padded_result, content_type='text/javascript')


    @staticmethod
    def _allow_keyword_args(f):
        """\
        Decorator to allow a function to take keyword args even though
        the RPC layer doesn't support that.  The decorated function
        assumes its last argument is a dictionary of keyword args and
        passes them to the original function as keyword args.
        """
        def new_fn(*args):
            assert args
            keyword_args = args[-1]
            args = args[:-1]
            return f(*args, **keyword_args)
        new_fn.func_name = f.func_name
        return new_fn


    def _grab_methods_from(self, module):
        for name in dir(module):
            attribute = getattr(module, name)
            if not callable(attribute):
                continue
            decorated_function = RpcHandler._allow_keyword_args(attribute)
            setattr(self._rpc_methods, name, decorated_function)
