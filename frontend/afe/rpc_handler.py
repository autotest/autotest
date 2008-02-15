"""\
RPC request handler Django.  Exposed RPC interface functions should be
defined in rpc_interface.py.
"""

__author__ = 'showard@google.com (Steve Howard)'

import django.http
import traceback, pydoc

from frontend.afe.json_rpc import serviceHandler
from frontend.afe import rpc_interface, rpc_utils, site_rpc_interface

# since site_rpc_interface is later in the list, its methods will override those
# of rpc_interface
RPC_INTERFACE_MODULES = (rpc_interface, site_rpc_interface)

class RpcMethodHolder(object):
        'Dummy class to hold RPC interface methods as attributes.'

rpc_methods = RpcMethodHolder()

dispatcher = serviceHandler.ServiceHandler(rpc_methods)

# get documentation for rpc_interface we can send back to the user
html_doc = pydoc.html.document(rpc_interface)

def rpc_handler(request):
        rpc_utils.set_user(request.afe_user)
	response = django.http.HttpResponse()
	if len(request.POST):
		response.write(dispatcher.handleRequest(request.raw_post_data))
	else:
		response.write(html_doc)

	response['Content-length'] = str(len(response.content))
	return response


def allow_keyword_args(f):
	"""\
	Decorator to allow a function to take keyword args even though the RPC
	layer doesn't support that.  The decorated function assumes its last
	argument is a dictionary of keyword args and passes them to the original
	function as keyword args.
	"""
	def new_fn(*args):
		assert args
		keyword_args = args[-1]
		args = args[:-1]
		return f(*args, **keyword_args)
	new_fn.func_name = f.func_name
	return new_fn

# decorate all functions in rpc_interface to take keyword args
function_type = type(rpc_handler) # could be any function
for module in RPC_INTERFACE_MODULES:
	for name in dir(module):
		thing = getattr(module, name)
		if type(thing) is function_type:
			decorated_function = allow_keyword_args(thing)
			setattr(rpc_methods, name, decorated_function)
