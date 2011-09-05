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

import time, os, logging, re, signal
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
from autotest_lib.client.tools import scan_results
import aexpect, virt_utils, virt_vm


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
            except virt_utils.LoginError, e:
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
            except (virt_utils.LoginError, virt_vm.VMError), e:
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
                    uri = "tcp:localhost:%d" % dest_vm.migration_port
                else:
                    uri = 'tcp:%s:%d' % (dest_host, mig_port)
            elif mig_protocol == "unix":
                uri = "unix:%s" % dest_vm.migration_file
            elif mig_protocol == "exec":
                uri = '"exec:nc localhost %s"' % dest_vm.migration_port

            if offline:
                vm.monitor.cmd("stop")
            vm.monitor.migrate(uri)

            if mig_cancel:
                time.sleep(2)
                vm.monitor.cmd("migrate_cancel")
                if not virt_utils.wait_for(mig_cancelled, 60, 2, 2,
                                          "Waiting for migration "
                                          "cancellation"):
                    raise error.TestFail("Failed to cancel migration")
                if offline:
                    vm.monitor.cmd("cont")
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
                    dest_vm.monitor.cmd("cont")
        except:
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
        if "paused" in dest_vm.monitor.info("status"):
            logging.debug("Destination VM is paused, resuming it")
            dest_vm.monitor.cmd("cont")

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
    destination_autotest_path = "/usr/local/autotest"

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

                bg = virt_utils.Thread(session.cmd_output,
                                      kwargs={'cmd': "bin/autotest control",
                                              'timeout': timeout,
                                              'print_func': logging.info})

                bg.start()

                while bg.is_alive():
                    logging.info("Autotest job did not end, start a round of "
                                 "migration")
                    vm.migrate(timeout=mig_timeout, protocol=mig_protocol)
            else:
                session.cmd_output("bin/autotest control", timeout=timeout,
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
            except:
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
    except:
        return None
