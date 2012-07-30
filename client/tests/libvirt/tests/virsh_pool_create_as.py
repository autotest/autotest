import os, logging
from autotest.client.shared import error
from autotest.client.virt import libvirt_vm as virt


def run_virsh_pool_create_as(test, params, env):
    '''
    Test the command virsh pool-create-as

    (1) Call virsh pool-create-as
    (2) Call virsh -c remote_uri pool-create-as
    (3) Call virsh pool-create-as with an unexpected option
    '''

    # Run test case
    if not params.has_key('pool_name') or not params.has_key('pool_target'):
        logging.error("Please give a 'name' and 'target'")

    pool_options = params.get('pool_options', '')

    pool_name = params.get('pool_name')
    pool_type = params.get('pool_type')
    pool_target = params.get('pool_target')

    if not os.path.isdir(pool_target):
        if os.path.isfile(pool_target):
            logging.error('<target> must be a directory')
        else:
            os.makedirs(pool_target)

    logging.info('Creating a %s type pool %s' % (pool_type, pool_name))
    status = virt.virsh_pool_create_as(pool_name, pool_type, pool_target,
                                       pool_options)

    # Check status_error
    status_error = params.get('status_error')
    if status_error == 'yes':
        if status:
            raise error.TestFail("%d not a expected command return value" % status)
        else:
            logging.info("It's an expected error")
    elif status_error == 'no':
        if not virt.virsh_pool_info(pool_name):
            raise error.TestFail('Failed to check pool information')
        else:
            logging.info('Pool %s is running' % pool_name)
        if not status:
            raise error.TestFail('%d not a expected command return value' % status)
        else:
            logging.info('Succeed to create pool %s' % pool_name)
