import os, time, logging
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class netpipe(test.test):
    version = 1
    NP_FILE = '/tmp/np.out'

    # http://www.scl.ameslab.gov/netpipe/code/NetPIPE-3.7.1.tar.gz
    def setup(self, tarball='NetPIPE-3.7.1.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.system('make')


    def initialize(self):
        self.job.require_gcc()

        # Add arguments later
        self.server_path = '%s %%s' % os.path.join(self.srcdir, 'NPtcp')
        # Add server_ip and arguments later
        base_path = os.path.join(self.srcdir, 'NPtcp -h')
        self.client_path = '%s %%s -o %s %%s' % (base_path, self.NP_FILE)
        self.results = []

    def cleanup(self):
        # Just in case...
        utils.system('killall -9 NPtcp', ignore_status=True)


    def run_once(self, server_ip, client_ip, role, bidirectional=False,
                 buffer_size=None, upper_bound=None,
                 perturbation_size=3):
        self.role = role

        # Any arguments used must be the same on both the client and the server
        args = '-p %d ' % perturbation_size
        if bidirectional:
            args += '-2 '
        if buffer_size:
            args += '-b %d ' % buffer_size
        if upper_bound:
            args += '-u %d ' % upper_bound


        server_tag = server_ip + '#netpipe-server'
        client_tag = client_ip + '#netpipe-client'
        all = [server_tag, client_tag]

        if role == 'server':
            # Wait up to ten minutes for both to reach this point.
            self.job.barrier(server_tag, 'start', 600).rendezvous(*all)
            self.server_start(args)
            # Both the client and server should be closed so just to make
            # sure they are both at the same point wait at most five minutes.
            self.job.barrier(server_tag, 'stop', 300).rendezvous(*all)
        elif role == 'client':
            # Wait up to ten minutes for the server to start
            self.job.barrier(client_tag, 'start', 600).rendezvous(*all)
            # Sleep 10 seconds to make sure the server is started
            time.sleep(10)
            self.client(server_ip, args)
            # Wait up to five minutes for the server to also reach this point
            self.job.barrier(client_tag, 'stop', 300).rendezvous(*all)
        else:
            raise error.TestError('invalid role specified')


    def server_start(self, args):
        cmd = self.server_path % args
        self.results.append(utils.system_output(cmd, retain_output=True))


    def client(self, server_ip, args):
        cmd = self.client_path % (server_ip, args)

        try:
            # We don't care about the actual output since the important stuff
            # goes to self.NP_FILE
            utils.system(cmd)
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
            else:
                raise


    def postprocess(self):
        if self.role == 'client':
            try:
                output = open(self.NP_FILE)
                for line in output.readlines():
                    buff, bandwidth, latency = line.split()
                    attr = {'buffer_size':buff}
                    keyval = {'bandwidth':bandwidth, 'latency':latency}
                    self.write_iteration_keyval(attr, keyval)
            finally:
                output.close()
                os.remove(self.NP_FILE)
