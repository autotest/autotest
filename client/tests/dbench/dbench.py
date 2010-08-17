import os, re

from autotest_lib.client.bin import utils, test

class dbench(test.test):
    version = 3

    # http://samba.org/ftp/tridge/dbench/dbench-3.04.tar.gz
    def setup(self, tarball='dbench-3.04.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('patch -p1 < ../dbench_startup.patch')
        utils.configure()
        utils.make()


    def initialize(self):
        self.job.require_gcc()
        self.results = []
        self.dbench = os.path.join(self.srcdir, 'dbench')


    def run_once(self, dir='.', nprocs=None, seconds=600, args=''):
        if not nprocs:
            nprocs = self.job.cpu_count()
        loadfile = os.path.join(self.srcdir, 'client.txt')
        cmd = '%s %s %s -D %s -c %s -t %d' % (self.dbench, nprocs, args,
                                              dir, loadfile, seconds)
        self.results = utils.system_output(cmd, retain_output=True)


    def postprocess_iteration(self):
        pattern = re.compile(r"Throughput (.*?) MB/sec (.*?) procs")
        (throughput, procs) = pattern.findall(self.results)[0]
        self.write_perf_keyval({'throughput':throughput, 'procs':procs})
