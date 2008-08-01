import os
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
        self.server_path = "%s %%s &" % os.path.join(self.srcdir,
                                                     'src/iperf -s -D')
        self.client_path = os.path.join(self.srcdir, 'src/iperf -c')
        self.results = []


    def run_once(self, server_ip, client_ip, role, udp=False,
                 bidirectional=False):
        self.role = role
        self.udp = udp
        self.bidirectional = bidirectional

        server_tag = server_ip + '#iperf-server'
        client_tag = client_ip + '#iperf-client'
        all = [server_tag, client_tag]

        job = self.job
        if role == 'server':
            # Start server and synchronize on server-up
            self.server_start()
            try:
                job.barrier(server_tag, 'server-up', 120).rendevous(*all)

                # Stop the server when the client finishes
                job.barrier(server_tag, 'client-done', 600).rendevous(*all)
            finally:
                self.server_stop()

        elif role == 'client':
            # Wait for server to start then run test
            job.barrier(client_tag, 'server-up', 120).rendevous(*all)
            self.client(server_ip)

            # Tell the server the client is done
            job.barrier(client_tag, 'client-done',  120).rendevous(*all)
        else:
            raise error.TestError('invalid role specified')


    def server_start(self):
        # we should really record the pid we forked off, but there
        # was no obvious way to run the daemon in the foreground.
        # Hacked it for now

        args = ''
        if self.udp:
            args += '-u'

        utils.system('killall -9 iperf', ignore_status=True)
        self.results.append(utils.system_output(self.server_path % args))


    def server_stop(self):
        # this should really just kill the pid I forked, but ...
        utils.system('killall -9 iperf')


    def client(self, server_ip):
        cmd = '%s %s' % (self.client_path, server_ip)
        if self.udp:
            cmd += ' -u'
        if self.bidirectional:
            cmd += ' -d'
        self.results.append(utils.system_output(cmd))

    def postprocess(self):
        # TODO: Actually process the results
        if self.role == 'client':
            self.write_perf_keyval({'output':self.results})
