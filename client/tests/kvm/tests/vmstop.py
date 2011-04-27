import logging, time, os
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
from autotest_lib.client.virt import virt_utils


def run_vmstop(test, params, env):
    """
    KVM guest stop test:
    1) Log into a guest
    2) Copy a file into guest
    3) Stop guest
    4) Check the status through monitor
    5) Check the session
    6) Migrat the vm to a file twice and compare them.

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = float(params.get("login_timeout", 240))
    session = vm.wait_for_login(timeout=timeout)

    save_path = params.get("save_path", "/tmp")
    clean_save = params.get("clean_save") == "yes"
    save1 = os.path.join(save_path, "save1")
    save2 = os.path.join(save_path, "save2")

    guest_path = params.get("guest_path", "/tmp")
    file_size = params.get("file_size", "1000")

    try:
        utils.run("dd if=/dev/zero of=/tmp/file bs=1M count=%s" % file_size)
        # Transfer file from host to guest, we didn't expect the finish of
        # transfer, we just let it to be a kind of stress in guest.
        bg = virt_utils.Thread(vm.copy_files_to, ("/tmp/file", guest_path),
                               dict(verbose=True, timeout=60))
        logging.info("Start the background transfer")
        bg.start()

        try:
            # wait for the transfer start
            time.sleep(5)
            logging.info("Stop the VM")
            vm.monitor.cmd("stop")

            # check with monitor
            logging.info("Check the status through monitor")
            if "paused" not in vm.monitor.info("status"):
                raise error.TestFail("Guest did not pause after sending stop")

            # check through session
            logging.info("Check the session")
            if session.is_responsive():
                raise error.TestFail("Session still alive after sending stop")

            # Check with the migration file
            logging.info("Save and check the state files")
            for p in [save1, save2]:
                vm.save_to_file(p)
                time.sleep(1)
                if not os.path.isfile(p):
                    raise error.TestFail("VM failed to save state file %s" % p)

            # Fail if we see deltas
            md5_save1 = utils.hash_file(save1)
            md5_save2 = utils.hash_file(save2)
            if md5_save1 != md5_save2:
                raise error.TestFail("The produced state files differ")
        finally:
            bg.join(suppress_exception=True)

    finally:
        session.close()
        if clean_save:
            logging.debug("Clean the state files")
            if os.path.isfile(save1):
                os.remove(save1)
            if os.path.isfile(save2):
                os.remove(save2)
        vm.monitor.cmd("cont")
