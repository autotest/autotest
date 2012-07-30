"""
oVirt SDK wrapper module.

@copyright: 2008-2012 Red Hat Inc.
"""


import time, logging

try:
    from ovirtsdk.api import API
    from ovirtsdk.xml import params as param
except ImportError:
    logging.error("ovirtsdk module isn't present, please run install.py "
                  "to build and install it")

from autotest.client.virt import virt_vm


_api = None
_connected = False


def connect(params):
    """
    Connect ovirt manager API.
    """
    url = params.get('ovirt_engine_url')
    username = params.get('ovirt_engine_user')
    password = params.get('ovirt_engine_password')
    version = params.get('ovirt_engine_version')

    if url is None or username is None or password is None:
        logging.error('ovirt_engine[url|user|password] are necessary!!')

    if version is None:
        version = param.Version(major='3', minor='0')
    else:
        version = param.Version(version)

    global _api, _connected

    try:
        # Try to connect oVirt API if connection doesn't exist,
        # otherwise, directly return existing API connection.
        if not _connected:
            _api = API(url, username, password)
            _connected = True
            return (_api, version)
        else:
            return (_api, version)
    except Exception as e:
        logging.error('Failed to connect: %s\n' % str(e))
    else:
        logging.info('Succeed to connect oVirt/Rhevm manager\n')


def disconnect():
    """
    Disconnect ovirt manager connection.
    """
    global _api, _connected

    if _connected:
        return _api.disconnect()


class VMManager(virt_vm.BaseVM):
    """
    This class handles all basic VM operations for oVirt.
    """

    def __init__(self, params, root_dir, address_cache=None, state=None):
        """
        Initialize the object and set a few attributes.

        @param name: The name of the object
        @param params: A dict containing VM params (see method
                       make_qemu_command for a full description)
        @param root_dir: Base directory for relative filenames
        @param address_cache: A dict that maps MAC addresses to IP addresses
        @param state: If provided, use this as self.__dict__
        """

        if state:
            self.__dict__ = state
        else:
            self.process = None
            self.serial_console = None
            self.redirs = {}
            self.vnc_port = 5900
            self.vnclisten = "0.0.0.0"
            self.pci_assignable = None
            self.netdev_id = []
            self.device_id = []
            self.pci_devices = []
            self.uuid = None
            self.only_pty = False

        self.spice_port = 8000
        self.name = params.get("vm_name", "")
        self.params = params
        self.root_dir = root_dir
        self.address_cache = address_cache
        self.vnclisten = "0.0.0.0"
        self.driver_type = "virt_v2v"

        super(VMManager, self).__init__(self.name, params)
        (self.api, self.version) = connect(params)

        if self.name:
            self.instance = self.api.vms.get(self.name)


    def list(self):
        """
        List all of VMs.
        """
        vm_list = []
        try:
            vms = self.api.vms.list(query='name=*')
            for i in range(len(vms)):
                vm_list.append(vms[i].name)
            return vm_list
        except Exception as e:
            logging.error('Failed to get vms:\n%s' % str(e))


    def state(self):
        """
        Return VM state.
        """
        try:
            return self.instance.status.state
        except Exception as e:
            logging.error('Failed to get %s status:\n%s' % (self.name, str(e)))


    def get_mac_address(self):
        """
        Return MAC address of a VM.
        """
        try:
            return self.instance.nics.get().get_mac().get_address()
        except Exception as e:
            logging.error('Failed to get %s status:\n%s' % (self.name, str(e)))


    def lookup_by_storagedomains(self, storage_name):
        """
        Lookup VM object in storage domain according to VM name.
        """
        try:
            storage = self.api.storagedomains.get(storage_name)
            return storage.vms.get(self.name)
        except Exception as e:
            logging.error('Failed to get %s from %s:\n%s' % (self.name,
                          storage_name, str(e)))


    def is_alive(self):
        """
        Judge if a VM is alive.
        """
        if self.state() == 'up':
            logging.info('The %s status is <Up>' % self.name)
            return True
        else:
            logging.debug('The %s status is <not Up>' % self.name)
            return False


    def is_dead(self):
        """
        Judge if a VM is dead.
        """
        if self.state() == 'down':
            logging.info('The %s status is <Down>' % self.name)
            return True
        else:
            logging.debug('The %s status is <not Down>' % self.name)
            return False


    def start(self):
        """
        Start a VM.
        """
        try:
            if self.state() != 'up':
                logging.info('Starting VM %s' % self.name)
                self.instance.start()
                logging.info('Waiting for VM to reach <Up> status ...')
                while self.state() != 'up':
                    self.instance = self.api.vms.get(self.name)
                    time.sleep(1)
            else:
                logging.debug('VM already up')
        except Exception as e:
            logging.error('Failed to start VM:\n%s' % str(e))


    def suspend(self):
        """
        Suspend a VM.
        """
        while self.state() != 'suspended':
            try:
                logging.info('Suspend VM %s' % self.name)
                self.instance.suspend()
                logging.info('Waiting for VM to reach <Suspended> status ...')
                while self.state() != 'suspended':
                    self.instance = self.api.vms.get(self.name)
                    time.sleep(1)

            except Exception as e:
                if e.reason == 'Bad Request' \
                    and 'asynchronous running tasks' in e.detail:
                    logging.warning("VM has asynchronous running tasks, "
                                    "trying again")
                    time.sleep(1)
                else:
                    logging.error('Failed to suspend VM:\n%s' % str(e))
                    break


    def resume(self):
        """
        Resume a suspended VM.
        """
        try:
            if self.state() != 'up':
                logging.info('Resume VM %s' % self.name)
                self.instance.start()
                logging.info('Waiting for VM to <Resume> status ...')
                while self.state() != 'up':
                    self.instance = self.api.vms.get(self.name)
                    time.sleep(1)
            else:
                logging.debug('VM already up')
        except Exception as e:
            logging.error('Failed to resume VM:\n%s' % str(e))


    def shutdown(self):
        """
        Shut down a running VM.
        """
        try:
            if self.state() != 'down':
                logging.info('Stop VM %s' % self.name)
                self.instance.stop()
                logging.info('Waiting for VM to reach <Down> status ...')
                while self.state() != 'down':
                    self.instance = self.api.vms.get(self.name)
                    time.sleep(1)
            else:
                logging.debug('VM already down')
        except Exception as e:
            logging.error('Failed to Stop VM:\n%s' % str(e))


    def delete(self):
        """
        Delete a VM.
        """
        try:
            if self.state() == 'down':
                logging.info('Delete VM %s' % self.name)
                self.instance.delete()
                logging.info('Waiting for VM to be <Deleted> ...')
                while self.name in [self.instance.name for self.instance \
                                    in self.api.vms.list()]:
                    time.sleep(1)
                logging.info('VM was removed successfully')
            else:
                logging.debug('VM already is down status')
        except Exception as e:
            logging.error('Failed to remove VM:\n%s' % str(e))


    def destroy(self):
        """
        Destroy a VM.
        """
        if self.api.vms is None:
            return

        self.shutdown()


    def delete_from_export_domain(self, export_name):
        """
        Remove a VM from specified export domain.

        @export_name: export domain name.
        """
        vm = self.lookup_by_storagedomains(export_name)
        try:
            vm.delete()
        except Exception as e:
            logging.error('Failed to remove VM:\n%s' % str(e))


    def import_from_export_domain(self, export_name, storage_name,
                                  cluster_name):
        """
        Import a VM from export domain to data domain.

        @export_name: Export domain name.
        @storage_name: Storage domain name.
        @cluster_name: Cluster name.
        """
        vm = self.lookup_by_storagedomains(export_name)
        storage_domains = self.api.storagedomains.get(storage_name)
        clusters = self.api.clusters.get(cluster_name)
        try:
            logging.info('Import VM %s' % self.name)
            vm.import_vm(param.Action(storage_domain=storage_domains,
                                      cluster=clusters))
            logging.info('Waiting for VM to reach <Down> status ...')
            while self.state() != 'down':
                self.instance = self.api.vms.get(self.name)
                time.sleep(1)
            logging.info('VM was imported successfully')
        except Exception as e:
            logging.error('Failed to import VM:\n%s' % str(e))


    def export_from_export_domain(self, export_name):
        """
        Export a VM from storage domain to export domain.

        @export_name: Export domain name.
        """
        storage_domains = self.api.storagedomains.get(export_name)
        try:
            logging.info('Export VM %s' % self.name)
            self.instance.export(param.Action(storage_domain=storage_domains))
            logging.info('Waiting for VM to reach <Down> status ...')
            while self.state() != 'down':
                self.instance = self.api.vms.get(self.name)
                time.sleep(1)
            logging.info('VM was exported successfully')
        except Exception as e:
            logging.error('Failed to export VM:\n%s' % str(e))


    def snapshot(self, snapshot_name='my_snapshot'):
        """
        Create a snapshot to VM.

        @snapshot_name: 'my_snapshot' is default snapshot name.
        """
        snap_params = param.Snapshot(description=snapshot_name,
                                     vm=self.instance)
        try:
            logging.info('Creating a snapshot %s for VM %s'
                         % (snapshot_name, self.name))
            self.instance.snapshots.add(snap_params)
            logging.info('Waiting for snapshot creation to finish ...')
            while self.state() == 'image_locked':
                self.instance = self.api.vms.get(self.name)
                time.sleep(1)
            logging.info('Snapshot was created successfully')
        except Exception as e:
            logging.error('Failed to create a snapshot:\n%s' % str(e))


    def create_template(self, cluster_name, template_name='my_template'):
        """
        Create a template from VM.

        @cluster_name: cluster name.
        @template_name: 'my_template' is default template name.
        """
        cluster = self.api.clusters.get(cluster_name)

        tmpl_params = param.Template(name=template_name,
                                     vm=self.instance,
                                     cluster=cluster)
        try:
            logging.info('Creating a template %s from VM %s'
                         % (template_name, self.name))
            self.api.templates.add(tmpl_params)
            logging.info('Waiting for VM to reach <Down> status ...')
            while self.state() != 'down':
                self.instance = self.api.vms.get(self.name)
                time.sleep(1)
        except Exception as e:
            logging.error('Failed to create a template from VM:\n%s' % str(e))


    def add(self, memory, disk_size, cluster_name, storage_name,
               nic_name='eth0', network_interface='virtio',
               network_name='ovirtmgmt', disk_interface='virtio',
               disk_format='raw', template_name='Blank'):
        """
        Create VM with one NIC and one Disk.

        @memory: VM's memory size such as 1024*1024*1024=1GB.
        @disk_size: VM's disk size such as 512*1024=512MB.
        @nic_name: VM's NICs name such as 'eth0'.
        @network_interface: VM's network interface such as 'virtio'.
        @network_name: network such as ovirtmgmt for ovirt, rhevm for rhel.
        @disk_format: VM's disk format such as 'raw' or 'cow'.
        @disk_interface: VM's disk interface such as 'virtio'.
        @cluster_name: cluster name.
        @storage_name: storage domain name.
        @template_name: VM's template name, default is 'Blank'.
        """
        # network name is ovirtmgmt for ovirt, rhevm for rhel.
        vm_params = param.VM(name=self.name, memory=memory,
                             cluster=self.api.clusters.get(cluster_name),
                             template=self.api.templates.get(template_name))

        storage = self.api.storagedomains.get(storage_name)

        storage_params = param.StorageDomains(storage_domain=[storage])

        nic_params = param.NIC(name=nic_name,
                               network=param.Network(name=network_name),
                               interface=network_interface)

        disk_params = param.Disk(storage_domains=storage_params,
                                 size=disk_size,
                                 type_='system',
                                 status=None,
                                 interface=disk_interface,
                                 format=disk_format,
                                 sparse=True,
                                 bootable=True)

        try:
            logging.info('Creating a VM %s' % self.name)
            self.api.vms.add(vm_params)

            logging.info('NIC is added to VM %s' % self.name)
            self.instance.nics.add(nic_params)

            logging.info('Disk is added to VM %s' % self.name)
            self.instance.disks.add(disk_params)

            logging.info('Waiting for VM to reach <Down> status ...')
            while self.state() != 'down':
                time.sleep(1)

        except Exception as e:
            logging.error('Failed to create VM with disk and NIC\n%s' % str(e))


    def add_vm_from_template(self, cluster_name, template_name='Blank',
                             new_name='my_new_vm'):
        """
        Create a VM from template.

        @cluster_name: cluster name.
        @template_name: default template is 'Blank'.
        @new_name: 'my_new_vm' is a default new VM's name.
        """
        vm_params = param.VM(name=new_name,
                             cluster=self.api.clusters.get(cluster_name),
                             template=self.api.templates.get(template_name))
        try:
            logging.info('Creating a VM %s from template %s'
                         % (new_name, template_name))
            self.api.vms.add(vm_params)
            logging.info('Waiting for VM to reach <Down> status ...')
            while self.state() != 'down':
                self.instance = self.api.vms.get(self.name)
                time.sleep(1)
            logging.info('VM was created from template successfully')
        except Exception as e:
            logging.error('Failed to create VM from template:\n%s' % str(e))


    def get_address(self, index=0):
        """
        Return the address of the guest through ovirt node tcpdump cache.

        @param index: Name or index of the NIC whose address is requested.
        @return: IP address of NIC.
        @raise VMIPAddressMissingError: If no IP address is found for the the
                NIC's MAC address
        """
        nic = self.virtnet[index]
        if nic.nettype == 'bridge':
            mac = self.get_mac_address()
            ip = self.address_cache.get(mac)
            # TODO: Verify MAC-IP address mapping on remote ovirt node
            if not ip:
                raise virt_vm.VMIPAddressMissingError(mac)
            return ip
        else:
            raise ValueError("Ovirt only support bridge nettype now.")


class DataCenterManager(object):
    """
    This class handles all basic datacenter operations.
    """

    def __init__(self, params):
        self.name = params.get("dc_name", "")
        self.params = params
        (self.api, self.version) = connect(params)

        if self.name:
            self.instance = self.api.datacenters.get(self.name)


    def list(self):
        """
        List all of datacenters.
        """
        dc_list = []
        try:
            logging.info('List Data centers')
            dcs = self.api.datacenters.list(query='name=*')
            for i in range(len(dcs)):
                dc_list.append(dcs[i].name)
            return dc_list
        except Exception as e:
            logging.error('Failed to get data centers:\n%s' % str(e))


    def add(self, storage_type):
        """
        Add a new data center.
        """
        if not self.name:
            self.name = "my_datacenter"
        try:
            logging.info('Creating a %s type datacenter %s'
                         % (storage_type, self.name))
            if self.api.datacenters.add(param.DataCenter(
                name=self.name,
                storage_type=storage_type,
                version=self.version)):
                logging.info('Data center was created successfully')
        except Exception as e:
            logging.error('Failed to create data center:\n%s' % str(e))


class ClusterManager(object):
    """
    This class handles all basic cluster operations.
    """

    def __init__(self, params):
        self.name = params.get("cluster_name", "")
        self.params = params
        (self.api, self.version) = connect(params)

        if self.name:
            self.instance = self.api.clusters.get(self.name)


    def list(self):
        """
        List all of clusters.
        """
        cluster_list = []
        try:
            logging.info('List clusters')
            clusters = self.api.clusters.list(query='name=*')
            for i in range(len(clusters)):
                cluster_list.append(clusters[i].name)
            return cluster_list
        except Exception as e:
            logging.error('Failed to get clusters:\n%s' % str(e))


    def add(self, dc_name, cpu_type='Intel Nehalem Family'):
        """
        Add a new cluster into data center.
        """
        if not self.name:
            self.name = "my_cluster"

        dc = self.api.datacenters.get(dc_name)
        try:
            logging.info('Creating a cluster %s in datacenter %s'
                         % (cluster_name, dc_name))
            if self.api.clusters.add(param.Cluster(name=self.name,
                                                   cpu=param.CPU(id=cpu_type),
                                                   data_center=dc,
                                                   version=self.version)):
                logging.info('Cluster was created successfully')
        except Exception as e:
            logging.error('Failed to create cluster:\n%s' % str(e))


class HostManager(object):
    """
    This class handles all basic host operations.
    """

    def __init__(self, params):
        self.name = params.get("hostname", "")
        self.params = params
        (self.api, self.version) = connect(params)

        if self.name:
            self.instance = self.api.hosts.get(self.name)


    def list(self):
        """
        List all of hosts.
        """
        host_list = []
        try:
            logging.info('List hosts')
            hosts = self.api.hosts.list(query='name=*')
            for i in range(len(hosts)):
                host_list.append(hosts[i].name)
            return host_list
        except Exception as e:
            logging.error('Failed to get hosts:\n%s' % str(e))


    def state(self):
        """
        Return host state.
        """
        try:
            return self.instance.status.state
        except Exception as e:
            logging.error('Failed to get %s status:\n%s' % (self.name, str(e)))


    def add(self, host_address, host_password, cluster_name):
        """
        Register a host into specified cluster.
        """
        if not self.name:
            self.name = 'my_host'

        clusters = self.api.clusters.get(cluster_name)
        host_params = param.Host(name=self.name, address=host_address,
                                 cluster=clusters, root_password=host_password)
        try:
            logging.info('Registing a host %s into cluster %s'
                         % (self.name, cluster_name))
            if self.api.hosts.add(host_params):
                logging.info('Waiting for host to reach the <Up> status ...')
                while self.state() != 'up':
                    time.sleep(1)
                else:
                    logging.info('Host is up')
                logging.info('Host was installed successfully')
        except Exception as e:
            logging.error('Failed to install host:\n%s' % str(e))


    def get_address(self):
        """
        Return host IP address.
        """
        try:
            logging.info('Get host %s IP' % self.name)
            return self.instance.get_address()
        except Exception as e:
            logging.error('Failed to get host %s IP address:\n%s' %
                         (self.name, str(e)))


class StorageDomainManager(object):
    """
    This class handles all basic storage domain operations.
    """

    def __init__(self, params):
        self.name = params.get("storage_name", "")
        self.params = params
        (self.api, self.version) = connect(params)

        if self.name:
            self.instance = self.api.storagedomains.get(self.name)


    def list(self):
        """
        List all of storagedomains.
        """
        storage_list = []
        try:
            logging.info('List storage domains')
            storages = self.api.storagedomains.list()
            for i in range(len(storages)):
                storage_list.append(storages[i].name)
            return storage_list
        except Exception as e:
            logging.error('Failed to get storage domains:\n%s' % str(e))


    def attach_iso_export_domain_into_datacenter(self, address, path,
                                                 dc_name, host_name,
                                                 domain_type,
                                                 storage_type='nfs',
                                                 name='my_iso'):
        """
        Attach ISO/export domain into data center.

        @name: ISO or Export name.
        @host_name: host name.
        @dc_name: data center name.
        @path: ISO/export domain path.
        @address: ISO/export domain address.
        @domain_type: storage domain type, it may be 'iso' or 'export'.
        @storage_type: storage type, it may be 'nfs', 'iscsi', or 'fc'.
        """
        dc = self.api.datacenters.get(dc_name)
        host = self.api.hosts.get(host_name)
        storage_params = param.Storage(type_=storage_type,
                                       address=address,
                                       path=path)

        storage_domain__params = param.StorageDomain(name=name,
                                                     data_center=dc,
                                                     type_=domain_type,
                                                     host=host,
                                                     storage = storage_params)

        try:
            logging.info('Create/import ISO storage domain %s' % name)
            if self.api.storagedomains.add(storage_domain__params):
                logging.info('%s domain was created/imported successfully'
                             % domain_type)

            logging.info('Attach ISO storage domain %s' % name)
            if self.api.datacenters.get(dc_name).storagedomains.add(
                self.api.storagedomains.get(name)):
                logging.info('%s domain was attached successfully'
                             % domain_type)

            logging.info('Activate ISO storage domain %s' % name)
            if self.api.datacenters.get(dc_name).storagedomains.get(
                name).activate():
                logging.info('%s domain was activated successfully'
                             % domain_type)
        except Exception as e:
            logging.error('Failed to add %s domain:\n%s'
                          % (domain_type, str(e)))
