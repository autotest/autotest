import logging, time, tempfile, os
from autotest.client.shared import error


def run_boot_savevm(test, params, env):
    """
    libvirt boot savevm test:

    1) Start guest booting
    2) Periodically savevm/loadvm while guest booting
    4) Stop test when able to login, or fail after timeout seconds.

    @param test: test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive() # This shouldn't require logging in to guest
    savevm_delay = float(params.get("savevm_delay"))
    savevm_login_delay = float(params.get("savevm_login_delay"))
    savevm_login_timeout = float(params.get("savevm_timeout"))
    savevm_statedir = params.get("savevm_statedir", tempfile.gettempdir())
    fd, savevm_statefile = tempfile.mkstemp(suffix='.img', prefix=vm.name+'-',
                                            dir=savevm_statedir)
    os.close(fd) # save_to_file doesn't need the file open
    start_time = time.time()
    cycles = 0

    successful_login = False
    while (time.time() - start_time) < savevm_login_timeout:
        logging.info("Save/Restore cycle %d", cycles + 1)
        time.sleep(savevm_delay)
        vm.pause()
        vm.save_to_file(savevm_statefile) # Re-use same filename
        vm.restore_from_file(savevm_statefile)
        vm.resume() # doesn't matter if already running or not
        vm.verify_kernel_crash() # just in case
        try:
            vm.wait_for_login(timeout=savevm_login_delay)
            successful_login = True # not set if timeout expires
            os.unlink(savevm_statefile) # don't let these clutter disk
            break
        except:
            pass # loop until successful login or time runs out
        cycles += 1

    time_elapsed = int(time.time() - start_time)
    info = "after %s s, %d load/save cycles" % (time_elapsed, cycles + 1)
    if not successful_login:
        raise error.TestFail("Can't log on '%s' %s" % (vm.name, info))
    else:
        logging.info("Test ended %s", info)
