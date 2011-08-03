import re, logging
from autotest_lib.client.common_lib import error


@error.context_aware
def run_hdparm(test, params, env):
    """
    Test hdparm setting on linux guest os. This case will:
    1) Set/record parameters value of hard disk to low performance status.
    2) Perform device/cache read timings then record the results.
    3) Set/record parameters value of hard disk to high performance status.
    4) Perform device/cache read timings then compare two results.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    def check_setting_result(set_cmd, timeout):
        params = re.findall("(-[a-zA-Z])([0-9]*)", set_cmd)
        disk = re.findall("(\/+[a-z]*\/[a-z]*$)", set_cmd)[0]
        for (param, value) in params:
            cmd = "hdparm %s %s" % (param, disk)
            (s, output) = session.cmd_status_output(cmd, timeout)
            if s != 0:
                raise error.TestError("Fail to get %s parameter value. "
                                      "Output is:\n%s" % (param, output.strip()))
            if value not in output:
                raise error.TestFail("Fail to set %s parameter to value: %s"
                                     % (param, value))


    def perform_read_timing(disk, timeout, num=5):
        results = 0
        for i in range(num):
            cmd = params.get("device_cache_read_cmd") % disk
            (s, output) = session.cmd_status_output(cmd, timeout)
            if s != 0:
                raise error.TestFail("Fail to perform device/cache read"
                                     " timings \nOutput is: %s\n" % output)
            logging.info("Output of device/cache read timing check (%s of %s):"
                         % (i + 1, num))
            for line in output.strip().splitlines():
                logging.info(line)
            (result, unit) = re.findall("= *([0-9]*.+[0-9]*) ([a-zA-Z]*)",
                             output)[1]
            if unit == "kB":
                result = float(result)/1024.0
            results += float(result)
        return results/num


    vm = env.get_vm(params["main_vm"])
    vm.create()
    session = vm.wait_for_login(timeout=int(params.get("login_timeout", 360)))
    try:
        timeout = float(params.get("cmd_timeout", 60))
        cmd = params.get("get_disk_cmd")
        output = session.cmd(cmd)
        disk = output.strip()

        error.context("Setting hard disk to lower performance")
        cmd = params.get("low_status_cmd") % disk
        session.cmd(cmd, timeout)

        error.context("Checking hard disk keyval under lower performance "
                      "settings")
        check_setting_result(cmd, timeout)
        low_result = perform_read_timing(disk, timeout)
        logging.info("Average buffered disk read speed under low performance "
                     "settings: %.2f MB/sec" % low_result)

        error.context("Setting hard disk to higher performance")
        cmd = params.get("high_status_cmd") % disk
        session.cmd(cmd, timeout)

        error.context("Checking hard disk keyval under higher performance "
                      "settings")
        check_setting_result(cmd, timeout)
        high_result = perform_read_timing(disk, timeout)
        logging.info("Average buffered disk read speed under high performance "
                     "settings: %.2f MB/sec" % high_result)

        if not float(high_result) > float(low_result):
            raise error.TestFail("High performance setting does not "
                                 "increase read speed\n")

    finally:
        if session:
            session.close()
