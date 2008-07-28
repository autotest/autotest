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
        self.server_path = "%s %%s &>/dev/null" % os.path.join(self.srcdir,
                                                     'src/iperf -s -D')
        self.client_path = os.path.join(self.srcdir, 'src/iperf -c')


    def execute(self, server_ip, client_ip, role, args=''):
        server_tag = server_ip + '#iperf-server'
        client_tag = client_ip + '#iperf-client'
        all = [server_tag, client_tag]

        job = self.job
        if role == 'server':
            # Start server and synchronize on server-up
            self.server_start(args)
            try:
                job.barrier(server_tag, 'server-up', 120).rendevous(*all)

                # Stop the server when the client finishes
                job.barrier(server_tag, 'client-done', 600).rendevous(*all)
            finally:
                self.server_stop()

        elif role == 'client':
            # Wait for server to start then run test
            job.barrier(client_tag, 'server-up', 120).rendevous(*all)
            self.client(server_ip, args)

            # Tell the server the client is done
            job.barrier(client_tag, 'client-done',  120).rendevous(*all)
        else:
            raise error.TestError('invalid role specified')


    def server_start(self, args):
        # we should really record the pid we forked off, but there
        # was no obvious way to run the daemon in the foreground.
        # Hacked it for now

        utils.system('killall iperf', ignore_status=True)
        print self.server_path % args
        utils.system(self.server_path % args)


    def server_stop(self):
        # this should really just kill the pid I forked, but ...
        utils.system('killall iperf')


    def client(self, server_ip, args):
        # run some client stuff
        utils.system('%s %s %s' % (self.client_path, server_ip, args))
