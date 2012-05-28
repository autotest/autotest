import os, re, logging, time, socket
from autotest.client.virt import virt_utils, kvm_monitor
from autotest.client.shared import error, utils
from autotest.client.shared.barrier import listen_server
from autotest.client.shared.syncdata import SyncData


def run_migration_multi_host_with_measure_speed(test, params, env):
    """
    KVM migration test:
    1) Get a live VM and clone it.
    2) Verify that the source VM supports migration.  If it does, proceed with
            the test.
    3) Start memory load in vm.
    4) Set defined migration speed.
    5) Send a migration command to the source VM and collecting statistic
            of migration speed.
    !) Checks that migration utilisation didn't slow down in guest stresser
       which would lead to less page-changes than required for this test.
       (migration speed is set too high for current CPU)
    6) Kill both VMs.
    7) Print statistic of migration.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    install_path = params.get("cpuflags_install_path", "/tmp")

    vm_mem = int(params.get("mem", "512"))

    get_mig_speed = re.compile("^transferred ram: (\d+) kbytes$",
                               re.MULTILINE)

    mig_speed = params.get("mig_speed", "1G")
    mig_speed_accuracy = float(params.get("mig_speed_accuracy", "0.2"))

    def get_migration_statistic(vm):
        last_transfer_mem = 0
        transfered_mem = 0
        mig_stat = utils.Statistic()
        for _ in range(30):
            o = vm.monitor.info("migrate")
            if isinstance(o, str):
                if not "status: active" in o:
                    raise error.TestWarn("Migration had already ended"
                                         " it shouldn't happen. Migration "
                                         "speed i probably too high and block "
                                         "vm in filling vm memory.")
                transfered_mem = int(get_mig_speed.search(o).groups()[0])
            else:
                if o.get("status") != "active":
                    raise error.TestWarn("Migration had already ended"
                                         " it shouldn't happen. Migration "
                                         "speed i probably too high and block "
                                         "vm in filling vm memory.")
                transfered_mem = o.get("ram").get("transferred") / (1024)

            real_mig_speed = (transfered_mem - last_transfer_mem) / 1024

            last_transfer_mem = transfered_mem

            logging.debug("Migration speeed %sMB." % (real_mig_speed))
            mig_stat.record(real_mig_speed)
            time.sleep(1)

        return mig_stat

    class TestMultihostMigration(virt_utils.MultihostMigration):
        def __init__(self, test, params, env):
            super(TestMultihostMigration, self).__init__(test, params, env)
            self.mig_stat = None
            self.srchost = self.params.get("hosts")[0]
            self.dsthost = self.params.get("hosts")[1]
            self.id = {'src': self.srchost,
                       'dst': self.dsthost,
                       "type": "file_trasfer"}
            self.link_speed = 0

        def check_vms(self, mig_data):
            """
            Check vms after migrate.

            @param mig_data: object with migration data.
            """
            pass

        def migrate_vms_src(self, mig_data):
            """
            Migrate vms source.

            @param mig_Data: Data for migration.

            For change way how machine migrates is necessary
            re implement this method.
            """
            vm = mig_data.vms[0]
            vm.migrate(dest_host=mig_data.dst,
                       remote_port=mig_data.vm_ports[vm.name],
                       not_wait_for_migration=True)
            self.mig_stat = get_migration_statistic(vm)

        def migration_scenario(self):
            sync = SyncData(self.master_id(), self.hostid, self.hosts,
                            self.id, self.sync_server)
            srchost = self.params.get("hosts")[0]
            dsthost = self.params.get("hosts")[1]
            vms = [params.get("vms").split()[0]]

            def worker(mig_data):
                vm = mig_data.vms[0]
                session = vm.wait_for_login(timeout=self.login_timeout)

                virt_utils.install_cpuflags_util_on_vm(test, vm, install_path,
                                               extra_flags="-msse3 -msse2")

                cmd = ("%s/cpuflags-test --stressmem %d" %
                    (os.path.join(install_path, "test_cpu_flags"), vm_mem / 2))
                logging.debug("Sending command: %s" % (cmd))
                session.sendline(cmd)

            if self.master_id() == self.hostid:
                server_port = virt_utils.find_free_port(5200, 6000)
                server = listen_server(port=server_port)
                data_len = 0
                sync.sync(server_port, timeout=120)
                client = server.socket.accept()[0]
                endtime = time.time() + 30
                while endtime > time.time():
                    data_len += len(client.recv(2048))
                client.close()
                server.close()
                self.link_speed = data_len / (30 * 1024 * 1024)
                logging.info("Link speed %dMB." % (self.link_speed))
                ms = utils.convert_data_size(mig_speed, 'M')
                if (ms > data_len / 30):
                    logging.warn("Migration speed %s is set faster than real"
                                 " link speed %dMB" % (mig_speed,
                                                       self.link_speed))
                else:
                    self.link_speed = ms / (1024 * 1024)
            else:
                data = ""
                for _ in range(10000):
                    data += "i"
                server_port = sync.sync(timeout=120)[self.master_id()]
                sock = socket.socket(socket.AF_INET,
                                     socket.SOCK_STREAM)
                sock.connect((self.master_id(), server_port))
                try:
                    endtime = time.time() + 10
                    while endtime > time.time():
                        sock.sendall(data)
                    sock.close()
                except:
                    pass
            self.migrate_wait(vms, srchost, dsthost, worker)

    mig = TestMultihostMigration(test, params, env)
    #Start migration
    mig.run()

    #If machine is migration master check migration statistic.
    if mig.master_id() == mig.hostid:
        mig_speed = utils.convert_data_size(mig_speed, "M")

        mig_stat = mig.mig_stat

        mig_speed = mig_speed / (1024 * 1024)
        real_speed = mig_stat.get_average()
        ack_speed = mig.link_speed * mig_speed_accuracy

        logging.info("Desired migration speed: %dMB/s." % (mig_speed))
        logging.info("Real Link speed %dMB." % (mig.link_speed))
        logging.info("Average migration speed: %d MB/s" %
                                (mig_stat.get_average()))
        logging.info("Minimal migration speed: %d MB/s" %
                                (mig_stat.get_min()))
        logging.info("Maximal migration speed: %d MB/s" %
                                (mig_stat.get_max()))

        if real_speed < mig.link_speed - ack_speed:
            raise error.TestWarn("Migration speed %sMB is slower by more"
                                 " %3.1f%% than real/desired speed %sMB" %
                         (real_speed, mig_speed_accuracy * 100, mig.link_speed))
        if real_speed > mig.link_speed + ack_speed:
            raise error.TestWarn("Migration speed %sMB is faster by more"
                                 " %3.1f%% than real/desired speed %sMB" %
                         (real_speed, mig_speed_accuracy * 100, mig.link_speed))
