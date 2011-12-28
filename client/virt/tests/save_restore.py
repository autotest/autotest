import logging, time, tempfile, os.path
from autotest_lib.client.common_lib import error

def run_save_restore(test, params, env):
    """
    VM save / restore test:

    1) Wait save_restore_start_delay seconds (default=10.0)
    2) Verify VM is running
    3) Pause, save VM to file (optionally in save_restore_path), verify paused.
    4) wait save_restore_delay seconds (if specified)
    5) restore VM from file, verify running
    6) Repeat save_restore_repeat times or 
       until save_restore_duration seconds pass.

    @param test: test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """

    def get_save_filename(path="",file_pfx=""):
        """
        Generate a guaranteed not to clash filename.
        
        @oaram: path: Optional base path to place file
        @param: file_pfxx: Optional prefix to filename
        @return: absolute path to new non-clashing filename
        """
        if not path:
            path = tempfile.gettempdir()
        fd,filename = tempfile.mkstemp(prefix = file_pfx, dir=path)
        os.close(fd)
        return filename

    def nuke_filename(filename):
        """
        Try to unlink filename, ignore any os errors.
        """
        try:
            os.unlink(filename)
        except OSError:
            pass

    vm = env.get_vm(params["main_vm"])
    # TODO: Verify initial VM state
    session = vm.wait_for_login()
    # FIXME: If VM already running, it gets paused for some reason.
    start_delay = float(params.get("save_restore_start_delay", "10.0"))
    restore_delay = float(params.get("save_restore_delay", "0.0"))
    path = os.path.abspath(params.get("save_restore_path", "/tmp")) # Validates path
    file_pfx = vm.name+'-'
    start_time = time.time()
    now = time_to_stop = start_time + float(params.get("save_restore_duration", "60.0"))
    repeat = int(params.get("save_restore_repeat","1"))
    while True:
        try:
            if not session.is_responsive():
                raise error.TestFail("Guest shell session is non-responsive")
            logging.info("Save/restores left: %d (or %0.4f more seconds)" % 
                         (repeat, (time_to_stop - time.time())))
            # TODO: Start some background test or load within VM
            if start_delay:
                logging.debug("Sleeping %0.4f seconds start_delay" % start_delay)
                time.sleep(start_delay)
            vm.pause()
            save_file = get_save_filename(path, file_pfx)
            vm.save_to_file(save_file)
            if restore_delay:
                logging.debug("Sleeping %0.4f seconds restore_delay" % restore_delay)
                time.sleep(restore_delay)
            vm.restore_from_file(save_file)
            vm.resume() # make sure some work gets done
            vm.verify_kernel_crash()
            now = time.time()
            # TODO: Examine background test/load completion/success status
        finally:
            if save_file:
                nuke_filename(save_file) # make sure these are cleaned up
        # Prepare/check next loop itteration
        repeat -= 1
        if (now >= time_to_stop) or (repeat <= 0):#TODO: or BG test status==foo
            break
    logging.info("Save/Restore itteration(s) complete.")
    if repeat > 0: # time_to_stop reached but itterations didn't complete
        raise error.TestFail("Save/Restore save_restore_duration"+\
                             " exceeded by %0.4f seconds with %d itterations"+\
                             " remaining." % (now-time_to_stop, repeat+1))
    # TODO: Check for any other failure conditions
    else:
        pass
