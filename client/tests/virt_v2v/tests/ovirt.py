import os, logging
from autotest.client.virt import ovirt

def get_args_dict(params):
    args_dict = {}
    keys_list = [ 'ovirt_engine_url', 'ovirt_engine_user',
                  'ovirt_engine_password', 'vm_name', 'export_name',
                  'storage_name', 'cluster_name' ]

    for key in keys_list:
        val = params.get(key)
        if val is None:
            raise KeyError("%s doesn't exist!!!" %key)
        else:
            args_dict[key] = val

    return args_dict


def run_ovirt(test, params, env):
    """
    Test ovirt class
    """

    args_dict = get_args_dict(params)
    logging.debug("arguments dictionary: %s" %args_dict)

    vm_name  = params.get('vm_name')
    export_name  = params.get('export_name')
    storage_name  = params.get('storage_name')
    cluster_name  = params.get('cluster_name')
    address_cache = env.get('address_cache')

    # Run test case
    vm = ovirt.VMManager(params, address_cache)
    dc = ovirt.DataCenterManager(params)
    cls = ovirt.ClusterManager(params)
    ht = ovirt.HostManager(params)
    sd = ovirt.StorageDomainManager(params)

    logging.info("Current data centers list: %s" % dc.list())
    logging.info("Current cluster list: %s" % cls.list())
    logging.info("Current host list: %s" % ht.list())
    logging.info("Current storage domain list: %s" % sd.list())
    logging.info("Current vm list: %s" % vm.list())

    vm.import_from_export_domain(export_name, storage_name, cluster_name)
    logging.info("Current vm list: %s" % vm.list())

    vm.start()

    if vm.is_alive():
        logging.info("The %s is alive" % vm_name)

    vm.suspend()
    vm.resume()
    vm.shutdown()

    if vm.is_dead():
        logging.info("The %s is dead" % vm_name)

#    vm.delete()
#    logging.info("Current vm list: %s" % vm.list())
