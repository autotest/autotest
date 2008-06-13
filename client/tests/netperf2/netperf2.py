import os
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils, error


class netperf2(test.test):
    version = 1

    # ftp://ftp.netperf.org/netperf/netperf-2.4.1.tar.gz
    def setup(self, tarball = 'netperf-2.4.1.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('./configure')
        utils.system('make')


    def initialize(self):
        # netserver doesn't detach properly from the console. When
        # it is run from ssh, this causes the ssh command not to
        # return even though netserver meant to be backgrounded.
        # This behavior is remedied by redirecting fd 0, 1 & 2
        self.server_path = ('%s &>/dev/null </dev/null'
                % os.path.join(self.srcdir, 'src/netserver'))
        self.client_path = os.path.join(self.srcdir, 'src/netperf')


    def execute(self, server_ip, client_ip, role, script='snapshot_script',
                                                                    args=''):
        server_tag = server_ip + '#netperf-server'
        client_tag = client_ip + '#netperf-client'
        all = [server_tag, client_tag]
        job = self.job
        if (role == 'server'):
            self.server_start()
            try:
                job.barrier(server_tag, 'start', 600).rendevous(*all)
                job.barrier(server_tag, 'stop', 3600).rendevous(*all)
            finally:
                self.server_stop()
        elif (role == 'client'):
            os.environ['NETPERF_CMD'] = self.client_path
            job.barrier(client_tag, 'start', 600).rendevous(*all)
            self.client(script, server_ip, args)
            job.barrier(client_tag, 'stop',  30).rendevous(*all)
        else:
            raise error.UnhandledError('invalid role specified')


    def server_start(self):
        # we should really record the pid we forked off, but there
        # was no obvious way to run the daemon in the foreground.
        # Hacked it for now
        utils.system('killall netserver', ignore_status=True)
        utils.system(self.server_path)


    def server_stop(self):
        # this should really just kill the pid I forked, but ...
        utils.system('killall netserver')


    def client(self, script, server_ip, args = 'CPU'):
        # run some client stuff
        stdout_path = os.path.join(self.resultsdir, script + '.stdout')
        stderr_path = os.path.join(self.resultsdir, script + '.stderr')
        self.job.stdout.tee_redirect(stdout_path)
        self.job.stderr.tee_redirect(stderr_path)

        script_path = os.path.join(self.srcdir, 'doc/examples', script)
        utils.system('%s %s %s' % (script_path, server_ip, args))

        self.job.stdout.restore()
        self.job.stderr.restore()
