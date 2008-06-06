"""\
This module provides a get_proxy() function, which should be used to access
the afe RPC server.
"""

__author__ = 'showard@google.com (Steve Howard)'

from json_rpc import proxy

def get_proxy(*args, **kwargs):
    return proxy.ServiceProxy(*args, **kwargs)
