import logging, socket, time, errno, os, fcntl
from autotest.client.virt import virt_test_utils, virt_utils
from autotest.client.shared.syncdata import SyncData

def run_migration_multi_host_fd(test, params, env):
    """
    KVM multi-host migration over fd test:

    Migrate machine over socket's fd. Migration execution progress is
    described in documentation for migrate method in class MultihostMigration.
    This test allows migrate only one machine at once.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    class TestMultihostMigrationFd(virt_test_utils.MultihostMigration):
        def __init__(self, test, params, env):
            super(TestMultihostMigrationFd, self).__init__(test, params, env)

        def migrate_vms_src(self, mig_data):
            """
            Migrate vms source.

            @param mig_Data: Data for migration.

            For change way how machine migrates is necessary
            re implement this method.
            """
            logging.info("Start migrating now...")
            vm = mig_data.vms[0]
            vm.migrate(dest_host=mig_data.dst,
                       protocol="fd",
                       fd_src=mig_data.params['migration_fd'])

        def _check_vms_source(self, mig_data):
            for vm in mig_data.vms:
                vm.wait_for_login(timeout=self.login_timeout)
            self._hosts_barrier(mig_data.hosts, mig_data.mig_id,
                                'prepare_VMS', 60)

        def _check_vms_dest(self, mig_data):
            self._hosts_barrier(mig_data.hosts, mig_data.mig_id,
                                 'prepare_VMS', 120)
            os.close(mig_data.params['migration_fd'])

        def _connect_to_server(self, host, port, timeout=60):
            """
            Connect to network server.
            """
            endtime = time.time() + timeout
            sock = None
            while endtime > time.time():
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    sock.connect((host, port))
                    break
                except socket.error, err:
                    (code, _) = err
                    if (code != errno.ECONNREFUSED):
                        raise
                    time.sleep(1)

            return sock

        def _create_server(self, port, timeout=60):
            """
            Create network server.
            """
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(timeout)
            sock.bind(('', port))
            sock.listen(1)
            return sock

        def migration_scenario(self):
            srchost = self.params.get("hosts")[0]
            dsthost = self.params.get("hosts")[1]
            mig_port = None

            if params.get("hostid") == self.master_id():
                mig_port = virt_utils.find_free_port(5200, 6000)

            sync = SyncData(self.master_id(), self.hostid,
                             self.params.get("hosts"),
                             {'src': srchost, 'dst': dsthost,
                              'port': "ports"}, self.sync_server)
            mig_port = sync.sync(mig_port, timeout=120)
            mig_port = mig_port[srchost]
            logging.debug("Migration port %d" % (mig_port))

            if params.get("hostid") != self.master_id():
                s = self._connect_to_server(srchost, mig_port)
                try:
                    fd = s.fileno()
                    logging.debug("File descrtiptor %d used for"
                                  " migration." % (fd))

                    self.migrate_wait(["vm1"], srchost, dsthost, mig_mode="fd",
                                      params_append={"migration_fd": fd})
                finally:
                    s.close()
            else:
                s = self._create_server(mig_port)
                try:
                    conn, _ = s.accept()
                    fd = conn.fileno()
                    logging.debug("File descrtiptor %d used for"
                                  " migration." % (fd))

                    #Prohibits descriptor inheritance.
                    flags = fcntl.fcntl(fd, fcntl.F_GETFD)
                    flags |= fcntl.FD_CLOEXEC
                    fcntl.fcntl(fd, fcntl.F_SETFD, flags)

                    self.migrate_wait(["vm1"], srchost, dsthost, mig_mode="fd",
                                      params_append={"migration_fd": fd})
                    conn.close()
                finally:
                    s.close()

    mig = TestMultihostMigrationFd(test, params, env)
    mig.run()
