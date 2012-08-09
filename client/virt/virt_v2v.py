"""
Utility functions to handle Virtual Machine conversion using virt-v2v.

@copyright: 2008-2012 Red Hat Inc.
"""

import logging

from autotest.client import os_dep, utils
from autotest.client.shared import ssh_key
from autotest.client.virt import virt_v2v_utils as v2v_utils

DEBUG = False

try:
    V2V_EXEC = os_dep.command('virt-v2v')
except ValueError:
    V2V_EXEC = None


def v2v_cmd(params):
    """
    Append cmd to 'virt-v2v' and execute, optionally return full results.

    @param: params: A dictionary includes all of required parameters such as
                    'target', 'hypervisor' and 'hostname', etc.
    @return: stdout of command
    """
    if V2V_EXEC is None:
        raise ValueError('Missing command: virt-v2v')

    target = params.get('target')
    hypervisor = params.get('hypervisor')
    hostname = params.get('hostname')
    username = params.get('username')
    password = params.get('password')

    uri_obj = v2v_utils.Uri(hypervisor)
    # Return actual 'uri' according to 'hostname' and 'hypervisor'
    uri = uri_obj.get_uri(hostname)

    tgt_obj = v2v_utils.Target(target, uri)
    # Return virt-v2v command line options based on 'target' and 'hypervisor'
    options = tgt_obj.get_cmd_options(params)

    # Convert a existing VM without or with connection authorization.
    if hypervisor == 'esx':
        v2v_utils.build_esx_no_verify(params)
    elif hypervisor == 'xen' or hypervisor == 'kvm':
        # Setup ssh key for build connection without password.
        ssh_key.setup_ssh_key(hostname, user=username, port=22,
                              password=password)
    else:
        pass

    # Construct a final virt-v2v command
    cmd = '%s %s' % (V2V_EXEC, options)
    logging.debug('%s' % cmd)
    cmd_result = utils.run(cmd, verbose=DEBUG)
    return cmd_result
