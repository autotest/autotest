"""
High-level KVM test utility functions.

This module is meant to reduce code size by performing common test procedures.
Generally, code here should look like test code.
More specifically:
    - Functions in this module should raise exceptions if things go wrong
      (unlike functions in kvm_utils.py and kvm_vm.py which report failure via
      their returned values).
    - Functions in this module may use logging.info(), in addition to
      logging.debug() and logging.error(), to log messages the user may be
      interested in (unlike kvm_utils.py and kvm_vm.py which use
      logging.debug() for anything that isn't an error).
    - Functions in this module typically use functions and classes from
      lower-level modules (e.g. kvm_utils.py, kvm_vm.py, kvm_subprocess.py).
    - Functions in this module should not be used by lower-level modules.
    - Functions in this module should be used in the right context.
      For example, a function should not be used where it may display
      misleading or inaccurate info or debug messages.

@copyright: 2008-2009 Red Hat Inc.
"""

import time, os, logging, re, signal, imp, tempfile, commands
import threading, shelve
from Queue import Queue
from autotest.client.shared import error, global_config
from autotest.client import utils
from autotest.client.tools import scan_results
from autotest.client.shared.syncdata import SyncData, SyncListenServer
import aexpect, virt_utils, virt_vm, virt_remote, virt_storage, virt_env_process

GLOBAL_CONFIG = global_config.global_config

def get_living_vm(env, vm_name):
    """
    Get a VM object from the environment and make sure it's alive.

    @param env: Dictionary with test environment.
    @param vm_name: Name of the desired VM object.
    @return: A VM object.
    """
    vm = env.get_vm(vm_name)
    if not vm:
        raise error.TestError("VM '%s' not found in environment" % vm_name)
    if not vm.is_alive():
        raise error.TestError("VM '%s' seems to be dead; test requires a "
                              "living VM" % vm_name)
    return vm


def wait_for_login(vm, nic_index=0, timeout=240, start=0, step=2, serial=None):
    """
    Try logging into a VM repeatedly.  Stop on success or when timeout expires.

    @param vm: VM object.
    @param nic_index: Index of NIC to access in the VM.
    @param timeout: Time to wait before giving up.
    @param serial: Whether to use a serial connection instead of a remote
            (ssh, rss) one.
    @return: A shell session object.
    """
    end_time = time.time() + timeout
    session = None
    if serial:
        type = 'serial'
        logging.info("Trying to log into guest %s using serial connection,"
                     " timeout %ds", vm.name, timeout)
        time.sleep(start)
        while time.time() < end_time:
            try:
                session = vm.serial_login()
                break
            except virt_remote.LoginError, e:
                logging.debug(e)
            time.sleep(step)
    else:
        type = 'remote'
        logging.info("Trying to log into guest %s using remote connection,"
                     " timeout %ds", vm.name, timeout)
        time.sleep(start)
        while time.time() < end_time:
            try:
                session = vm.login(nic_index=nic_index)
                break
            except (virt_remote.LoginError, virt_vm.VMError), e:
                logging.debug(e)
            time.sleep(step)
    if not session:
        raise error.TestFail("Could not log into guest %s using %s connection" %
                             (vm.name, type))
    logging.info("Logged into guest %s using %s connection", vm.name, type)
    return session


def reboot(vm, session, method="shell", sleep_before_reset=10, nic_index=0,
           timeout=240):
    """
    Reboot the VM and wait for it to come back up by trying to log in until
    timeout expires.

    @param vm: VM object.
    @param session: A shell session object.
    @param method: Reboot method.  Can be "shell" (send a shell reboot
            command) or "system_reset" (send a system_reset monitor command).
    @param nic_index: Index of NIC to access in the VM, when logging in after
            rebooting.
    @param timeout: Time to wait before giving up (after rebooting).
    @return: A new shell session object.
    """
    if method == "shell":
        # Send a reboot command to the guest's shell
        session.sendline(vm.get_params().get("reboot_command"))
        logging.info("Reboot command sent. Waiting for guest to go down")
    elif method == "system_reset":
        # Sleep for a while before sending the command
        time.sleep(sleep_before_reset)
        # Clear the event list of all QMP monitors
        monitors = [m for m in vm.monitors if m.protocol == "qmp"]
        for m in monitors:
            m.clear_events()
        # Send a system_reset monitor command
        vm.monitor.cmd("system_reset")
        logging.info("Monitor command system_reset sent. Waiting for guest to "
                     "go down")
        # Look for RESET QMP events
        time.sleep(1)
        for m in monitors:
            if not m.get_event("RESET"):
                raise error.TestFail("RESET QMP event not received after "
                                     "system_reset (monitor '%s')" % m.name)
            else:
                logging.info("RESET QMP event received")
    else:
        logging.error("Unknown reboot method: %s", method)

    # Wait for the session to become unresponsive and close it
    if not virt_utils.wait_for(lambda: not session.is_responsive(timeout=30),
                              120, 0, 1):
        raise error.TestFail("Guest refuses to go down")
    session.close()

    # Try logging into the guest until timeout expires
    logging.info("Guest is down. Waiting for it to go up again, timeout %ds",
                 timeout)
    session = vm.wait_for_login(nic_index, timeout=timeout)
    logging.info("Guest is up again")
    return session


@error.context_aware
def update_boot_option(vm, args_removed=None, args_added=None,
                       need_reboot=True):
    """
    Update guest default kernel option.

    @param vm: The VM object.
    @param args_removed: Kernel options want to remove.
    @param args_added: Kernel options want to add.
    @param need_reboot: Whether need reboot VM or not.
    @raise error.TestError: Raised if fail to update guest kernel cmdlie.

    """
    if vm.params.get("os_type") == 'windows':
        # this function is only for linux, if we need to change
        # windows guest's boot option, we can use a function like:
        # update_win_bootloader(args_removed, args_added, reboot)
        # (this function is not implement.)
        # here we just:
        return

    login_timeout = int(vm.params.get("login_timeout"))
    session = vm.wait_for_login(timeout=login_timeout)

    msg = "Update guest kernel cmdline. "
    cmd = "grubby --update-kernel=`grubby --default-kernel` "
    if args_removed is not None:
        msg += " remove args: %s." % args_removed
        cmd += '--remove-args="%s." ' % args_removed
    if args_added is not None:
        msg += " add args: %s" % args_added
        cmd += '--args="%s"' % args_added
    error.context(msg, logging.info)
    s, o = session.cmd_status_output(cmd)
    if s != 0:
        logging.error(o)
        raise error.TestError("Fail to modify guest kernel cmdline")

    if need_reboot:
        error.context("Rebooting guest ...", logging.info)
        vm.reboot(session=session, timeout=login_timeout)


def migrate(vm, env=None, mig_timeout=3600, mig_protocol="tcp",
            mig_cancel=False, offline=False, stable_check=False,
            clean=False, save_path=None, dest_host='localhost', mig_port=None):
    """
    Migrate a VM locally and re-register it in the environment.

    @param vm: The VM to migrate.
    @param env: The environment dictionary.  If omitted, the migrated VM will
            not be registered.
    @param mig_timeout: timeout value for migration.
    @param mig_protocol: migration protocol
    @param mig_cancel: Test migrate_cancel or not when protocol is tcp.
    @param dest_host: Destination host (defaults to 'localhost').
    @param mig_port: Port that will be used for migration.
    @return: The post-migration VM, in case of same host migration, True in
            case of multi-host migration.
    """
    def mig_finished():
        o = vm.monitor.info("migrate")
        if isinstance(o, str):
            return "status: active" not in o
        else:
            return o.get("status") != "active"

    def mig_succeeded():
        o = vm.monitor.info("migrate")
        if isinstance(o, str):
            return "status: completed" in o
        else:
            return o.get("status") == "completed"

    def mig_failed():
        o = vm.monitor.info("migrate")
        if isinstance(o, str):
            return "status: failed" in o
        else:
            return o.get("status") == "failed"

    def mig_cancelled():
        o = vm.monitor.info("migrate")
        if isinstance(o, str):
            return ("Migration status: cancelled" in o or
                    "Migration status: canceled" in o)
        else:
            return (o.get("status") == "cancelled" or
                    o.get("status") == "canceled")

    def wait_for_migration():
        if not virt_utils.wait_for(mig_finished, mig_timeout, 2, 2,
                                  "Waiting for migration to finish"):
            raise error.TestFail("Timeout expired while waiting for migration "
                                 "to finish")

    if dest_host == 'localhost':
        dest_vm = vm.clone()

    if (dest_host == 'localhost') and stable_check:
        # Pause the dest vm after creation
        dest_vm.params['extra_params'] = (dest_vm.params.get('extra_params','')
                                          + ' -S')

    if dest_host == 'localhost':
        dest_vm.create(migration_mode=mig_protocol, mac_source=vm)

    try:
        try:
            if mig_protocol == "tcp":
                if dest_host == 'localhost':
                    uri = "tcp:0:%d" % dest_vm.migration_port
                else:
                    uri = 'tcp:%s:%d' % (dest_host, mig_port)
            elif mig_protocol == "unix":
                uri = "unix:%s" % dest_vm.migration_file
            elif mig_protocol == "exec":
                uri = '"exec:nc localhost %s"' % dest_vm.migration_port

            if offline:
                vm.pause()
            vm.monitor.migrate(uri)

            if mig_cancel:
                time.sleep(2)
                vm.monitor.cmd("migrate_cancel")
                if not virt_utils.wait_for(mig_cancelled, 60, 2, 2,
                                          "Waiting for migration "
                                          "cancellation"):
                    raise error.TestFail("Failed to cancel migration")
                if offline:
                    vm.resume()
                if dest_host == 'localhost':
                    dest_vm.destroy(gracefully=False)
                return vm
            else:
                wait_for_migration()
                if (dest_host == 'localhost') and stable_check:
                    save_path = None or "/tmp"
                    save1 = os.path.join(save_path, "src")
                    save2 = os.path.join(save_path, "dst")

                    vm.save_to_file(save1)
                    dest_vm.save_to_file(save2)

                    # Fail if we see deltas
                    md5_save1 = utils.hash_file(save1)
                    md5_save2 = utils.hash_file(save2)
                    if md5_save1 != md5_save2:
                        raise error.TestFail("Mismatch of VM state before "
                                             "and after migration")

                if (dest_host == 'localhost') and offline:
                    dest_vm.resume()
        except Exception:
            if dest_host == 'localhost':
                dest_vm.destroy()
            raise

    finally:
        if (dest_host == 'localhost') and stable_check and clean:
            logging.debug("Cleaning the state files")
            if os.path.isfile(save1):
                os.remove(save1)
            if os.path.isfile(save2):
                os.remove(save2)

    # Report migration status
    if mig_succeeded():
        logging.info("Migration finished successfully")
    elif mig_failed():
        raise error.TestFail("Migration failed")
    else:
        raise error.TestFail("Migration ended with unknown status")

    if dest_host == 'localhost':
        if dest_vm.monitor.verify_status("paused"):
            logging.debug("Destination VM is paused, resuming it")
            dest_vm.resume()

    # Kill the source VM
    vm.destroy(gracefully=False)

    # Replace the source VM with the new cloned VM
    if (dest_host == 'localhost') and (env is not None):
        env.register_vm(vm.name, dest_vm)

    # Return the new cloned VM
    if dest_host == 'localhost':
        return dest_vm
    else:
        return vm


def guest_active(vm):
    o = vm.monitor.info("status")
    if isinstance(o, str):
        return "status: running" in o
    else:
        if "status" in o:
            return o.get("status") == "running"
        else:
            return o.get("running")


class MigrationData(object):
    def __init__(self, params, srchost, dsthost, vms_name, params_append):
        """
        Class that contains data needed for one migration.
        """
        self.params = params.copy()
        self.params.update(params_append)

        self.source = False
        if params.get("hostid") == srchost:
            self.source = True

        self.destination = False
        if params.get("hostid") == dsthost:
            self.destination = True

        self.src = srchost
        self.dst = dsthost
        self.hosts = [srchost, dsthost]
        self.mig_id = {'src': srchost, 'dst': dsthost, "vms": vms_name}
        self.vms_name = vms_name
        self.vms = []
        self.vm_ports = None


    def is_src(self):
        """
        @return: True if host is source.
        """
        return self.source


    def is_dst(self):
        """
        @return: True if host is destination.
        """
        return self.destination


class MultihostMigration(object):
    """
    Class that provides a framework for multi-host migration.

    Migration can be run both synchronously and asynchronously.
    To specify what is going to happen during the multi-host
    migration, it is necessary to reimplement the method
    migration_scenario. It is possible to start multiple migrations
    in separate threads, since self.migrate is thread safe.

    Only one test using multihost migration framework should be
    started on one machine otherwise it is necessary to solve the
    problem with listen server port.

    Multihost migration starts SyncListenServer through which
    all messages are transfered, since the multiple hosts can
    be in diferent states.

    Class SyncData is used to transfer data over network or
    synchronize the migration process. Synchronization sessions
    are recognized by session_id.

    It is important to note that, in order to have multi-host
    migration, one needs shared guest image storage. The simplest
    case is when the guest images are on an NFS server.

    Example:
        class TestMultihostMigration(virt_utils.MultihostMigration):
            def __init__(self, test, params, env):
                super(testMultihostMigration, self).__init__(test, params, env)

            def migration_scenario(self):
                srchost = self.params.get("hosts")[0]
                dsthost = self.params.get("hosts")[1]

                def worker(mig_data):
                    vm = env.get_vm("vm1")
                    session = vm.wait_for_login(timeout=self.login_timeout)
                    session.sendline("nohup dd if=/dev/zero of=/dev/null &")
                    session.cmd("killall -0 dd")

                def check_worker(mig_data):
                    vm = env.get_vm("vm1")
                    session = vm.wait_for_login(timeout=self.login_timeout)
                    session.cmd("killall -9 dd")

                # Almost synchronized migration, waiting to end it.
                # Work is started only on first VM.
                self.migrate_wait(["vm1", "vm2"], srchost, dsthost,
                                  worker, check_worker)

                # Migration started in different threads.
                # It allows to start multiple migrations simultaneously.
                mig1 = self.migrate(["vm1"], srchost, dsthost,
                                    worker, check_worker)
                mig2 = self.migrate(["vm2"], srchost, dsthost)
                mig2.join()
                mig1.join()

    mig = TestMultihostMigration(test, params, env)
    mig.run()
    """
    def __init__(self, test, params, env, preprocess_env=True):
        self.test = test
        self.params = params
        self.env = env
        self.hosts = params.get("hosts")
        self.hostid = params.get('hostid', "")
        self.comm_port = int(params.get("comm_port", 13234))
        vms_count = len(params["vms"].split())

        self.login_timeout = int(params.get("login_timeout", 360))
        self.disk_prepare_timeout = int(params.get("disk_prepare_timeout",
                                              160 * vms_count))
        self.finish_timeout = int(params.get("finish_timeout",
                                              120 * vms_count))

        self.new_params = None

        if params.get("clone_master") == "yes":
            self.clone_master = True
        else:
            self.clone_master = False

        self.mig_timeout = int(params.get("mig_timeout"))
        # Port used to communicate info between source and destination
        self.regain_ip_cmd = params.get("regain_ip_cmd", "dhclient")

        self.vm_lock = threading.Lock()

        self.sync_server = None
        if self.clone_master:
            self.sync_server = SyncListenServer()

        if preprocess_env:
            self.preprocess_env()
            self._hosts_barrier(self.hosts, self.hosts, 'disk_prepared',
                                 self.disk_prepare_timeout)


    def migration_scenario(self):
        """
        Multi Host migration_scenario is started from method run where the
        exceptions are checked. It is not necessary to take care of
        cleaning up after test crash or finish.
        """
        raise NotImplementedError


    def migrate_vms_src(self, mig_data):
        """
        Migrate vms source.

        @param mig_Data: Data for migration.

        For change way how machine migrates is necessary
        re implement this method.
        """
        def mig_wrapper(vm, dsthost, vm_ports):
            vm.migrate(dest_host=dsthost, remote_port=vm_ports[vm.name])

        logging.info("Start migrating now...")
        multi_mig = []
        for vm in mig_data.vms:
            multi_mig.append((mig_wrapper, (vm, mig_data.dst,
                                            mig_data.vm_ports)))
        virt_utils.parallel(multi_mig)


    def migrate_vms_dest(self, mig_data):
        """
        Migrate vms destination. This function is started on dest host during
        migration.

        @param mig_Data: Data for migration.
        """
        pass


    def __del__(self):
        if self.sync_server:
            self.sync_server.close()


    def master_id(self):
        return self.hosts[0]


    def _hosts_barrier(self, hosts, session_id, tag, timeout):
        logging.debug("Barrier timeout: %d tags: %s" % (timeout, tag))
        tags = SyncData(self.master_id(), self.hostid, hosts,
                        "%s,%s,barrier" % (str(session_id), tag),
                        self.sync_server).sync(tag, timeout)
        logging.debug("Barrier tag %s" % (tags))


    def preprocess_env(self):
        """
        Prepare env to start vms.
        """
        virt_storage.preprocess_images(self.test.bindir, self.params, self.env)


    def _check_vms_source(self, mig_data):
        for vm in mig_data.vms:
            vm.wait_for_login(timeout=self.login_timeout)

        sync = SyncData(self.master_id(), self.hostid, mig_data.hosts,
                        mig_data.mig_id, self.sync_server)
        mig_data.vm_ports = sync.sync(timeout=120)[mig_data.dst]
        logging.info("Received from destination the migration port %s",
                     str(mig_data.vm_ports))


    def _check_vms_dest(self, mig_data):
        mig_data.vm_ports = {}
        for vm in mig_data.vms:
            logging.info("Communicating to source migration port %s",
                         vm.migration_port)
            mig_data.vm_ports[vm.name] = vm.migration_port

        SyncData(self.master_id(), self.hostid,
                 mig_data.hosts, mig_data.mig_id,
                 self.sync_server).sync(mig_data.vm_ports, timeout=120)


    def _prepare_params(self, mig_data):
        """
        Prepare separate params for vm migration.

        @param vms_name: List of vms.
        """
        new_params = mig_data.params.copy()
        new_params["vms"] = " ".join(mig_data.vms_name)
        return new_params


    def _check_vms(self, mig_data):
        """
        Check if vms are started correctly.

        @param vms: list of vms.
        @param source: Must be True if is source machine.
        """
        logging.info("Try check vms %s" % (mig_data.vms_name))
        for vm in mig_data.vms_name:
            if not self.env.get_vm(vm) in mig_data.vms:
                mig_data.vms.append(self.env.get_vm(vm))
        for vm in mig_data.vms:
            logging.info("Check vm %s on host %s" % (vm.name, self.hostid))
            vm.verify_alive()

        if mig_data.is_src():
            self._check_vms_source(mig_data)
        else:
            self._check_vms_dest(mig_data)


    def prepare_for_migration(self, mig_data, migration_mode):
        """
        Prepare destination of migration for migration.

        @param mig_data: Class with data necessary for migration.
        @param migration_mode: Migration mode for prepare machine.
        """
        new_params = self._prepare_params(mig_data)

        new_params['migration_mode'] = migration_mode
        new_params['start_vm'] = 'yes'
        self.vm_lock.acquire()
        virt_env_process.process(self.test, new_params, self.env,
                                 virt_env_process.preprocess_image,
                                 virt_env_process.preprocess_vm)
        self.vm_lock.release()

        self._check_vms(mig_data)


    def migrate_vms(self, mig_data):
        """
        Migrate vms.
        """
        if mig_data.is_src():
            self.migrate_vms_src(mig_data)
        else:
            self.migrate_vms_dest(mig_data)


    def check_vms(self, mig_data):
        """
        Check vms after migrate.

        @param mig_data: object with migration data.
        """
        for vm in mig_data.vms:
            if not guest_active(vm):
                raise error.TestFail("Guest not active after migration")

        logging.info("Migrated guest appears to be running")

        logging.info("Logging into migrated guest after migration...")
        for vm in mig_data.vms:
            session_serial = vm.wait_for_serial_login(timeout=
                                                      self.login_timeout)
            #There is sometime happen that system sends some message on
            #serial console and IP renew command block test. Because
            #there must be added "sleep" in IP renew command.
            session_serial.cmd(self.regain_ip_cmd)
            vm.wait_for_login(timeout=self.login_timeout)


    def postprocess_env(self):
        """
        Kill vms and delete cloned images.
        """
        virt_storage.postprocess_images(self.test.bindir, self.params)


    def migrate(self, vms_name, srchost, dsthost, start_work=None,
                check_work=None, mig_mode="tcp", params_append=None):
        """
        Migrate machine from srchost to dsthost. It executes start_work on
        source machine before migration and executes check_work on dsthost
        after migration.

        Migration execution progress:

        source host                   |   dest host
        --------------------------------------------------------
           prepare guest on both sides of migration
            - start machine and check if machine works
            - synchronize transfer data needed for migration
        --------------------------------------------------------
        start work on source guests   |   wait for migration
        --------------------------------------------------------
                     migrate guest to dest host.
              wait on finish migration synchronization
        --------------------------------------------------------
                                      |   check work on vms
        --------------------------------------------------------
                    wait for sync on finish migration

        @param vms_name: List of vms.
        @param srchost: src host id.
        @param dsthost: dst host id.
        @param start_work: Function started before migration.
        @param check_work: Function started after migration.
        @param mig_mode: Migration mode.
        @param params_append: Append params to self.params only for migration.
        """
        def migrate_wrap(vms_name, srchost, dsthost, start_work=None,
                check_work=None, params_append=None):
            logging.info("Starting migrate vms %s from host %s to %s" %
                         (vms_name, srchost, dsthost))
            error = None
            mig_data = MigrationData(self.params, srchost, dsthost,
                                     vms_name, params_append)
            try:
                try:
                    if mig_data.is_src():
                        self.prepare_for_migration(mig_data, None)
                    elif self.hostid == dsthost:
                        self.prepare_for_migration(mig_data, mig_mode)
                    else:
                        return

                    if mig_data.is_src():
                        if start_work:
                            start_work(mig_data)

                    self.migrate_vms(mig_data)

                    timeout = 30
                    if not mig_data.is_src():
                        timeout = self.mig_timeout
                    self._hosts_barrier(mig_data.hosts, mig_data.mig_id,
                                        'mig_finished', timeout)

                    if mig_data.is_dst():
                        self.check_vms(mig_data)
                        if check_work:
                            check_work(mig_data)

                except:
                    error = True
                    raise
            finally:
                if not error:
                    self._hosts_barrier(self.hosts,
                                        mig_data.mig_id,
                                        'test_finihed',
                                        self.finish_timeout)

        def wait_wrap(vms_name, srchost, dsthost):
            mig_data = MigrationData(self.params, srchost, dsthost, vms_name,
                                     None)
            timeout = (self.login_timeout + self.mig_timeout +
                       self.finish_timeout)

            self._hosts_barrier(self.hosts, mig_data.mig_id,
                                'test_finihed', timeout)

        if (self.hostid in [srchost, dsthost]):
            mig_thread = utils.InterruptedThread(migrate_wrap, (vms_name,
                                                                srchost,
                                                                dsthost,
                                                                start_work,
                                                                check_work,
                                                                params_append))
        else:
            mig_thread = utils.InterruptedThread(wait_wrap, (vms_name,
                                                             srchost,
                                                             dsthost))
        mig_thread.start()
        return mig_thread


    def migrate_wait(self, vms_name, srchost, dsthost, start_work=None,
                      check_work=None, mig_mode="tcp", params_append=None):
        """
        Migrate machine from srchost to dsthost and wait for finish.
        It executes start_work on source machine before migration and executes
        check_work on dsthost after migration.

        @param vms_name: List of vms.
        @param srchost: src host id.
        @param dsthost: dst host id.
        @param start_work: Function which is started before migration.
        @param check_work: Function which is started after
                           done of migration.
        """
        self.migrate(vms_name, srchost, dsthost, start_work, check_work,
                     mig_mode, params_append).join()


    def cleanup(self):
        """
        Cleanup env after test.
        """
        if self.clone_master:
            self.sync_server.close()
            self.postprocess_env()


    def run(self):
        """
        Start multihost migration scenario.
        After scenario is finished or if scenario crashed it calls postprocess
        machines and cleanup env.
        """
        try:
            self.migration_scenario()

            self._hosts_barrier(self.hosts, self.hosts, 'all_test_finihed',
                                self.finish_timeout)
        finally:
            self.cleanup()


def stop_windows_service(session, service, timeout=120):
    """
    Stop a Windows service using sc.
    If the service is already stopped or is not installed, do nothing.

    @param service: The name of the service
    @param timeout: Time duration to wait for service to stop
    @raise error.TestError: Raised if the service can't be stopped
    """
    end_time = time.time() + timeout
    while time.time() < end_time:
        o = session.cmd_output("sc stop %s" % service, timeout=60)
        # FAILED 1060 means the service isn't installed.
        # FAILED 1062 means the service hasn't been started.
        if re.search(r"\bFAILED (1060|1062)\b", o, re.I):
            break
        time.sleep(1)
    else:
        raise error.TestError("Could not stop service '%s'" % service)


def start_windows_service(session, service, timeout=120):
    """
    Start a Windows service using sc.
    If the service is already running, do nothing.
    If the service isn't installed, fail.

    @param service: The name of the service
    @param timeout: Time duration to wait for service to start
    @raise error.TestError: Raised if the service can't be started
    """
    end_time = time.time() + timeout
    while time.time() < end_time:
        o = session.cmd_output("sc start %s" % service, timeout=60)
        # FAILED 1060 means the service isn't installed.
        if re.search(r"\bFAILED 1060\b", o, re.I):
            raise error.TestError("Could not start service '%s' "
                                  "(service not installed)" % service)
        # FAILED 1056 means the service is already running.
        if re.search(r"\bFAILED 1056\b", o, re.I):
            break
        time.sleep(1)
    else:
        raise error.TestError("Could not start service '%s'" % service)


def get_time(session, time_command, time_filter_re, time_format):
    """
    Return the host time and guest time.  If the guest time cannot be fetched
    a TestError exception is raised.

    Note that the shell session should be ready to receive commands
    (i.e. should "display" a command prompt and should be done with all
    previous commands).

    @param session: A shell session.
    @param time_command: Command to issue to get the current guest time.
    @param time_filter_re: Regex filter to apply on the output of
            time_command in order to get the current time.
    @param time_format: Format string to pass to time.strptime() with the
            result of the regex filter.
    @return: A tuple containing the host time and guest time.
    """
    if len(re.findall("ntpdate|w32tm", time_command)) == 0:
        host_time = time.time()
        s = session.cmd_output(time_command)

        try:
            s = re.findall(time_filter_re, s)[0]
        except IndexError:
            logging.debug("The time string from guest is:\n%s", s)
            raise error.TestError("The time string from guest is unexpected.")
        except Exception, e:
            logging.debug("(time_filter_re, time_string): (%s, %s)",
                          time_filter_re, s)
            raise e

        guest_time = time.mktime(time.strptime(s, time_format))
    else:
        o = session.cmd(time_command)
        if re.match('ntpdate', time_command):
            offset = re.findall('offset (.*) sec', o)[0]
            host_main, host_mantissa = re.findall(time_filter_re, o)[0]
            host_time = (time.mktime(time.strptime(host_main, time_format)) +
                         float("0.%s" % host_mantissa))
            guest_time = host_time - float(offset)
        else:
            guest_time =  re.findall(time_filter_re, o)[0]
            offset = re.findall("o:(.*)s", o)[0]
            if re.match('PM', guest_time):
                hour = re.findall('\d+ (\d+):', guest_time)[0]
                hour = str(int(hour) + 12)
                guest_time = re.sub('\d+\s\d+:', "\d+\s%s:" % hour,
                                    guest_time)[:-3]
            else:
                guest_time = guest_time[:-3]
            guest_time = time.mktime(time.strptime(guest_time, time_format))
            host_time = guest_time + float(offset)

    return (host_time, guest_time)


def get_memory_info(lvms):
    """
    Get memory information from host and guests in format:
    Host: memfree = XXXM; Guests memsh = {XXX,XXX,...}

    @params lvms: List of VM objects
    @return: String with memory info report
    """
    if not isinstance(lvms, list):
        raise error.TestError("Invalid list passed to get_stat: %s " % lvms)

    try:
        meminfo = "Host: memfree = "
        meminfo += str(int(utils.freememtotal()) / 1024) + "M; "
        meminfo += "swapfree = "
        mf = int(utils.read_from_meminfo("SwapFree")) / 1024
        meminfo += str(mf) + "M; "
    except Exception, e:
        raise error.TestFail("Could not fetch host free memory info, "
                             "reason: %s" % e)

    meminfo += "Guests memsh = {"
    for vm in lvms:
        shm = vm.get_shared_meminfo()
        if shm is None:
            raise error.TestError("Could not get shared meminfo from "
                                  "VM %s" % vm)
        meminfo += "%dM; " % shm
    meminfo = meminfo[0:-2] + "}"

    return meminfo


def run_file_transfer(test, params, env):
    """
    Transfer a file back and forth between host and guest.

    1) Boot up a VM.
    2) Create a large file by dd on host.
    3) Copy this file from host to guest.
    4) Copy this file from guest to host.
    5) Check if file transfers ended good.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    login_timeout = int(params.get("login_timeout", 360))

    session = vm.wait_for_login(timeout=login_timeout)

    dir_name = test.tmpdir
    transfer_timeout = int(params.get("transfer_timeout"))
    transfer_type = params.get("transfer_type")
    tmp_dir = params.get("tmp_dir", "/tmp/")
    clean_cmd = params.get("clean_cmd", "rm -f")
    filesize = int(params.get("filesize", 4000))
    count = int(filesize / 10)
    if count == 0:
        count = 1

    host_path = os.path.join(dir_name, "tmp-%s" %
                             virt_utils.generate_random_string(8))
    host_path2 = host_path + ".2"
    cmd = "dd if=/dev/zero of=%s bs=10M count=%d" % (host_path, count)
    guest_path = (tmp_dir + "file_transfer-%s" %
                  virt_utils.generate_random_string(8))

    try:
        logging.info("Creating %dMB file on host", filesize)
        utils.run(cmd)

        if transfer_type == "remote":
            logging.info("Transfering file host -> guest, timeout: %ss",
                         transfer_timeout)
            t_begin = time.time()
            vm.copy_files_to(host_path, guest_path, timeout=transfer_timeout)
            t_end = time.time()
            throughput = filesize / (t_end - t_begin)
            logging.info("File transfer host -> guest succeed, "
                         "estimated throughput: %.2fMB/s", throughput)

            logging.info("Transfering file guest -> host, timeout: %ss",
                         transfer_timeout)
            t_begin = time.time()
            vm.copy_files_from(guest_path, host_path2, timeout=transfer_timeout)
            t_end = time.time()
            throughput = filesize / (t_end - t_begin)
            logging.info("File transfer guest -> host succeed, "
                         "estimated throughput: %.2fMB/s", throughput)
        else:
            raise error.TestError("Unknown test file transfer mode %s" %
                                  transfer_type)

        if (utils.hash_file(host_path, method="md5") !=
            utils.hash_file(host_path2, method="md5")):
            raise error.TestFail("File changed after transfer host -> guest "
                                 "and guest -> host")

    finally:
        logging.info('Cleaning temp file on guest')
        session.cmd("%s %s" % (clean_cmd, guest_path))
        logging.info('Cleaning temp files on host')
        try:
            os.remove(host_path)
            os.remove(host_path2)
        except OSError:
            pass
        session.close()


def run_autotest(vm, session, control_path, timeout, outputdir, params):
    """
    Run an autotest control file inside a guest (linux only utility).

    @param vm: VM object.
    @param session: A shell session on the VM provided.
    @param control_path: A path to an autotest control file.
    @param timeout: Timeout under which the autotest control file must complete.
    @param outputdir: Path on host where we should copy the guest autotest
            results to.

    The following params is used by the migration
    @param params: Test params used in the migration test
    """
    def copy_if_hash_differs(vm, local_path, remote_path):
        """
        Copy a file to a guest if it doesn't exist or if its MD5sum differs.

        @param vm: VM object.
        @param local_path: Local path.
        @param remote_path: Remote path.

        @return: Whether the hash differs (True) or not (False).
        """
        hash_differs = False
        local_hash = utils.hash_file(local_path)
        basename = os.path.basename(local_path)
        output = session.cmd_output("md5sum %s" % remote_path)
        if "such file" in output:
            remote_hash = "0"
        elif output:
            remote_hash = output.split()[0]
        else:
            logging.warning("MD5 check for remote path %s did not return.",
                            remote_path)
            # Let's be a little more lenient here and see if it wasn't a
            # temporary problem
            remote_hash = "0"
        if remote_hash != local_hash:
            hash_differs = True
            logging.debug("Copying %s to guest "
                          "(remote hash: %s, local hash:%s)",
                          basename, remote_hash, local_hash)
            vm.copy_files_to(local_path, remote_path)
        return hash_differs


    def extract(vm, remote_path, dest_dir):
        """
        Extract the autotest .tar.bz2 file on the guest, ensuring the final
        destination path will be dest_dir.

        @param vm: VM object
        @param remote_path: Remote file path
        @param dest_dir: Destination dir for the contents
        """
        basename = os.path.basename(remote_path)
        logging.debug("Extracting %s on VM %s", basename, vm.name)
        session.cmd("rm -rf %s" % dest_dir)
        dirname = os.path.dirname(remote_path)
        session.cmd("cd %s" % dirname)
        session.cmd("mkdir -p %s" % os.path.dirname(dest_dir))
        e_cmd = "tar xjvf %s -C %s" % (basename, os.path.dirname(dest_dir))
        output = session.cmd(e_cmd, timeout=120)
        autotest_dirname = ""
        for line in output.splitlines():
            autotest_dirname = line.split("/")[0]
            break
        if autotest_dirname != os.path.basename(dest_dir):
            session.cmd("cd %s" % os.path.dirname(dest_dir))
            session.cmd("mv %s %s" %
                        (autotest_dirname, os.path.basename(dest_dir)))


    def get_results(guest_autotest_path):
        """
        Copy autotest results present on the guest back to the host.
        """
        logging.debug("Trying to copy autotest results from guest")
        guest_results_dir = os.path.join(outputdir, "guest_autotest_results")
        if not os.path.exists(guest_results_dir):
            os.mkdir(guest_results_dir)
        vm.copy_files_from("%s/results/default/*" % guest_autotest_path,
                           guest_results_dir)


    def get_results_summary(guest_autotest_path):
        """
        Get the status of the tests that were executed on the host and close
        the session where autotest was being executed.
        """
        session.cmd("cd %s" % guest_autotest_path)
        output = session.cmd_output("cat results/*/status")
        try:
            results = scan_results.parse_results(output)
            # Report test results
            logging.info("Results (test, status, duration, info):")
            for result in results:
                logging.info(str(result))
            session.close()
            return results
        except Exception, e:
            logging.error("Error processing guest autotest results: %s", e)
            return None


    if not os.path.isfile(control_path):
        raise error.TestError("Invalid path to autotest control file: %s" %
                              control_path)

    migrate_background = params.get("migrate_background") == "yes"
    if migrate_background:
        mig_timeout = float(params.get("mig_timeout", "3600"))
        mig_protocol = params.get("migration_protocol", "tcp")

    compressed_autotest_path = "/tmp/autotest.tar.bz2"
    destination_autotest_path = GLOBAL_CONFIG.get_config_value('COMMON',
                                                            'autotest_top_path')

    # To avoid problems, let's make the test use the current AUTODIR
    # (autotest client path) location
    autotest_path = os.environ['AUTODIR']
    autotest_basename = os.path.basename(autotest_path)
    autotest_parentdir = os.path.dirname(autotest_path)

    # tar the contents of bindir/autotest
    cmd = ("cd %s; tar cvjf %s %s/*" %
           (autotest_parentdir, compressed_autotest_path, autotest_basename))
    # Until we have nested virtualization, we don't need the kvm test :)
    cmd += " --exclude=%s/tests/kvm" % autotest_basename
    cmd += " --exclude=%s/results" % autotest_basename
    cmd += " --exclude=%s/tmp" % autotest_basename
    cmd += " --exclude=%s/control*" % autotest_basename
    cmd += " --exclude=*.pyc"
    cmd += " --exclude=*.svn"
    cmd += " --exclude=*.git"
    utils.run(cmd)

    # Copy autotest.tar.bz2
    update = copy_if_hash_differs(vm, compressed_autotest_path,
                                  compressed_autotest_path)

    # Extract autotest.tar.bz2
    if update:
        extract(vm, compressed_autotest_path, destination_autotest_path)

    g_fd, g_path = tempfile.mkstemp(dir='/tmp/')
    aux_file = os.fdopen(g_fd, 'w')
    config = GLOBAL_CONFIG.get_section_values(('CLIENT', 'COMMON'))
    config.write(aux_file)
    aux_file.close()
    global_config_guest = os.path.join(destination_autotest_path,
                                       'global_config.ini')
    vm.copy_files_to(g_path, global_config_guest)
    os.unlink(g_path)

    vm.copy_files_to(control_path,
                     os.path.join(destination_autotest_path, 'control'))

    # Run the test
    logging.info("Running autotest control file %s on guest, timeout %ss",
                 os.path.basename(control_path), timeout)
    session.cmd("cd %s" % destination_autotest_path)
    try:
        session.cmd("rm -f control.state")
        session.cmd("rm -rf results/*")
    except aexpect.ShellError:
        pass
    try:
        bg = None
        try:
            logging.info("---------------- Test output ----------------")
            if migrate_background:
                mig_timeout = float(params.get("mig_timeout", "3600"))
                mig_protocol = params.get("migration_protocol", "tcp")

                bg = utils.InterruptedThread(session.cmd_output,
                                      kwargs={'cmd': "./autotest control",
                                              'timeout': timeout,
                                              'print_func': logging.info})

                bg.start()

                while bg.isAlive():
                    logging.info("Autotest job did not end, start a round of "
                                 "migration")
                    vm.migrate(timeout=mig_timeout, protocol=mig_protocol)
            else:
                session.cmd_output("./autotest control", timeout=timeout,
                                   print_func=logging.info)
        finally:
            logging.info("------------- End of test output ------------")
            if migrate_background and bg:
                bg.join()
    except aexpect.ShellTimeoutError:
        if vm.is_alive():
            get_results(destination_autotest_path)
            get_results_summary(destination_autotest_path)
            raise error.TestError("Timeout elapsed while waiting for job to "
                                  "complete")
        else:
            raise error.TestError("Autotest job on guest failed "
                                  "(VM terminated during job)")
    except aexpect.ShellProcessTerminatedError:
        get_results(destination_autotest_path)
        raise error.TestError("Autotest job on guest failed "
                              "(Remote session terminated during job)")

    results = get_results_summary(destination_autotest_path)
    get_results(destination_autotest_path)

    # Make a list of FAIL/ERROR/ABORT results (make sure FAIL results appear
    # before ERROR results, and ERROR results appear before ABORT results)
    bad_results = [r[0] for r in results if r[1] == "FAIL"]
    bad_results += [r[0] for r in results if r[1] == "ERROR"]
    bad_results += [r[0] for r in results if r[1] == "ABORT"]

    # Fail the test if necessary
    if not results:
        raise error.TestFail("Autotest control file run did not produce any "
                             "recognizable results")
    if bad_results:
        if len(bad_results) == 1:
            e_msg = ("Test %s failed during control file execution" %
                     bad_results[0])
        else:
            e_msg = ("Tests %s failed during control file execution" %
                     " ".join(bad_results))
        raise error.TestFail(e_msg)


def get_loss_ratio(output):
    """
    Get the packet loss ratio from the output of ping
.
    @param output: Ping output.
    """
    try:
        return int(re.findall('(\d+)% packet loss', output)[0])
    except IndexError:
        logging.debug(output)
        return -1


def raw_ping(command, timeout, session, output_func):
    """
    Low-level ping command execution.

    @param command: Ping command.
    @param timeout: Timeout of the ping command.
    @param session: Local executon hint or session to execute the ping command.
    """
    if session is None:
        process = aexpect.run_bg(command, output_func=output_func,
                                        timeout=timeout)

        # Send SIGINT signal to notify the timeout of running ping process,
        # Because ping have the ability to catch the SIGINT signal so we can
        # always get the packet loss ratio even if timeout.
        if process.is_alive():
            virt_utils.kill_process_tree(process.get_pid(), signal.SIGINT)

        status = process.get_status()
        output = process.get_output()

        process.close()
        return status, output
    else:
        output = ""
        try:
            output = session.cmd_output(command, timeout=timeout,
                                        print_func=output_func)
        except aexpect.ShellTimeoutError:
            # Send ctrl+c (SIGINT) through ssh session
            session.send("\003")
            try:
                output2 = session.read_up_to_prompt(print_func=output_func)
                output += output2
            except aexpect.ExpectTimeoutError, e:
                output += e.output
                # We also need to use this session to query the return value
                session.send("\003")

        session.sendline(session.status_test_command)
        try:
            o2 = session.read_up_to_prompt()
        except aexpect.ExpectError:
            status = -1
        else:
            try:
                status = int(re.findall("\d+", o2)[0])
            except Exception:
                status = -1

        return status, output


def ping(dest=None, count=None, interval=None, interface=None,
         packetsize=None, ttl=None, hint=None, adaptive=False,
         broadcast=False, flood=False, timeout=0,
         output_func=logging.debug, session=None):
    """
    Wrapper of ping.

    @param dest: Destination address.
    @param count: Count of icmp packet.
    @param interval: Interval of two icmp echo request.
    @param interface: Specified interface of the source address.
    @param packetsize: Packet size of icmp.
    @param ttl: IP time to live.
    @param hint: Path mtu discovery hint.
    @param adaptive: Adaptive ping flag.
    @param broadcast: Broadcast ping flag.
    @param flood: Flood ping flag.
    @param timeout: Timeout for the ping command.
    @param output_func: Function used to log the result of ping.
    @param session: Local executon hint or session to execute the ping command.
    """
    if dest is not None:
        command = "ping %s " % dest
    else:
        command = "ping localhost "
    if count is not None:
        command += " -c %s" % count
    if interval is not None:
        command += " -i %s" % interval
    if interface is not None:
        command += " -I %s" % interface
    if packetsize is not None:
        command += " -s %s" % packetsize
    if ttl is not None:
        command += " -t %s" % ttl
    if hint is not None:
        command += " -M %s" % hint
    if adaptive:
        command += " -A"
    if broadcast:
        command += " -b"
    if flood:
        command += " -f -q"
        output_func = None

    return raw_ping(command, timeout, session, output_func)


def get_linux_ifname(session, mac_address):
    """
    Get the interface name through the mac address.

    @param session: session to the virtual machine
    @mac_address: the macaddress of nic
    """

    output = session.cmd_output("ifconfig -a")

    try:
        ethname = re.findall("(\w+)\s+Link.*%s" % mac_address, output,
                             re.IGNORECASE)[0]
        return ethname
    except Exception:
        return None


def run_virt_sub_test(test, params, env, sub_type=None, tag=None):
    """
    Call another test script in one test script.
    @param test:   KVM test object.
    @param params: Dictionary with the test parameters.
    @param env:    Dictionary with test environment.
    @param sub_type: Type of called test script.
    @param tag:    Tag for get the sub_test params
    """
    if sub_type is None:
        raise error.TestError("No sub test is found")
    virt_dir = os.path.dirname(virt_utils.__file__)
    subtest_dir_virt = os.path.join(virt_dir, "tests")
    subtest_dir_kvm = os.path.join(test.bindir, "tests")
    subtest_dir = None
    for d in [subtest_dir_kvm, subtest_dir_virt]:
        module_path = os.path.join(d, "%s.py" % sub_type)
        if os.path.isfile(module_path):
            subtest_dir = d
            break
    if subtest_dir is None:
        raise error.TestError("Could not find test file %s.py "
                              "on either %s or %s directory" % (sub_type,
                              subtest_dir_kvm, subtest_dir_virt))

    f, p, d = imp.find_module(sub_type, [subtest_dir])
    test_module = imp.load_module(sub_type, f, p, d)
    f.close()
    # Run the test function
    run_func = getattr(test_module, "run_%s" % sub_type)
    if tag is not None:
        params = params.object_params(tag)
    run_func(test, params, env)


def pin_vm_threads(vm, node):
    """
    Pin VM threads to single cpu of a numa node
    @param vm: VM object
    @param node: NumaNode object
    """
    for i in vm.vhost_threads:
        logging.info("pin vhost thread(%s) to cpu(%s)" % (i, node.pin_cpu(i)))
    for i in vm.vcpu_threads:
        logging.info("pin vcpu thread(%s) to cpu(%s)" % (i, node.pin_cpu(i)))


def service_setup(vm, session, dir):

    params = vm.get_params()
    rh_perf_envsetup_script = params.get("rh_perf_envsetup_script")
    rebooted = params.get("rebooted", "rebooted")

    if rh_perf_envsetup_script:
        src = os.path.join(dir, rh_perf_envsetup_script)
        vm.copy_files_to(src, "/tmp/rh_perf_envsetup.sh")
        logging.info("setup perf environment for host")
        commands.getoutput("bash %s host %s" % (src, rebooted))
        logging.info("setup perf environment for guest")
        session.cmd("bash /tmp/rh_perf_envsetup.sh guest %s" % rebooted)

def cmd_runner_monitor(vm, monitor_cmd, test_cmd, guest_path, timeout=300):
    """
    For record the env information such as cpu utilization, meminfo while
    run guest test in guest.
    @vm: Guest Object
    @monitor_cmd: monitor command running in backgroud
    @test_cmd: test suit run command
    @guest_path: path in guest to store the test result and monitor data
    @timeout: longest time for monitor running
    Return: tag the suffix of the results
    """
    def thread_kill(cmd, p_file):
        fd = shelve.open(p_file)
        s, o = commands.getstatusoutput("pstree -p %s" % fd["pid"])
        tmp = re.split("\s+", cmd)[0]
        pid = re.findall("%s.(\d+)" % tmp, o)[0]
        s, o = commands.getstatusoutput("kill -9 %s" % pid)
        fd.close()
        return (s, o)

    def monitor_thread(m_cmd, p_file, r_file):
        fd = shelve.open(p_file)
        fd["pid"] = os.getpid()
        fd.close()
        os.system("%s &> %s" % (m_cmd, r_file))

    def test_thread(session, m_cmd, t_cmd, p_file, flag, timeout):
        flag.put(True)
        s, o = session.cmd_status_output(t_cmd, timeout)
        if s != 0:
            raise error.TestFail("Test failed or timeout: %s" % o)
        if not flag.empty():
            flag.get()
            thread_kill(m_cmd, p_file)

    kill_thread_flag = Queue(1)
    session = wait_for_login(vm, 0, 300, 0, 2)
    tag = vm.instance
    pid_file = "/tmp/monitor_pid_%s" % tag
    result_file = "/tmp/host_monitor_result_%s" % tag

    monitor = threading.Thread(target=monitor_thread,args=(monitor_cmd,
                              pid_file, result_file))
    test_runner = threading.Thread(target=test_thread, args=(session,
                                   monitor_cmd, test_cmd, pid_file,
                                   kill_thread_flag, timeout))
    monitor.start()
    test_runner.start()
    monitor.join(int(timeout))
    if not kill_thread_flag.empty():
        kill_thread_flag.get()
        thread_kill(monitor_cmd, pid_file)
        thread_kill("sh", pid_file)

    guest_result_file = "/tmp/guest_result_%s" % tag
    guest_monitor_result_file = "/tmp/guest_monitor_result_%s" % tag
    vm.copy_files_from(guest_path, guest_result_file)
    vm.copy_files_from("%s_monitor" % guest_path, guest_monitor_result_file)
    return tag

def aton(str):
    """
    Transform a string to a number(include float and int). If the string is
    not in the form of number, just return false.

    @str: string to transfrom
    Return: float, int or False for failed transform
    """
    try:
        return int(str)
    except ValueError:
        try:
            return float(str)
        except ValueError:
            return False

def summary_up_result(result_file, ignore, row_head, column_mark):
    """
    Use to summary the monitor or other kinds of results. Now it calculates
    the average value for each item in the results. It fits to the records
    that are in matrix form.

    @result_file: files which need to calculate
    @ignore: pattern for the comment in results which need to through away
    @row_head: pattern for the items in row
    @column_mark: pattern for the first line in matrix which used to generate
    the items in column
    Return: A dictionary with the average value of results
    """
    head_flag = False
    result_dict = {}
    column_list = {}
    row_list = []
    fd = open(result_file, "r")
    for eachLine in fd:
        if len(re.findall(ignore, eachLine)) == 0:
            if len(re.findall(column_mark, eachLine)) != 0 and not head_flag:
                column = 0
                empty, row, eachLine = re.split(row_head, eachLine)
                for i in re.split("\s+", eachLine):
                    if i:
                        result_dict[i] = {}
                        column_list[column] = i
                        column += 1
                head_flag = True
            elif len(re.findall(column_mark, eachLine)) == 0:
                column = 0
                empty, row, eachLine = re.split(row_head, eachLine)
                row_flag = False
                for i in row_list:
                    if row == i:
                        row_flag = True
                if row_flag == False:
                    row_list.append(row)
                    for i in result_dict:
                        result_dict[i][row] = []
                for i in re.split("\s+", eachLine):
                    if i:
                        result_dict[column_list[column]][row].append(i)
                        column += 1
    fd.close()
    # Calculate the average value
    average_list = {}
    for i in column_list:
        average_list[column_list[i]] = {}
        for j in row_list:
            average_list[column_list[i]][j] = {}
            check = result_dict[column_list[i]][j][0]
            if aton(check) or aton(check) == 0.0:
                count = 0
                for k in result_dict[column_list[i]][j]:
                    count += aton(k)
                average_list[column_list[i]][j] = "%.2f" % (count /
                                len(result_dict[column_list[i]][j]))

    return average_list
