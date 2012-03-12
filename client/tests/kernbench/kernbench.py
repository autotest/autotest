import re, pickle, os, logging
from autotest_lib.client.bin import utils, test


class kernbench(test.test):
    version = 5

    def initialize(self):
        self.job.require_gcc()
        self.job.drop_caches_between_iterations = False


    def __init_tree(self, version=None):
        #
        # If we have a local copy of the 3.2.1 tarball use that
        # else let the kernel object use the defined mirrors
        # to obtain it.
        #
        # http://kernel.org/pub/linux/kernel/v3.x/linux-3.2.1.tar.bz2
        #
        if version:
            default_ver = version
        else:
            default_ver = '3.2.1'

        tarball = None
        for dir in (self.bindir, '/usr/local/src'):
            tar = 'linux-%s.tar.bz2' % default_ver
            path = os.path.join(dir, tar)
            if os.path.exists(path):
                tarball = path
                break
        if not tarball:
            tarball = default_ver

        # Do the extraction of the kernel tree
        kernel = self.job.kernel(tarball, self.outputdir, self.tmpdir)
        kernel.config(defconfig=True, logged=False)
        return kernel


    def warmup(self, threads=None, version=None):
        if threads:
            self.threads = threads
        else:
            self.threads = self.job.cpu_count()*2

        self.kernel = self.__init_tree(version)
        logging.info("Warmup run ...")
        logfile = os.path.join(self.debugdir, 'build_log')
        try:
            self.kernel.build_timed(self.threads, output=logfile)  # warmup run
        finally:
            if os.path.exists(logfile):
                utils.system("gzip -9 '%s'" % logfile, ignore_status=True)


    def run_once(self):
        logging.info("Performance run, iteration %d,"
                     " %d threads" % (self.iteration, self.threads))
        if self.iteration:
            timefile = 'time.%d' % self.iteration
        else:
            timefile = 'time.profile'
        self.timefile = os.path.join(self.resultsdir, timefile)
        self.kernel.build_timed(self.threads, self.timefile)


    def cleanup(self):
        self.kernel.clean(logged=False)    # Don't leave litter lying around


    def postprocess_iteration(self):
        os.chdir(self.resultsdir)
        utils.system("grep -h elapsed %s >> time" % self.timefile)

        results = open(self.timefile).read()
        (user, system, elapsed) = utils.extract_all_time_results(results)[0]
        self.write_perf_keyval({'user':user,
                                'system':system,
                                'elapsed':elapsed
                               })
