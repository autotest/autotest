import os, re, socket
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils, error


class iperf(test.test):
    version = 1

    # http://downloads.sourceforge.net/iperf/iperf-2.0.4.tar.gz
    def setup(self, tarball = 'iperf-2.0.4.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('./configure')
        utils.system('make')


    def initialize(self):
        self.job.require_gcc()

        self.SERVER_PORT = '5001'

        wrapper_path = os.path.join(self.job.toolsdir, 'proc_wrapper.py')

        # The %%s is to add extra args later
        # We cannot use daemon mode because it is unreliable with
        # UDP transfers.
        self.server_path = "%s %%s&" % os.path.join(self.srcdir,
                                                    'src/iperf -s')
        # Add the servername and arguments later
        client_path = "%s %%s %%s" % os.path.join(self.srcdir,
                                                       'src/iperf -y c -c')
        self.client_path = "%s %s" % (wrapper_path, client_path)

        self.results = []


    def run_once(self, server_ip, client_ip, role, udp=False,
                 bidirectional=False, test_time=10, stream_list=[1]):
        self.role = role
        self.udp = udp
        self.bidirectional = bidirectional
        self.stream_list = stream_list

        server_tag = server_ip + '#iperf-server'
        client_tag = client_ip + '#iperf-client'
        all = [server_tag, client_tag]

        for num_streams in stream_list:
            print "Run: #%d" % num_streams
            if self.role == 'server':
                self.ip = socket.gethostbyname(server_ip)
                # Start server and synchronize on server-up
                self.server_start()
                try:
                    # Wait up to two minutes for the server and client
                    # to reach this point
                    print "server start"
                    self.job.barrier(server_tag, 'start', 120).rendevous(*all)

                    # Stop the server when the client finishes
                    # Wait up to test_time + 5 seconds for the task to complete
                    print "servre finish"
                    self.job.barrier(server_tag, 'finish',
                                     test_time + 500).rendevous(*all)
                finally:
                    self.server_stop()

            elif role == 'client':
                self.ip = socket.gethostbyname(client_ip)
                # Wait up to two minutes for the server and client
                # to reach this point
                print "client stazrt"
                self.job.barrier(client_tag, 'start', 120).rendevous(*all)
                self.client(server_ip, test_time, num_streams)

                # Wait up to 5 seconds for the server to also reach this point
                print "client fnish"
                self.job.barrier(client_tag, 'finish', 5).rendevous(*all)
            else:
                raise error.TestError('invalid role specified')


    def server_start(self):
        # we should really record the pid we forked off, but there
        # was no obvious way to run the daemon in the foreground.
        # Hacked it for now

        args = ''
        if self.udp:
            args += '-u '

        utils.system('killall -9 iperf', ignore_status=True)
        self.results.append(utils.system_output(self.server_path % args,
                                                retain_output=True))


    def server_stop(self):
        # this should really just kill the pid I forked, but ...
        utils.system('killall -9 iperf', ignore_status=True)


    def client(self, server_ip, test_time, num_streams):
        args = '-t %d -P %d ' % (test_time, num_streams)
        if self.udp:
            args += '-u '
        if self.bidirectional:
            args += '-d '

        cmd = self.client_path % (server_ip, args)
        try:
            self.results.append(utils.system_output(cmd, timeout=test_time+5,
                                                    retain_output=True))
        except error.CmdError, e:
            """ Catch errors due to timeout, but raise others
            The actual error string is:
              "Command did not complete within %d seconds"
            called in function join_bg_job in the file common_lib/utils.py

            Looking for 'within' is probably not the best way to do this but
            works for now"""

            if 'within' in e.additional_text:
                print e.additional_text
                self.results.append(None)
            else:
                raise


    def postprocess(self):
        """The following patterns parse the following outputs:
        TCP -- bidirectional
        20080806120605,10.75.222.14,59744,10.75.222.13,5001,13,0.0-10.0,105054208,84029467
        20080806120605,10.75.222.14,5001,10.75.222.13,46112,12,0.0-10.0,1176387584,940172245
        CPU: 38.88% -- 85 samples

        UDP -- bidirectional
        20080807094252,10.75.222.14,32807,10.75.222.13,5001,4,0.0-3.0,395430,1048592
        20080807094252,10.75.222.14,5001,10.75.222.13,32809,3,0.0-3.0,395430,1048656,0.004,0,269,0.000,0
        20080807094252,10.75.222.13,5001,10.75.222.14,32807,4,0.0-3.0,395430,1048711,0.007,0,269,0.000,0
        CPU: 227.23% -- 90 samples

        The second two lines of the UDP pattern are the same as the TCP pattern
        with the exception that they add fields for jitter and datagram stats.
        """

        # Using join to keep < 80 chars
        tcp_pattern = ''.join(['(\d+),([0-9.]+),(\d+),([0-9.]+),(\d+),(\d+),',
                               '([0-9.]+)-([0-9.]+),(\d+),(\d+)'])
        udp_pattern = tcp_pattern + ',([0-9.]+),(\d+),(\d+),([0-9.]+),(\d+)'

        tcp_regex = re.compile(tcp_pattern)
        udp_regex = re.compile(udp_pattern)

        tcp_keys = ['date', 'local_ip', 'local_port', 'remote_ip',
                    'remote_port', 'id', 'start', 'end',
                    'bytes_transfered', 'bandwidth']
        udp_keys = tcp_keys[:]
        udp_keys.extend(['jitter', 'num_error_dgrams', 'num_dgrams',
                         'percent_error_dgrams', 'num_out_of_order_dgrams'])

        if self.role == 'client':
            if len(self.stream_list) != len(self.results):
                raise error.TestError('Mismatched number of results')

            keyval = {}
            runs = {'Bandwidth_S2C':[], 'Bandwidth_C2S':[],
                    'Jitter_S2C':[], 'Jitter_C2S':[]}

            # Iterate over each stream and add values to the keyval
            for i, streams in enumerate(self.stream_list):
                # Handle Errors due to client timeouts
                if self.results[i] == None:
                    for key in runs:
                        keyval['%s_%d' % (key, streams)] = 0
                        keyval['CPU_C_%d' % streams] = (
                            cpu_line.split(' ',2)[1][:-1])
                    continue

                if self.udp:
                    regex = udp_regex
                    keys = udp_keys
                    # Ignore the first line
                    stdout = self.results[i].split('\n',1)[1]
                else:
                    regex = tcp_regex
                    keys = tcp_keys
                    stdout = self.results[i]

                # This will not find the average lines because the 'id' field
                # is negative and doesn't match the patterns -- this is good
                for match in regex.findall(stdout):
                    stats = dict(zip(keys,match))

                    # Determine Flow Direction
                    if (stats['local_ip'] == self.ip and
                        stats['local_port'] == self.SERVER_PORT):
                        runs['Bandwidth_S2C'].append(int(stats['bandwidth']))
                        try:
                            runs['Jitter_S2C'].append(float(stats['jitter']))
                        except:
                            pass
                    else:
                        runs['Bandwidth_C2S'].append(int(stats['bandwidth']))
                        try:
                            runs['Jitter_C2S'].append(float(stats['jitter']))
                        except:
                            pass

                # Calculate Averages assuming there are values
                for key in [k for k in runs if len(runs[k]) > 0]:
                    keyval['%s_%d' % (key, streams)] = (sum(runs[key]) /
                                                        len(runs[key]))

                # Grab the CPU value from a line like:
                # CPU: 17.26% -- 27 samples
                cpu_line = stdout.split('\n')[-1]
                keyval['CPU_C_%d' % streams] = cpu_line.split(' ',2)[1][:-1]

            self.write_perf_keyval(keyval)
        else:
            print self.results
