"""\
This module provides a get_proxy() function, which should be used to access
the afe RPC server.
"""

__author__ = 'showard@google.com (Steve Howard)'

# we currently use xmlrpclib, but we modify it slightly to support keyword args
# in function calls (with corresponding support in the server)

from json_rpc import proxy

def get_proxy(*args, **kwargs):
	return proxy.ServiceProxy(*args, **kwargs)
