import os
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils, error


class netperf2(test.test):
    version = 2

    # ftp://ftp.netperf.org/netperf/netperf-2.4.4.tar.gz
    def setup(self, tarball = 'netperf-2.4.4.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('./configure')
        utils.system('make')


    def initialize(self):
        self.job.require_gcc()

        self.server_path = '%s&' % os.path.join(self.srcdir,
                                                'src/netserver')
        # Add server_ip and arguments later
        self.client_path = '%s %%s %%s' % os.path.join(self.srcdir,
                                                       'src/netperf -H')

        self.valid_tests = ['TCP_STREAM', 'TCP_RR', 'TCP_CRR', 'TCP_SENDFILE',
                            'UDP_STREAM', 'UDP_RR']
        self.results = []


    def run_once(self, server_ip, client_ip, role, test='TCP_STREAM',
                 test_time=10, stream_list=[1]):
        if test not in self.valid_tests:
            raise error.TestError('invalid test specified')
        self.role = role
        self.test = test
        self.stream_list = stream_list

        server_tag = server_ip + '#netperf-server'
        client_tag = client_ip + '#netperf-client'
        all = [server_tag, client_tag]

        for num_streams in stream_list:
            if role == 'server':
                self.server_start()
                try:
                    # Wait up to ten minutes for the client to reach this
                    # point.
                    self.job.barrier(server_tag, 'start_%d' % num_streams,
                                     600).rendevous(*all)
                    # Wait up to test_time + 5 minutes for the test to
                    # complete
                    self.job.barrier(server_tag, 'stop_%d' % num_streams,
                                     test_time+300).rendevous(*all)
                finally:
                    self.server_stop()

            elif role == 'client':
                # Wait up to ten minutes for the server to start
                self.job.barrier(client_tag, 'start_%d' % num_streams,
                                 600).rendevous(*all)
                self.client(server_ip, test, test_time, num_streams)
                # Wait up to 5 minutes for the server to also reach this point
                self.job.barrier(client_tag, 'stop_%d' % num_streams,
                                 300).rendevous(*all)
            else:
                raise error.TestError('invalid role specified')


    def server_start(self):
        utils.system('killall netserver', ignore_status=True)
        self.results.append(utils.system_output(self.server_path,
                                                retain_output=True))


    def server_stop(self):
        utils.system('killall netserver', ignore_status=True)


    def client(self, server_ip, test, test_time, num_streams):
        args = '-t %s -l %d' % (test, test_time)
        cmd = self.client_path % (server_ip, args)

        try:
            self.results.append(utils.get_cpu_percentage(
                utils.system_output_parallel, [cmd]*num_streams,
                timeout=test_time+60, retain_output=True))
        except error.CmdError, e:
            """ Catch errors due to timeout, but raise others
            The actual error string is:
              "Command did not complete within %d seconds"
            called in function join_bg_job in the file common_lib/utils.py

            Looking for 'within' is probably not the best way to do this but
            works for now"""

            if ('within' in e.additional_text
                or 'non-zero' in e.additional_text):
                print e.additional_text
                # Results are cpu%, outputs
                self.results.append((0, None))
            else:
                raise


    def postprocess(self):
        if self.role == 'client':
            if len(self.stream_list) != len(self.results):
                raise error.TestError('Mismatched number of results')

            function = None
            keys = None

            # Each of the functions return tuples in which the keys define
            # what that item in the tuple represents
            if self.test in ['TCP_STREAM', 'TCP_SENDFILE']:
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

            # self.results is a list of tuples. The first element in each
            # tuple is the cpu utilization for that run, and the second
            # element is a list containing the output for each stream in that
            # run.
            for i, streams in enumerate(self.stream_list):
                attr = {'stream_count':streams}
                keyval = {}
                temp_vals = []
                keyval['CPU'], outputs  = self.results[i]

                # Short circuit to handle errors due to client timeouts
                if not outputs:
                    self.write_iteration_keyval(attr, keyval)
                    continue

                for result in outputs:
                    temp_vals.append(function(result))

                # Compute the sum of elements returned from function which
                # represent the string contained in keys
                for j, key in enumerate(keys):
                    vals = [x[j] for x in temp_vals]
                    keyval[key] = sum(vals)

                self.write_iteration_keyval(attr, keyval)


    def process_tcp_stream(self, output):
        """Parses the following (works for both TCP_STREAM and TCP_SENDFILE)
        and returns a singleton containing throughput.

        TCP STREAM TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET to kcqz13.prod.google.com (10.75.222.13) port 0 AF_INET
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

        UDP UNIDIRECTIONAL SEND TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET to kcqz13.prod.google.com (10.75.222.13) port 0 AF_INET
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

        TCP REQUEST/RESPONSE TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET to kcqz13.prod.google.com (10.75.222.13) port 0 AF_INET
        Local /Remote
        Socket Size   Request  Resp.   Elapsed  Trans.
        Send   Recv   Size     Size    Time     Rate
        bytes  Bytes  bytes    bytes   secs.    per sec

        16384  87380  1        1       2.00     14118.53
        16384  87380
        """

        return float(output.splitlines()[6].split()[5]),
