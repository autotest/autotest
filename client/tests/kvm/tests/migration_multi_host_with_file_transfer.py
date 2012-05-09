import logging, threading
from autotest.client.virt import virt_utils
from autotest.client import utils as client_utils
from autotest.client.shared import utils, error
from autotest.client.shared.syncdata import SyncData
from autotest.client.virt import virt_env_process

@error.context_aware
def run_migration_multi_host_with_file_transfer(test, params, env):
    """
    KVM multi-host migration test:

    Migration execution progress is described in documentation
    for migrate method in class MultihostMigration.

    This test starts vm on master host. When vm is started then it starts file
    transfer between vm and master host:
          work:                             migration:
       host1->vm                        mig_1(host1->host2)
       vm->host1
       checksum file
       host1->vm
       vm->host1                        mig_2(host2<-host1)
       checksum file
       host1->vm
       vm->host1
       checksum file                    mig_3(host1<-host2)
           ...                                 ...
           ...                                 ...
           ...                                 ...
       host1->vm                               ...
       vm->host1                               ...
       checksum file                    mig_migrate_count(host2<-host1)

     end:
       check all checksum with orig_file checksum

    @param test: Kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    @param cfg:
        file_size: Size of generated file.
        transfer_timeout: Timeout for file transfer.
        transfer_speed: File transfer speed limit.
        guest_path: Path where file is stored on guest.
    """
    guest_root = params.get("guest_root", "root")
    guest_pass = params.get("password", "123456")

    shell_client = params.get("shell_client", "ssh")
    shell_port = int(params.get("shell_port", "22"))
    shell_prompt = params.get("shell_prompt")

    #Path where file is stored on guest.
    guest_path = params.get("guest_path", "/tmp/file")
    #Path where file is generated.
    host_path = "/tmp/file-%s" % virt_utils.generate_random_string(6)
    #Path on host for file copied from vm.
    host_path_returned = "%s-returned" % host_path
    file_size = params.get("file_size", "500")
    transfer_timeout = int(params.get("transfer_timeout", "240"))
    transfer_speed = int(params.get("transfer_speed", "100")) * 1000
    d_transfer_timeout = 2 * transfer_timeout

    #Count of migration during file transfer.
    migrate_count = int(params.get("migrate_count", "3"))

    class TestMultihostMigration(virt_utils.MultihostMigration):
        def __init__(self, test, params, env):
            super(TestMultihostMigration, self).__init__(test, params, env)
            self.vm = None
            self.vm_addr = None
            self.srchost = self.params.get("hosts")[0]
            self.dsthost = self.params.get("hosts")[1]
            self.slave = self.dsthost
            self.id = {'src': self.srchost,
                       'dst': self.dsthost,
                       "type": "file_trasfer"}
            self.file_check_sums = []

        def check_vms(self, mig_data):
            """
            Check vms after migrate.

            @param mig_data: object with migration data.
            """
            for vm in mig_data.vms:
                if not virt_utils.guest_active(vm):
                    raise error.TestFail("Guest not active after migration")

            logging.info("Migrated guest appears to be running")

            logging.info("Logging into migrated guest after migration...")
            for vm in mig_data.vms:
                vm.wait_for_login(timeout=self.login_timeout)

        def _prepare_vm(self, vm_name):
            """
            Prepare, start vm and return vm.

            @param vm_name: Class with data necessary for migration.

            @return: Started VM.
            """
            new_params = self.params.copy()

            new_params['migration_mode'] = None
            new_params['start_vm'] = 'yes'
            self.vm_lock.acquire()
            virt_env_process.process(self.test, new_params, self.env,
                                     virt_env_process.preprocess_image,
                                     virt_env_process.preprocess_vm)
            self.vm_lock.release()
            vm = self.env.get_vm(vm_name)
            vm.wait_for_login(timeout=self.login_timeout)
            return vm

        def _copy_until_end(self, end_event):
            #Copy until migration not end.
            while not end_event.isSet():
                logging.info("Copy file to guest %s.", self.vm_addr)
                virt_utils.copy_files_to(self.vm_addr, "scp", guest_root,
                                         guest_pass, 22, host_path,
                                         guest_path, limit=transfer_speed,
                                         verbose=True,
                                         timeout=transfer_timeout)
                logging.info("Copy file to guests %s done.", self.vm_addr)

                logging.info("Copy file from guest %s.", self.vm_addr)
                virt_utils.copy_files_from(self.vm_addr, "scp", guest_root,
                                           guest_pass, 22, guest_path,
                                           host_path_returned,
                                           limit=transfer_speed, verbose=True,
                                           timeout=transfer_timeout)
                logging.info("Copy file from guests %s done.", self.vm_addr)
                check_sum = client_utils.hash_file(host_path_returned)
                #store checksum for later check.
                self.file_check_sums.append(check_sum)

        def _run_and_migrate(self, bg, end_event, sync, migrate_count):
                bg.start()
                try:
                    while bg.isAlive():
                        logging.info("File transfer not ended, starting"
                                     " a round of migration...")
                        sync.sync(True, timeout=d_transfer_timeout)
                        self.migrate_wait([self.vm],
                                          self.srchost,
                                          self.dsthost)
                        tmp = self.dsthost
                        self.dsthost = self.srchost
                        self.srchost = tmp
                        migrate_count -= 1
                        if (migrate_count <= 0):
                            end_event.set()
                            bg.join()

                    sync.sync(False, timeout=d_transfer_timeout)
                except Exception:
                    # If something bad happened in the main thread, ignore
                    # exceptions raised in the background thread
                    bg.join(suppress_exception=True)
                    raise
                else:
                    bg.join()

        def _slave_migrate(self, sync):
            while True:
                done = sync.sync(timeout=d_transfer_timeout)[self.master_id()]
                if not done:
                    break
                logging.info("File transfer not ended, starting"
                             " a round of migration...")
                self.migrate_wait([self.vm],
                                  self.srchost,
                                  self.dsthost)

                tmp = self.dsthost
                self.dsthost = self.srchost
                self.srchost = tmp

        def migration_scenario(self):
            sync = SyncData(self.master_id(), self.hostid, self.hosts,
                            self.id, self.sync_server)
            self.vm = params.get("vms").split()[0]
            address_cache = env.get("address_cache")

            if (self.hostid == self.master_id()):
                utils.run("dd if=/dev/urandom of=%s bs=1M"
                          " count=%s" % (host_path, file_size))

                self.vm_addr = self._prepare_vm(self.vm).get_address()

                end_event = threading.Event()
                bg = utils.InterruptedThread(self._copy_until_end,
                                             (end_event,))

                self._hosts_barrier(self.hosts, self.id, "befor_mig", 120)
                sync.sync(address_cache, timeout=120)
                error.context("ping-pong between host and guest while"
                              " migrating", logging.info)
                self._run_and_migrate(bg, end_event, sync, migrate_count)

                #Check if guest lives.
                virt_utils.wait_for_login(shell_client, self.vm_addr,
                                          shell_port, guest_root,
                                          guest_pass, shell_prompt)
                self._hosts_barrier(self.hosts, self.id, "After_check", 120)

                error.context("comparing hashes", logging.info)
                orig_hash = client_utils.hash_file(host_path)
                returned_hash = client_utils.hash_file(host_path_returned)

                #Check all check sum
                wrong_check_sum = False
                for i in range(len(self.file_check_sums)):
                    check_sum = self.file_check_sums[i]
                    if check_sum != orig_hash:
                        wrong_check_sum = True
                        logging.error("Checksum in transfer number"
                                      " %d if wrong." % (i))
                if wrong_check_sum:
                    raise error.TestFail("Returned file hash (%s) differs from"
                                         " original one (%s)" % (returned_hash,
                                                                 orig_hash))
                else:
                    #clean temp
                    utils.run("rm -rf %s" % (host_path))
                    utils.run("rm -rf %s" % (returned_hash))

                error.context()
            else:
                self._hosts_barrier(self.hosts, self.id, "befor_mig", 260)
                address_cache.update(sync.sync(timeout=120)[self.master_id()])
                logging.debug("Address cache updated to %s" % address_cache)
                self._slave_migrate(sync)

                #Wait for check if guest lives.
                self._hosts_barrier(self.hosts, self.id, "After_check", 120)

    mig = TestMultihostMigration(test, params, env)
    mig.run()
