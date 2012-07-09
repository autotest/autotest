import os, logging
from autotest.client.virt import virt_v2v as v2v

def get_args_dict(params):
    args_dict = {}
    keys_list = [ 'target', 'vms', 'ovirt_engine_url', 'ovirt_engine_user',
                  'ovirt_engine_password', 'hypervisor', 'hostname', 'storage',
                  'network', 'netrc', 'username', 'password' ]

    for key in keys_list:
        val = params.get(key)
        if val is None:
            raise KeyError("%s doesn't exist!!!" %key)
        else:
            args_dict[key] = val

    return args_dict


def run_convert_ovirt(test, params, env):
    """
    Test convert vm to ovirt
    """

    args_dict = get_args_dict(params)

    # Run test case
    v2v.v2v_cmd(args_dict)
