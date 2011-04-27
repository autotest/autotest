import logging, re
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils
from autotest_lib.client.virt import virt_test_utils, virt_utils, aexpect


def run_ethtool(test, params, env):
    """
    Test offload functions of ethernet device by ethtool

    1) Log into a guest.
    2) Initialize the callback of sub functions.
    3) Enable/disable sub function of NIC.
    4) Execute callback function.
    5) Check the return value.
    6) Restore original configuration.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.

    @todo: Not all guests have ethtool installed, so
        find a way to get it installed using yum/apt-get/
        whatever
    """
    def ethtool_get(f_type):
        feature_pattern = {
            'tx':  'tx.*checksumming',
            'rx':  'rx.*checksumming',
            'sg':  'scatter.*gather',
            'tso': 'tcp.*segmentation.*offload',
            'gso': 'generic.*segmentation.*offload',
            'gro': 'generic.*receive.*offload',
            'lro': 'large.*receive.*offload',
            }
        o = session.cmd("ethtool -k %s" % ethname)
        try:
            return re.findall("%s: (.*)" % feature_pattern.get(f_type), o)[0]
        except IndexError:
            logging.debug("Could not get %s status", f_type)


    def ethtool_set(f_type, status):
        """
        Set ethernet device offload status

        @param f_type: Offload type name
        @param status: New status will be changed to
        """
        logging.info("Try to set %s %s", f_type, status)
        if status not in ["off", "on"]:
            return False
        cmd = "ethtool -K %s %s %s" % (ethname, f_type, status)
        if ethtool_get(f_type) != status:
            try:
                session.cmd(cmd)
                return True
            except:
                return False
        if ethtool_get(f_type) != status:
            logging.error("Fail to set %s %s", f_type, status)
            return False
        return True


    def ethtool_save_params():
        logging.info("Save ethtool configuration")
        for i in supported_features:
            feature_status[i] = ethtool_get(i)


    def ethtool_restore_params():
        logging.info("Restore ethtool configuration")
        for i in supported_features:
            ethtool_set(i, feature_status[i])


    def compare_md5sum(name):
        logging.info("Compare md5sum of the files on guest and host")
        host_result = utils.hash_file(name, method="md5")
        try:
            o = session.cmd_output("md5sum %s" % name)
            guest_result = re.findall("\w+", o)[0]
        except IndexError:
            logging.error("Could not get file md5sum in guest")
            return False
        logging.debug("md5sum: guest(%s), host(%s)", guest_result, host_result)
        return guest_result == host_result


    def transfer_file(src="guest"):
        """
        Transfer file by scp, use tcpdump to capture packets, then check the
        return string.

        @param src: Source host of transfer file
        @return: Tuple (status, error msg/tcpdump result)
        """
        session2.cmd_output("rm -rf %s" % filename)
        dd_cmd = ("dd if=/dev/urandom of=%s bs=1M count=%s" %
                  (filename, params.get("filesize")))
        failure = (False, "Failed to create file using dd, cmd: %s" % dd_cmd)
        logging.info("Creating file in source host, cmd: %s", dd_cmd)
        tcpdump_cmd = "tcpdump -lep -s 0 tcp -vv port ssh"
        if src == "guest":
            tcpdump_cmd += " and src %s" % guest_ip
            copy_files_from = vm.copy_files_from
            try:
                session.cmd_output(dd_cmd, timeout=360)
            except aexpect.ShellCmdError, e:
                return failure
        else:
            tcpdump_cmd += " and dst %s" % guest_ip
            copy_files_from = vm.copy_files_to
            try:
                utils.system(dd_cmd)
            except error.CmdError, e:
                return failure

        # only capture the new tcp port after offload setup
        original_tcp_ports = re.findall("tcp.*:(\d+).*%s" % guest_ip,
                                      utils.system_output("/bin/netstat -nap"))
        for i in original_tcp_ports:
            tcpdump_cmd += " and not port %s" % i
        logging.debug("Listen using command: %s", tcpdump_cmd)
        session2.sendline(tcpdump_cmd)
        if not virt_utils.wait_for(
                           lambda:session.cmd_status("pgrep tcpdump") == 0, 30):
            return (False, "Tcpdump process wasn't launched")

        logging.info("Start to transfer file")
        try:
            copy_files_from(filename, filename)
        except virt_utils.SCPError, e:
            return (False, "File transfer failed (%s)" % e)
        logging.info("Transfer file completed")
        session.cmd("killall tcpdump")
        try:
            tcpdump_string = session2.read_up_to_prompt(timeout=60)
        except aexpect.ExpectError:
            return (False, "Fail to read tcpdump's output")

        if not compare_md5sum(filename):
            return (False, "Files' md5sum mismatched")
        return (True, tcpdump_string)


    def tx_callback(status="on"):
        s, o = transfer_file(src="guest")
        if not s:
            logging.error(o)
            return False
        return True


    def rx_callback(status="on"):
        s, o = transfer_file(src="host")
        if not s:
            logging.error(o)
            return False
        return True


    def so_callback(status="on"):
        s, o = transfer_file(src="guest")
        if not s:
            logging.error(o)
            return False
        logging.info("Check if contained large frame")
        # MTU: default IPv4 MTU is 1500 Bytes, ethernet header is 14 Bytes
        return (status == "on") ^ (len([i for i in re.findall(
                                   "length (\d*):", o) if int(i) > mtu]) == 0)


    def ro_callback(status="on"):
        s, o = transfer_file(src="host")
        if not s:
            logging.error(o)
            return False
        return True


    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    session = vm.wait_for_login(timeout=int(params.get("login_timeout", 360)))
    # Let's just error the test if we identify that there's no ethtool installed
    session.cmd("ethtool -h")
    session2 = vm.wait_for_login(timeout=int(params.get("login_timeout", 360)))
    mtu = 1514
    feature_status = {}
    filename = "/tmp/ethtool.dd"
    guest_ip = vm.get_address()
    ethname = virt_test_utils.get_linux_ifname(session, vm.get_mac_address(0))
    supported_features = params.get("supported_features")
    if supported_features:
        supported_features = supported_features.split()
    else:
        supported_features = []
    test_matrix = {
        # type:(callback,    (dependence), (exclude)
        "tx":  (tx_callback, (), ()),
        "rx":  (rx_callback, (), ()),
        "sg":  (tx_callback, ("tx",), ()),
        "tso": (so_callback, ("tx", "sg",), ("gso",)),
        "gso": (so_callback, (), ("tso",)),
        "gro": (ro_callback, ("rx",), ("lro",)),
        "lro": (rx_callback, (), ("gro",)),
        }
    ethtool_save_params()
    success = True
    try:
        for f_type in supported_features:
            callback = test_matrix[f_type][0]
            for i in test_matrix[f_type][2]:
                if not ethtool_set(i, "off"):
                    logging.error("Fail to disable %s", i)
                    success = False
            for i in [f for f in test_matrix[f_type][1]] + [f_type]:
                if not ethtool_set(i, "on"):
                    logging.error("Fail to enable %s", i)
                    success = False
            if not callback():
                raise error.TestFail("Test failed, %s: on", f_type)

            if not ethtool_set(f_type, "off"):
                logging.error("Fail to disable %s", f_type)
                success = False
            if not callback(status="off"):
                raise error.TestFail("Test failed, %s: off", f_type)
        if not success:
            raise error.TestError("Enable/disable offload function fail")
    finally:
        ethtool_restore_params()
        session.close()
        session2.close()
