import logging, os, commands, sys, threading, re, glob
from autotest.client.shared import error
from autotest.client import utils
from autotest.client.virt import aexpect, virt_utils
from autotest.client.virt import virt_test_utils
from autotest.server.hosts.ssh_host import SSHHost

def run_netperf(test, params, env):
    """
    Network stress test with netperf.

    1) Boot up VM(s), setup SSH authorization between host
       and guest(s)/external host
    2) Prepare the test environment in server/client/host
    3) Execute netperf tests, collect and analyze the results

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    login_timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=login_timeout)
    if params.get("rh_perf_envsetup_script"):
        virt_test_utils.service_setup(vm, session, test.virtdir)
    server = vm.get_address()
    server_ctl = vm.get_address(1)
    session.close()

    logging.debug(commands.getoutput("numactl --hardware"))
    logging.debug(commands.getoutput("numactl --show"))
    # pin guest vcpus/memory/vhost threads to last numa node of host by default
    if params.get('numa_node'):
        numa_node = int(params.get('numa_node'))
        node = virt_utils.NumaNode(numa_node)
        virt_test_utils.pin_vm_threads(vm, node)

    if "vm2" in params["vms"]:
        vm2 = env.get_vm("vm2")
        vm2.verify_alive()
        session2 = vm2.wait_for_login(timeout=login_timeout)
        if params.get("rh_perf_envsetup_script"):
            virt_test_utils.service_setup(vm2, session2, test.virtdir)
        client = vm2.get_address()
        session2.close()
        if params.get('numa_node'):
            virt_test_utils.pin_vm_threads(vm2, node)

    if params.get("client"):
        client = params["client"]
    if params.get("host"):
        host = params["host"]
    else:
        cmd = "ifconfig %s|awk 'NR==2 {print $2}'|awk -F: '{print $2}'"
        host = commands.getoutput(cmd % params["bridge"])

    shell_port = int(params["shell_port"])
    password = params["password"]
    username = params["username"]

    def env_setup(ip):
        logging.debug("Setup env for %s" % ip)
        SSHHost(ip, user=username, port=shell_port, password=password)
        ssh_cmd(ip, "service iptables stop")
        ssh_cmd(ip, "echo 1 > /proc/sys/net/ipv4/conf/all/arp_ignore")

        netperf_dir = os.path.join(os.environ['AUTODIR'], "tests/netperf2")
        for i in params.get("netperf_files").split():
            virt_utils.scp_to_remote(ip, shell_port, username, password,
                                     "%s/%s" % (netperf_dir, i), "/tmp/")
        ssh_cmd(ip, params.get("setup_cmd"))

    logging.info("Prepare env of server/client/host")

    env_setup(server_ctl)
    env_setup(client)
    env_setup(host)
    logging.info("Start netperf testing ...")
    start_test(server, server_ctl, host, client, test.resultsdir,
               l=int(params.get('l')),
               sessions_rr=params.get('sessions_rr'),
               sessions=params.get('sessions'),
               sizes_rr=params.get('sizes_rr'),
               sizes=params.get('sizes'),
               protocols=params.get('protocols'),
               ver_cmd=params.get('ver_cmd', "rpm -q qemu-kvm"))


def start_test(server, server_ctl, host, client, resultsdir, l=60,
               sessions_rr="50 100 250 500", sessions="1 2 4",
               sizes_rr="64 256 512 1024 2048",
               sizes="64 256 512 1024 2048 4096",
               protocols="TCP_STREAM TCP_MAERTS TCP_RR", ver_cmd=None):
    """
    Start to test with different kind of configurations

    @param server: netperf server ip for data connection
    @param server_ctl: ip to control netperf server
    @param host: localhost ip
    @param client: netperf client ip
    @param resultsdir: directory to restore the results
    @param l: test duration
    @param sessions_rr: sessions number list for RR test
    @param sessions: sessions number list
    @param sizes_rr: request/response sizes (TCP_RR, UDP_RR)
    @param sizes: send size (TCP_STREAM, UDP_STREAM)
    @param protocols: test type
    """

    def parse_file(file_prefix, raw=""):
        """ Parse result files and reture throughput total """
        thu = 0
        for file in glob.glob("%s.*.nf" % file_prefix):
            o = commands.getoutput("cat %s |tail -n 1" % file)
            try:
                thu += float(o.split()[raw])
            except:
                logging.debug(commands.getoutput("cat %s.*" % file_prefix))
                return -1
        return thu

    fd = open("%s/netperf-result.RHS" % resultsdir, "w")
    fd.write("#ver# %s\n#ver# host kernel: %s\n#ver# guest kernel:%s\n" % (
             commands.getoutput(ver_cmd),
             os.uname()[2], ssh_cmd(server_ctl, "uname -r")))
    desc = """#desc# The tests are %s seconds sessions of "Netperf". 'throughput' was taken from netperf's report.
#desc# other measurements were taken on the host.
#desc# How to read the results:
#desc# - The Throughput is measured in Mbit/sec.
#desc# - io_exit: io exits of KVM.
#desc# - irq_inj: irq injections of KVM.
#desc#
""" % (l)
    fd.write(desc)

    for protocol in protocols.split():
        logging.info(protocol)
        fd.write("Category:" + protocol+ "\n")
        row = "%5s|%8s|%10s|%6s|%9s|%10s|%10s|%12s|%12s|%9s|%8s|%8s|%10s|%10s" \
              "|%11s|%10s" % ("size", "sessions", "throughput", "%CPU",
              "thr/%CPU", "#tx-pkts", "#rx-pkts", "#tx-byts", "#rx-byts",
              "#re-trans", "#tx-intr", "#rx-intr", "#io_exit", "#irq_inj",
              "#tpkt/#exit", "#rpkt/#irq")
        logging.info(row)
        fd.write(row + "\n")
        if (protocol == "TCP_RR"):
            sessions_test = sessions_rr.split()
            sizes_test = sizes_rr.split()
        else:
            sessions_test = sessions.split()
            sizes_test = sizes.split()
        for i in sizes_test:
            for j in sessions_test:
                if (protocol == "TCP_RR"):
                    ret = launch_client(1, server, server_ctl, host, client, l,
                    "-t %s -v 0 -P -0 -- -r %s,%s -b %s" % (protocol, i, i, j))
                    thu = parse_file("/tmp/netperf.%s" % ret['pid'], 0)
                else:
                    ret = launch_client(j, server, server_ctl, host, client, l,
                                     "-C -c -t %s -- -m %s" % (protocol, i))
                    thu = parse_file("/tmp/netperf.%s" % ret['pid'], 4)
                cpu = 100 - float(ret['mpstat'].split()[10])
                normal = thu / cpu
                pkt_rx_irq = float(ret['rx_pkts']) / float(ret['irq_inj'])
                pkt_tx_exit = float(ret['tx_pkts']) / float(ret['io_exit'])
                row = "%5d|%8d|%10.2f|%6.2f|%9.2f|%10d|%10d|%12d|%12d|%9d" \
                      "|%8d|%8d|%10d|%10d|%11.2f|%10.2f" % (int(i), int(j),
                      thu, cpu, normal, ret['tx_pkts'], ret['rx_pkts'],
                      ret['tx_byts'], ret['rx_byts'], ret['re_pkts'],
                      ret['tx_intr'], ret['rx_intr'], ret['io_exit'],
                      ret['irq_inj'], pkt_tx_exit, pkt_rx_irq)
                logging.info(row)
                fd.write(row + "\n")
                fd.flush()
                logging.debug("Remove temporary files")
                commands.getoutput("rm -f /tmp/netperf.%s.*.nf" % ret['pid'])
    fd.close()


def ssh_cmd(ip, cmd, user="root"):
    """
    Execute remote command and return the output

    @param ip: remote machine IP
    @param cmd: executed command
    @param user: username
    """
    return utils.system_output('ssh -o StrictHostKeyChecking=no -o '
    'UserKnownHostsFile=/dev/null %s@%s "%s"' % (user, ip, cmd))


def launch_client(sessions, server, server_ctl, host, client, l, nf_args):
    """ Launch netperf clients """

    client_path="/tmp/netperf-2.4.5/src/netperf"
    server_path="/tmp/netperf-2.4.5/src/netserver"
    ssh_cmd(server_ctl, "pidof netserver || %s" % server_path)
    ncpu = ssh_cmd(server_ctl, "cat /proc/cpuinfo |grep processor |wc -l")

    def count_interrupt(name):
        """
        @param name: the name of interrupt, such as "virtio0-input"
        """
        intr = 0
        stat = ssh_cmd(server_ctl, "cat /proc/interrupts |grep %s" % name)
        for cpu in range(int(ncpu)):
            intr += int(stat.split()[cpu+1])
        return intr

    def get_state():
        for i in ssh_cmd(server_ctl, "ifconfig").split("\n\n"):
            if server in i:
                nrx = int(re.findall("RX packets:(\d+)", i)[0])
                ntx = int(re.findall("TX packets:(\d+)", i)[0])
                nrxb = int(re.findall("RX bytes:(\d+)", i)[0])
                ntxb = int(re.findall("TX bytes:(\d+)", i)[0])
        nre = int(ssh_cmd(server_ctl, "grep Tcp /proc/net/snmp|tail -1"
                 ).split()[12])
        nrx_intr = count_interrupt("virtio0-input")
        ntx_intr = count_interrupt("virtio0-output")
        io_exit = int(ssh_cmd(host, "cat /sys/kernel/debug/kvm/io_exits"))
        irq_inj = int(ssh_cmd(host, "cat /sys/kernel/debug/kvm/irq_injections"))
        return [nrx, ntx, nrxb, ntxb, nre, nrx_intr, ntx_intr, io_exit, irq_inj]

    def netperf_thread(i):
        output = ssh_cmd(client, "numactl --hardware")
        n = int(re.findall("available: (\d+) nodes", output)[0]) - 1
        cmd = "numactl --cpunodebind=%s --membind=%s %s -H %s -l %s %s" % \
                                    (n, n, client_path, server, l, nf_args)
        output = ssh_cmd(client, cmd)
        f = file("/tmp/netperf.%s.%s.nf" % (pid, i), "w")
        f.write(output)
        f.close()

    start_state = get_state()
    pid = str(os.getpid())
    threads = []
    for i in range(int(sessions)):
        t = threading.Thread(target=netperf_thread, kwargs={"i": i})
        threads.append(t)
        t.start()
    ret = {}
    ret['pid'] = pid
    ret['mpstat'] = ssh_cmd(host, "mpstat 1 %d |tail -n 1" % (l - 1))
    for t in threads:
        t.join()

    end_state = get_state()
    items = ['rx_pkts', 'tx_pkts', 'rx_byts', 'tx_byts', 're_pkts',
             'rx_intr', 'tx_intr', 'io_exit', 'irq_inj']
    for i in range(len(items)):
        ret[items[i]] = end_state[i] - start_state[i]
    return ret
