import time, os, signal, re
from autotest_lib.client.bin import test, utils


class tbench(test.test):
    version = 2

    def initialize(self):
        self.job.require_gcc()


    # http://samba.org/ftp/tridge/dbench/dbench-3.04.tar.gz
    def setup(self, tarball = 'dbench-3.04.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.configure()
        utils.make()


    def run_once(self, nprocs = None, args = ''):
        # only supports combined server+client model at the moment
        # should support separate I suppose, but nobody uses it
        if not nprocs:
            nprocs = self.job.cpu_count()
        args = args + ' %s' % nprocs

        pid = os.fork()
        if pid:                         # parent
            time.sleep(1)
            client = self.srcdir + '/client.txt'
            args = '-c ' + client + ' ' + '%s' % args
            cmd = os.path.join(self.srcdir, "tbench") + " " + args
            # Standard output is verbose and merely makes our debug logs huge
            # so we don't retain it.  It gets parsed for the results.
            self.results = utils.run(cmd, stderr_tee=utils.TEE_TO_LOGS).stdout
            os.kill(pid, signal.SIGTERM)    # clean up the server
        else:                           # child
            server = self.srcdir + '/tbench_srv'
            os.execlp(server, server)


    def postprocess_iteration(self):
        pattern = re.compile(r"Throughput (.*?) MB/sec (.*?) procs")
        (throughput, procs) = pattern.findall(self.results)[0]
        self.write_perf_keyval({'throughput':throughput, 'procs':procs})
