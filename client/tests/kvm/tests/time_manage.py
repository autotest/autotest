import logging, time, commands
from autotest.client.shared import error
from autotest.client.virt import virt_test_utils, aexpect
from autotest.client.virt import virt_env_process

@error.context_aware
def run_time_manage(test, params, env):
    """
    Time manage test:

    1) Generate stress in host.
    2) Run atleast 15 vms with "driftfix=slew" option
    3) Reboot the guest.
    4) Repeat the step 3 for all guests and check whether the guest
       responds properly(not any watchdog reported).
    5) TODO: Improve the way of checking the response and
        run some stress inside guest too.
    6) Continue the step 4 for 10 iterations and
       record the guest/host realtime, calculate drift in time for
       each iterations.
    7) Print the drift values for all sessions
    8) TODO: Validate if the drift value has to be within defined value

    @param test: KVM test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    # Checking the main vm is alive
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

    # Collect test parameters
    login_timeout = float(params.get("login_timeout", 240))
    host_load_command = params.get("host_load_command")
    host_load_kill_command = params.get("host_load_kill_command")
    time_command = params.get("time_command")
    time_filter_re = params.get("time_filter_re")
    time_format = params.get("time_format")

    # Intialize the variables
    itr = 0
    num = 2
    host_load_sessions = []
    sessions = [session]
    prev_time = []
    curr_time = []
    timedrift = []
    totaldrift = []
    vmnames =["vm1"]

    # Run some load on the host
    logging.info("Starting load on host.")
    host_load_sessions.append(aexpect.run_bg(host_load_command,
                                             output_func=logging.debug,
                                             output_prefix="host load ",
                                             timeout=0.5))
    # Boot the VMs
    try:
        while num <= int(params.get("max_vms")):
            # Clone vm according to the first one
            vm_name = "vm%d" % num
            vmnames.append(vm_name)
            vm_params = vm.params.copy()
            curr_vm = vm.clone(vm_name, vm_params)
            env.register_vm(vm_name, curr_vm)
            virt_env_process.preprocess_vm(test, vm_params, env, vm_name)
            params["vms"] += " " + vm_name

            sessions.append(curr_vm.wait_for_login(timeout=login_timeout))
            logging.info("Guest #%d booted up successfully", num)

            # Check whether all previous shell sessions are responsive
            error.context("checking responsiveness of the booted guest")
            for se in sessions:
                se.cmd(params.get("alive_test_cmd"))
            num += 1

        while itr <= int(params.get("max_itrs")):
            for vmid,se in enumerate(sessions):
                # Get the respective vm object
                vmname = "vm%d" % (vmid +1)
                vm = env.get_vm(vmname)
                # Run current iteration
                logging.info("Rebooting:vm%d iteration %d " % ((vmid + 1), itr))
                se = vm.reboot(se ,timeout=timeout)
                # Remember the current changed session
                sessions[vmid] = se
                error.context("checking responsiveness of guest")
                se.cmd(params.get("alive_test_cmd"))
                if itr == 0:
                    (ht0, gt0) = virt_test_utils.get_time(se, time_command,
                                                   time_filter_re, time_format)
                    prev_time.append((ht0, gt0))
                else:
                    (ht1, gt1) = virt_test_utils.get_time(se, time_command,
                                                   time_filter_re, time_format)
                    curr_time.append((ht1, gt1))
            if itr != 0:
                for i in range(int(params.get("max_vms"))):
                    hdelta = curr_time[i][0] - prev_time[i][0]
                    gdelta = curr_time[i][1] - prev_time[i][1]
                    drift = format( 100.0 * (hdelta - gdelta) / hdelta, ".2f" )
                    timedrift.append(drift)
                totaldrift.append(timedrift)
                prev_time = curr_time
                timedrift = []
                curr_time = []
            # Wait for some time before next iteration
            time.sleep(30)
            itr += 1

        logging.info("The time drift values for all VM sessions/iterations")
        logging.info("VM-Name:%s" % vmnames)
        for idx,value in enumerate(totaldrift):
            logging.info("itr-%2d:%s" % (idx+1,value))

    finally:
        for se in sessions:
            # Closing all the sessions.
            se.close()
        logging.info("killing load on host.")
        host_load_sessions.append(aexpect.run_bg(host_load_kill_command,
                                                 output_func=logging.debug,
                                                 output_prefix="host load kill",
                                                 timeout=0.5))
