import os, time, re, logging
from autotest_lib.client.bin import test, utils
from autotest_lib.client.bin.net import net_utils
from autotest_lib.client.common_lib import error

MPSTAT_IX = 0
NETPERF_IX = 1

class netperf2(test.test):
    version = 3

    # ftp://ftp.netperf.org/netperf/netperf-2.4.4.tar.gz
    def setup(self, tarball = 'netperf-2.4.4.tar.gz'):
        self.job.require_gcc()
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('patch -p0 < ../wait_before_data.patch')
        # Fixing up a compile issue under newer systems that have
        # CPU_SET_S defined on /usr/include/sched.h, backported from
        # upstream svn trunk
        utils.system('patch -p0 < ../fix_netperf_build.patch')
        utils.system('./configure')
        utils.system('make')
        utils.system('sync')


    def initialize(self):
        self.server_prog = '%s&' % os.path.join(self.srcdir, 'src/netserver')
        self.client_prog = '%s' % os.path.join(self.srcdir, 'src/netperf')
        self.valid_tests = ['TCP_STREAM', 'TCP_MAERTS', 'TCP_RR', 'TCP_CRR',
                            'TCP_SENDFILE', 'UDP_STREAM', 'UDP_RR']
        self.results = []
        self.actual_times = []
        self.netif = ''
        self.network = net_utils.network()
        self.network_utils = net_utils.network_utils()


    def run_once(self, server_ip, client_ip, role, test = 'TCP_STREAM',
                 test_time = 15, stream_list = [1], test_specific_args = '',
                 cpu_affinity = '', dev = '', bidi = False, wait_time = 5):
        """
        server_ip: IP address of host running netserver
        client_ip: IP address of host running netperf client(s)
        role: 'client' or 'server'
        test: one of TCP_STREAM, TCP_MEARTS, TCP_RR, TCP_CRR, TCP_SENDFILE,
            UDP_STREAM or UDP_RR
        test_time: time to run the test for in seconds
        stream_list: list of number of netperf streams to launch
        test_specific_args: Optional test specific args.  For example to set
            the request,response size for RR tests to 200,100, set it
            to: '-- -r 200,100'.  Or, to set the send buffer size of STREAM
            tests to 200, set it to: '-- -m 200'
        cpu_affinity: netperf/netserver processes will get taskset to the
            cpu_affinity.  cpu_affinity is specified as a bitmask in hex
            without the leading 0x.  For example, to run on CPUs 0 & 5,
            cpu_affinity needs to be '21'
        dev: device on which to run traffic on.  For example, to run on
            inteface eth1, set it to 'eth1'.
        bidi: bi-directional traffic.  This is supported for TCP_STREAM
            test only. The RR & CRR tests are bi-directional by nature.
        wait_time: Time to wait after establishing data/control connections
            but before sending data traffic.
        """
        if test not in self.valid_tests:
            raise error.TestError('invalid test specified')
        self.role = role
        self.test = test
        self.test_time = test_time
        self.wait_time = wait_time
        self.stream_list = stream_list
        self.bidi = bidi

        server_tag = server_ip + '#netperf-server'
        client_tag = client_ip + '#netperf-client'
        all = [server_tag, client_tag]

        # If a specific device has been requested, configure it.
        if dev:
            timeout = 60
            if role == 'server':
                self.configure_interface(dev, server_ip)
                self.ping(client_ip, timeout)
            else:
                self.configure_interface(dev, client_ip)
                self.ping(server_ip, timeout)

        for num_streams in stream_list:
            if role == 'server':
                self.server_start(cpu_affinity)
                try:
                    # Wait up to ten minutes for the client to reach this
                    # point.
                    self.job.barrier(server_tag, 'start_%d' % num_streams,
                                     600).rendezvous(*all)
                    # Wait up to test_time + 5 minutes for the test to
                    # complete
                    self.job.barrier(server_tag, 'stop_%d' % num_streams,
                                     test_time+300).rendezvous(*all)
                finally:
                    self.server_stop()

            elif role == 'client':
                # Wait up to ten minutes for the server to start
                self.job.barrier(client_tag, 'start_%d' % num_streams,
                                 600).rendezvous(*all)
                self.client(server_ip, test, test_time, num_streams,
                            test_specific_args, cpu_affinity)
                # Wait up to 5 minutes for the server to also reach this point
                self.job.barrier(client_tag, 'stop_%d' % num_streams,
                                 300).rendezvous(*all)
            else:
                raise error.TestError('invalid role specified')

        self.restore_interface()


    def configure_interface(self, dev, ip_addr):
        self.netif = net_utils.netif(dev)
        self.netif.up()
        if self.netif.get_ipaddr() != ip_addr:
            self.netif.set_ipaddr(ip_addr)


    def restore_interface(self):
        if self.netif:
            self.netif.restore()


    def server_start(self, cpu_affinity):
        utils.system('killall netserver', ignore_status=True)
        cmd = self.server_prog
        if cpu_affinity:
            cmd = 'taskset %s %s' % (cpu_affinity, cmd)

        self.results.append(utils.system_output(cmd, retain_output=True))


    def server_stop(self):
        utils.system('killall netserver', ignore_status=True)


    def client(self, server_ip, test, test_time, num_streams,
               test_specific_args, cpu_affinity):
        args = '-H %s -t %s -l %d' % (server_ip, test, test_time)
        if self.wait_time:
            args += ' -s %d ' % self.wait_time

        # Append the test specific arguments.
        if test_specific_args:
            args += ' ' + test_specific_args

        cmd = '%s %s' % (self.client_prog, args)

        if cpu_affinity:
            cmd = 'taskset %s %s' % (cpu_affinity, cmd)

        try:
            cmds = []

            # Get 5 mpstat samples. Since tests with large number of streams
            # take a long time to start up all the streams, we'll toss out the
            # first and last sample when recording results
            interval = max(1, test_time / 5)
            cmds.append('sleep %d && mpstat -P ALL %s 5' % (self.wait_time,
                                                            interval))

            # Add the netperf commands
            for i in xrange(num_streams):
                cmds.append(cmd)
                if self.bidi and test == 'TCP_STREAM':
                    cmds.append(cmd.replace('TCP_STREAM', 'TCP_MAERTS'))

            t0 = time.time()
            # Launch all commands in parallel
            out = utils.run_parallel(cmds, timeout=test_time + 500,
                                     ignore_status=True)
            t1 = time.time()

            self.results.append(out)
            self.actual_times.append(t1 - t0 - self.wait_time)
            # Log test output
            logging.info(out)

        except error.CmdError, e:
            """ Catch errors due to timeout, but raise others
            The actual error string is:
              "Command did not complete within %d seconds"
            called in function join_bg_job in the file common_lib/utils.py

            Looking for 'within' is probably not the best way to do this but
            works for now"""

            if ('within' in e.additional_text
                or 'non-zero' in e.additional_text):
                logging.debug(e.additional_text)
                self.results.append(None)
                self.actual_times.append(1)
            else:
                raise


    def postprocess(self):
        if self.role == 'client':
            # if profilers are enabled, the test gets runs twice
            if (len(self.stream_list) != len(self.results) and
               2*len(self.stream_list) != len(self.results)):
                raise error.TestError('Mismatched number of results')

            function = None
            keys = None

            # Each of the functions return tuples in which the keys define
            # what that item in the tuple represents
            if self.test in ['TCP_STREAM', 'TCP_MAERTS', 'TCP_SENDFILE']:
                function = self.process_tcp_stream
                keys = ('Throughput',)
            elif self.test == 'UDP_STREAM':
                function = self.process_udp_stream
                keys = ('Throughput', 'Errors')
            elif self.test in ['TCP_RR', 'TCP_CRR', 'UDP_RR']:
                function = self.process_request_response
                keys = ('Transfer_Rate',)
            else:
                raise error.TestError('Unhandled test')

            for i, streams in enumerate(self.stream_list):
                attr = {'stream_count':streams}
                keyval = {}
                temp_vals = []

                # Short circuit to handle errors due to client timeouts
                if not self.results[i]:
                    self.write_iteration_keyval(attr, keyval)
                    continue

                # Collect output of netperf sessions
                failed_streams_count = 0
                for result in self.results[i][NETPERF_IX:]:
                    if result.exit_status:
                        failed_streams_count += 1
                    else:
                        temp_vals.append(function(result.stdout))

                keyval['Failed_streams_count'] = failed_streams_count

                # Process mpstat output
                mpstat_out = self.results[i][MPSTAT_IX].stdout
                cpu_stats = self.network_utils.process_mpstat(mpstat_out, 5)
                keyval['CPU_C'] = 100 - cpu_stats['idle']
                keyval['CPU_C_SYS'] = cpu_stats['sys']
                keyval['CPU_C_HI'] = cpu_stats['irq']
                keyval['CPU_C_SI'] = cpu_stats['soft']
                keyval['INTRS_C'] = cpu_stats['intr/s']

                actual_time = self.actual_times[i]
                keyval['actual_time'] = actual_time
                logging.info('actual_time: %f', actual_time)

                # Compute the sum of elements returned from function which
                # represent the string contained in keys
                for j, key in enumerate(keys):
                    vals = [x[j] for x in temp_vals]
                    # scale result by the actual time taken
                    keyval[key] = sum(vals)

                # record 'Efficiency' as perf/CPU
                if keyval['CPU_C'] != 0:
                    keyval['Efficieny_C'] = keyval[keys[0]]/keyval['CPU_C']
                else:
                    keyval['Efficieny_C'] = keyval[keys[0]]

                self.write_iteration_keyval(attr, keyval)


    def process_tcp_stream(self, output):
        """Parses the following (works for both TCP_STREAM, TCP_MAERTS and
        TCP_SENDFILE) and returns a singleton containing throughput.

        TCP STREAM TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET to foo.bar.com \
        (10.10.10.3) port 0 AF_INET
        Recv   Send    Send
        Socket Socket  Message  Elapsed
        Size   Size    Size     Time     Throughput
        bytes  bytes   bytes    secs.    10^6bits/sec

        87380  16384  16384    2.00      941.28
        """

        return float(output.splitlines()[6].split()[4]),


    def process_udp_stream(self, output):
        """Parses the following and returns a touple containing throughput
        and the number of errors.

        UDP UNIDIRECTIONAL SEND TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET \
        to foo.bar.com (10.10.10.3) port 0 AF_INET
        Socket  Message  Elapsed      Messages
        Size    Size     Time         Okay Errors   Throughput
        bytes   bytes    secs            #      #   10^6bits/sec

        129024   65507   2.00         3673      0     961.87
        131072           2.00         3673            961.87
        """

        line_tokens = output.splitlines()[5].split()
        return float(line_tokens[5]), int(line_tokens[4])


    def process_request_response(self, output):
        """Parses the following which works for both rr (TCP and UDP) and crr
        tests and returns a singleton containing transfer rate.

        TCP REQUEST/RESPONSE TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET \
        to foo.bar.com (10.10.10.3) port 0 AF_INET
        Local /Remote
        Socket Size   Request  Resp.   Elapsed  Trans.
        Send   Recv   Size     Size    Time     Rate
        bytes  Bytes  bytes    bytes   secs.    per sec

        16384  87380  1        1       2.00     14118.53
        16384  87380
        """

        return float(output.splitlines()[6].split()[5]),


    def ping(self, ip, timeout):
        curr_time = time.time()
        end_time = curr_time + timeout
        while curr_time < end_time:
            if not os.system('ping -c 1 ' + ip):
                # Ping succeeded
                return
            # Ping failed. Lets sleep a bit and try again.
            time.sleep(5)
            curr_time = time.time()

        return
