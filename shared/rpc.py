'''
Basic definitions for the rpc services.
'''

import frontend

__all__ = ['DEFAULT_PATH',
           'AFE_PATH',
           'TKO_PATH',
           'PATHS']

#: RPC path to use for unknown service
DEFAULT_PATH = '/'

#: RPC path for the AFE service
AFE_PATH = "%srpc/" % frontend.AFE_URL_PREFIX

#: RPC path for the TKO service
TKO_PATH = "%srpc/" % frontend.TKO_URL_PREFIX

#: The service available on a regular Autotest RPC server and their RPC PATHS
PATHS = {frontend.AFE_SERVICE_NAME: AFE_PATH,
         frontend.TKO_SERVICE_NAME: TKO_PATH}
