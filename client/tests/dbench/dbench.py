import os, re
from autotest_lib.client.bin import autotest_utils, test
from autotest_lib.client.common_lib import utils

class dbench(test.test):
    version = 1

    # http://samba.org/ftp/tridge/dbench/dbench-3.04.tar.gz
    def setup(self, tarball = 'dbench-3.04.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('./configure')
        utils.system('make')


    def execute(self, iterations = 1, dir = None, nprocs = None, args = ''):
        if not nprocs:
            nprocs = self.job.cpu_count()
        profilers = self.job.profilers
        args = args + ' -c '+self.srcdir+'/client.txt'
        if dir:
            args += ' -D ' + dir
        args += ' %s' % nprocs
        cmd = self.srcdir + '/dbench ' + args
        results = []
        if not profilers.only():
            for i in range(iterations):
                results.append(utils.system_output(cmd, retain_output=True))

        # Do a profiling run if necessary
        if profilers.present():
            profilers.start(self)
            results.append(utils.system_output(cmd, retain_output=True))
            profilers.stop(self)
            profilers.report(self)

        self.__format_results("\n".join(results))


    def __format_results(self, results):
        out = open(self.resultsdir + '/keyval', 'w')
        pattern = re.compile(r"Throughput (.*?) MB/sec (.*?) procs")
        for result in pattern.findall(results):
            print >> out, "throughput=%s\nprocs=%s\n" % result
        out.close()
