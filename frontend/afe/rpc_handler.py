"""\
RPC request handler Django.  Exposed RPC interface functions should be
defined in rpc_interface.py.
"""

__author__ = 'showard@google.com (Steve Howard)'

import django.http
import traceback, pydoc

from frontend.afe.json_rpc import serviceHandler
from frontend.afe import rpc_utils


class RpcMethodHolder(object):
    'Dummy class to hold RPC interface methods as attributes.'


class RpcHandler(object):
    def __init__(self, rpc_interface_modules, document_module=None):
        self._rpc_methods = RpcMethodHolder()
        self._dispatcher = serviceHandler.ServiceHandler(
            self._rpc_methods)

        # store all methods from interface modules
        for module in rpc_interface_modules:
            self._grab_methods_from(module)

        # get documentation for rpc_interface we can send back to the
        # user
        if document_module is None:
            document_module = rpc_interface_modules[0]
        self.html_doc = pydoc.html.document(document_module)


    def handle_rpc_request(self, request):
        response = django.http.HttpResponse()
        if len(request.POST):
            response.write(self._dispatcher.handleRequest(
                request.raw_post_data))
        else:
            response.write(self.html_doc)

        response['Content-length'] = str(len(response.content))
        return response


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
            decorated_function = (
                RpcHandler._allow_keyword_args(attribute))
            setattr(self._rpc_methods, name, decorated_function)
