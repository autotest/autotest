import os, re, logging, time
from autotest.client.virt import virt_utils, kvm_monitor
from autotest.client.shared import error, utils


def run_migration_with_speed_measurement(test, params, env):
    """
    KVM migration test:
    1) Get a live VM and clone it.
    2) Verify that the source VM supports migration.  If it does, proceed with
            the test.
    3) Start memory load on vm.
    4) Send a migration command to the source VM and collecting statistic
            of migration speed.
    !) If migration speed is too high migration could be successful and then
            test ends with warning.
    5) Kill off both VMs.
    6) Print statistic of migration.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    login_timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=login_timeout)

    mig_timeout = float(params.get("mig_timeout", "10"))
    mig_protocol = params.get("migration_protocol", "tcp")

    install_path = params.get("cpuflags_install_path", "/tmp")

    vm_mem = int(params.get("mem", "512"))

    get_mig_speed = re.compile("^transferred ram: (\d+) kbytes$",
                               re.MULTILINE)

    mig_speed = params.get("mig_speed", "1G")
    mig_speed_accuracy = float(params.get("mig_speed_accuracy", "0.2"))
    clonevm = None

    def get_migration_statistic(vm):
        last_transfer_mem = 0
        transfered_mem = 0
        mig_stat = utils.Statistic()
        for _ in range(30):
            o = vm.monitor.info("migrate")
            warning_msg = ("Migration already ended. Migration speed is"
                           " probably too high and will block vm while"
                           " filling its memory.")
            fail_msg = ("Could not determine the transferred memory from"
                        " monitor data: %s" % o)
            if isinstance(o, str):
                if not "status: active" in o:
                    raise error.TestWarn(warning_msg)
                try:
                    transfered_mem = int(get_mig_speed.search(o).groups()[0])
                except (IndexError, ValueError):
                    raise error.TestFail(fail_msg)
            else:
                if o.get("status") != "active":
                    raise error.TestWarn(warning_msg)
                try:
                    transfered_mem = o.get("ram").get("transferred") / (1024)
                except (IndexError, ValueError):
                    raise error.TestFail(fail_msg)

            real_mig_speed = (transfered_mem - last_transfer_mem) / 1024

            last_transfer_mem = transfered_mem

            logging.debug("Migration speeed %s MB." % (real_mig_speed))
            mig_stat.record(real_mig_speed)
            time.sleep(1)

        return mig_stat

    try:
        # Reboot the VM in the background
        virt_utils.install_cpuflags_util_on_vm(test, vm, install_path,
                                               extra_flags="-msse3 -msse2")

        vm.monitor.migrate_set_speed(mig_speed)

        cmd = ("%s/cpuflags-test --stressmem %d" %
                (os.path.join(install_path, "test_cpu_flags"), vm_mem / 2))
        logging.debug("Sending command: %s" % (cmd))
        session.sendline(cmd)

        time.sleep(2)

        clonevm = vm.migrate(mig_timeout, mig_protocol,
                             not_wait_for_migration=True)

        mig_speed = utils.convert_data_size(mig_speed, "M")

        mig_stat = get_migration_statistic(vm)

        mig_speed = mig_speed / (1024 * 1024)
        real_speed = mig_stat.get_average()
        ack_speed = mig_speed * mig_speed_accuracy

        logging.info("Desired migration speed: %d MB/s." % (mig_speed))
        logging.info("Average migration speed: %d MB/s" %
                                (mig_stat.get_average()))
        logging.info("Minimum migration speed: %d MB/s" %
                                (mig_stat.get_min()))
        logging.info("Maximum migration speed: %d MB/s" %
                                (mig_stat.get_max()))

        if real_speed < mig_speed - ack_speed:
            raise error.TestWarn("Migration speed %s MB is slower by more"
                                 " %3.1f%% than desired speed %s MB" %
                         (real_speed, mig_speed_accuracy * 100, mig_speed))
        if real_speed > mig_speed + ack_speed:
            raise error.TestWarn("Migration speed %s MB is faster by more"
                                 " %3.1f%% than desired speed %s MB" %
                         (real_speed, mig_speed_accuracy * 100, mig_speed))

    finally:
        session.close()
        if clonevm:
            clonevm.destroy(gracefully=False)
        if vm:
            vm.destroy(gracefully=False)
