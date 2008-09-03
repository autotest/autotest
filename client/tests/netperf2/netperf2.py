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

        self.valid_tests = ['TCP_STREAM', 'TCP_RR', 'TCP_CRR',
                            'UDP_STREAM', 'UDP_RR', 'UDP_CRR']
        self.results = []


    def run_once(self, server_ip, client_ip, role, test='TCP_STREAM',
                 test_time=10, stream_list=[1]):
        if test not in self.valid_tests:
            raise error.TestError('invalid test specified')
        self.role = role

        server_tag = server_ip + '#netperf-server'
        client_tag = client_ip + '#netperf-client'
        all = [server_tag, client_tag]


        for num_streams in stream_list:
            if role == 'server':
                self.server_start()
                try:
                    self.job.barrier(server_tag, 'start', 120).rendevous(*all)
                    self.job.barrier(server_tag, 'stop', 5400).rendevous(*all)
                finally:
                    self.server_stop()

            elif role == 'client':
                self.job.barrier(client_tag, 'start', 120).rendevous(*all)
                self.client(server_ip, test, test_time, num_streams)
                self.job.barrier(client_tag, 'stop',  30).rendevous(*all)
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
                utils.system_output_parallel,
                [cmd]*num_streams,
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
        print "Post Processing"
        print self.role
        print self.results
        print "End Post Processing"
