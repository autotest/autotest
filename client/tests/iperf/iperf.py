import os, re, socket, time, logging
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class iperf(test.test):
    version = 1

    # http://downloads.sourceforge.net/iperf/iperf-2.0.4.tar.gz
    def setup(self, tarball = 'iperf-2.0.4.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('./configure')
        utils.system('make')


    def initialize(self):
        self.job.require_gcc()

        self.SERVER_PORT = '5001'

        # The %%s is to add extra args later
        # We cannot use daemon mode because it is unreliable with
        # UDP transfers.
        self.server_path = "%s %%s&" % os.path.join(self.srcdir,
                                                    'src/iperf -s')
        # Add the servername and arguments later
        self.client_path = "%s %%s %%s" % os.path.join(self.srcdir,
                                                       'src/iperf -y c -c')

        self.results = []
        self.actual_times = []


    def run_once(self, server_ip, client_ip, role, udp=False,
                 bidirectional=False, test_time=10, stream_list=[1]):
        self.role = role
        self.udp = udp
        self.bidirectional = bidirectional
        self.test_time = test_time
        self.stream_list = stream_list

        server_tag = server_ip + '#iperf-server'
        client_tag = client_ip + '#iperf-client'
        all = [server_tag, client_tag]

        for num_streams in stream_list:
            if self.role == 'server':
                self.ip = socket.gethostbyname(server_ip)
                # Start server and synchronize on server-up
                self.server_start()
                try:
                    # Wait up to ten minutes for the server and client
                    # to reach this point
                    self.job.barrier(server_tag, 'start_%d' % num_streams,
                                     600).rendevous(*all)

                    # Stop the server when the client finishes
                    # Wait up to test_time + five minutes
                    self.job.barrier(server_tag, 'finish_%d' % num_streams,
                                     test_time+300).rendevous(*all)
                finally:
                    self.server_stop()

            elif role == 'client':
                self.ip = socket.gethostbyname(client_ip)
                # Wait up to ten minutes for the server and client
                # to reach this point
                self.job.barrier(client_tag, 'start_%d' % num_streams,
                                 600).rendevous(*all)
                self.client(server_ip, test_time, num_streams)

                # Wait up to 5 minutes for the server to also reach this point
                self.job.barrier(client_tag, 'finish_%d' % num_streams,
                                 300).rendevous(*all)
            else:
                raise error.TestError('invalid role specified')


    def server_start(self):
        args = ''
        if self.udp:
            args += '-u '

        utils.system('killall -9 iperf', ignore_status=True)
        self.results.append(utils.system_output(self.server_path % args,
                                                retain_output=True))


    def server_stop(self):
        utils.system('killall -9 iperf', ignore_status=True)


    def client(self, server_ip, test_time, num_streams):
        args = '-t %d -P %d ' % (test_time, num_streams)
        if self.udp:
            args += '-u '
        if self.bidirectional:
            args += '-d '

        cmd = self.client_path % (server_ip, args)
        try:
            t0 = time.time()
            self.results.append(utils.get_cpu_percentage(
                utils.system_output, cmd, timeout=test_time+60,
                retain_output=True))
            t1 = time.time()

            self.actual_times.append(t1 - t0)

        except error.CmdError, e:
            """ Catch errors due to timeout, but raise others
            The actual error string is:
              "Command did not complete within %d seconds"
            called in function join_bg_job in the file common_lib/utils.py

            Looking for 'within' is probably not the best way to do this but
            works for now"""

            if 'within' in e.additional_text:
                # Results are cpu%, output
                self.results.append((0, None))
                self.actual_times.append(1)
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

            for i, streams in enumerate(self.stream_list):
                attr = {'stream_count':streams}
                keyval = {}
                keyval['CPU_C'], output  = self.results[i]
                runs = {'Bandwidth_S2C':[], 'Bandwidth_C2S':[],
                        'Jitter_S2C':[], 'Jitter_C2S':[]}

                # Short circuit to handle errors due to client timeouts
                if output is None:
                    self.write_iteration_keyval(attr, keyval)
                    continue

                if self.udp:
                    regex = udp_regex
                    keys = udp_keys
                    # Ignore the first line
                    stdout = output.split('\n',1)[1]
                else:
                    regex = tcp_regex
                    keys = tcp_keys
                    stdout = output

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

                # Calculate sums assuming there are values
                for key in [k for k in runs if len(runs[k]) > 0]:
                    keyval[key] = sum(runs[key])

                # scale the bandwidth based on the actual time taken
                # by tests to run
                scale = self.test_time/self.actual_times[i]
                total_bw = 0
                for key in ['Bandwidth_S2C', 'Bandwidth_C2S']:
                    if len(runs[key]) > 0:
                        keyval[key] = keyval[key] * scale
                        total_bw = total_bw + keyval[key]

                keyval['Efficiency_C'] = total_bw/keyval['CPU_C']
                self.write_iteration_keyval(attr, keyval)
        else:
            # This test currently does not produce a keyval file on the
            # server side. This should be implemented eventually.
            logging.info(self.results)
