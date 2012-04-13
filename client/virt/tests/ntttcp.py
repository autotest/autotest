import logging, os, glob, re, commands
from autotest.client.common_lib import error
from autotest.client.common_lib import utils
from autotest.client.virt import virt_utils, aexpect, virt_test_utils

_receiver_ready = False

def run_ntttcp(test, params, env):
    """
    Run NTttcp on Windows guest

    1) Install NTttcp in server/client side by Autoit
    2) Start NTttcp in server/client side
    3) Get test results

    @param test: kvm test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    login_timeout = int(params.get("login_timeout", 360))
    timeout = int(params.get("timeout"))
    results_path = os.path.join(test.resultsdir,
                                'raw_output_%s' % test.iteration)
    platform = "x86"
    if params.get("platform") == "64":
        platform = "x64"
    buffers = params.get("buffers").split()
    buf_num = params.get("buf_num", 200000)
    session_num = params.get("session_num")

    vm_sender = env.get_vm(params["main_vm"])
    vm_sender.verify_alive()
    vm_receiver = None
    receiver_addr = params.get("receiver_address")

    logging.debug(utils.system("numactl --hardware", ignore_status=True))
    logging.debug(utils.system("numactl --show", ignore_status=True))
    # pin guest vcpus/memory/vhost threads to last numa node of host by default
    if params.get('numa_node'):
        numa_node = int(params.get('numa_node'))
        node = virt_utils.NumaNode(numa_node)
        virt_test_utils.pin_vm_threads(vm_sender, node)

    if not receiver_addr:
        vm_receiver = env.get_vm("vm2")
        vm_receiver.verify_alive()
        try:
            sess = None
            sess = vm_receiver.wait_for_login(timeout=login_timeout)
            receiver_addr = vm_receiver.get_address()
            if not receiver_addr:
                raise error.TestError("Can't get receiver(%s) ip address" %
                                      vm_sender.name)
            if params.get('numa_node'):
                virt_test_utils.pin_vm_threads(vm_receiver, node)
        finally:
            if sess:
                sess.close()

    @error.context_aware
    def install_ntttcp(session):
        """ Install ntttcp through a remote session """
        logging.info("Installing NTttcp ...")
        try:
            # Don't install ntttcp if it's already installed
            error.context("NTttcp directory already exists")
            session.cmd(params.get("check_ntttcp_cmd"))
        except aexpect.ShellCmdError, e:
            ntttcp_install_cmd = params.get("ntttcp_install_cmd")
            error.context("Installing NTttcp on guest")
            session.cmd(ntttcp_install_cmd % (platform, platform), timeout=200)

    def receiver():
        """ Receive side """
        logging.info("Starting receiver process on %s", receiver_addr)
        if vm_receiver:
            session = vm_receiver.wait_for_login(timeout=login_timeout)
        else:
            username = params.get("username", "")
            password = params.get("password", "")
            prompt = params.get("shell_prompt", "[\#\$]")
            linesep = eval("'%s'" % params.get("shell_linesep", r"\n"))
            client = params.get("shell_client")
            port = int(params.get("shell_port"))
            log_filename = ("session-%s-%s.log" % (receiver_addr,
                            virt_utils.generate_random_string(4)))
            session = virt_utils.remote_login(client, receiver_addr, port,
                                             username, password, prompt,
                                             linesep, log_filename, timeout)
            session.set_status_test_command("echo %errorlevel%")
        install_ntttcp(session)
        ntttcp_receiver_cmd = params.get("ntttcp_receiver_cmd")
        global _receiver_ready
        f = open(results_path + ".receiver", 'a')
        for b in buffers:
            virt_utils.wait_for(lambda: not _wait(), timeout)
            _receiver_ready = True
            rbuf = params.get("fixed_rbuf", b)
            cmd = ntttcp_receiver_cmd % (session_num, receiver_addr, rbuf, buf_num)
            r = session.cmd_output(cmd, timeout=timeout,
                                   print_func=logging.debug)
            f.write("Send buffer size: %s\n%s\n%s" % (b, cmd, r))
        f.close()
        session.close()

    def _wait():
        """ Check if receiver is ready """
        global _receiver_ready
        if _receiver_ready:
            return _receiver_ready
        return False

    def sender():
        """ Send side """
        logging.info("Sarting sender process ...")
        session = vm_sender.wait_for_login(timeout=login_timeout)
        install_ntttcp(session)
        ntttcp_sender_cmd = params.get("ntttcp_sender_cmd")
        f = open(results_path + ".sender", 'a')
        try:
            global _receiver_ready
            for b in buffers:
                cmd = ntttcp_sender_cmd % (session_num, receiver_addr, b, buf_num)
                # Wait until receiver ready
                virt_utils.wait_for(_wait, timeout)
                r = session.cmd_output(cmd, timeout=timeout,
                                       print_func=logging.debug)
                _receiver_ready = False
                f.write("Send buffer size: %s\n%s\n%s" % (b, cmd, r))
        finally:
            f.close()
            session.close()

    def parse_file(resultfile):
        """ Parse raw result files and generate files with standard format """
        file = open(resultfile, "r")
        list= []
        found = False
        for line in file.readlines():
            o = re.findall("Send buffer size: (\d+)", line)
            if o:
                buffer = o[0]
            if "Total Throughput(Mbit/s)" in line:
                found = True
            if found:
                fields = line.split()
                if len(fields) == 0:
                    continue
                try:
                    [float(i) for i in fields]
                    list.append([buffer, fields[-1]])
                except ValueError:
                    continue
                found = False
        return list

    try:
        bg = utils.InterruptedThread(receiver, ())
        bg.start()
        if bg.isAlive():
            sender()
            bg.join(suppress_exception=True)
        else:
            raise error.TestError("Can't start backgroud receiver thread")
    finally:
        for i in glob.glob("%s.receiver" % results_path):
            f = open("%s.RHS" % results_path, "w")
            raw = "  buf(k)| throughput(Mbit/s)"
            logging.info(raw)
            f.write(raw + "\n")
            for j in parse_file(i):
                raw = "%8s| %8s" % (j[0], j[1])
                logging.info(raw)
                f.write(raw + "\n")
            f.close()
