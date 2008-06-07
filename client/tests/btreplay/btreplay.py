import time, os
from autotest_lib.client.bin import test, os_dep, autotest_utils
from autotest_lib.client.common_lib import error, utils


class btreplay(test.test):
    version = 1

    # http://brick.kernel.dk/snaps/blktrace-git-latest.tar.gz
    def setup(self, tarball = 'blktrace-git-latest.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        autotest_utils.extract_tarball_to_dir(tarball, self.srcdir)

        self.job.setup_dep(['libaio'])
        libs = '-L' + self.autodir + '/deps/libaio/lib -laio'
        cflags = '-I ' + self.autodir + '/deps/libaio/include'
        var_libs = 'LIBS="' + libs + '"'
        var_cflags  = 'CFLAGS="' + cflags + '"'
        self.make_flags = var_libs + ' ' + var_cflags

        os.chdir(self.srcdir)
        utils.system('patch -p1 < ../Makefile.patch')
        utils.system(self.make_flags + ' make')


    def initialize(self):
        self.ldlib = 'LD_LIBRARY_PATH=%s/deps/libaio/lib'%(self.autodir)


    def _run_btreplay(self, dev, devices, tmpdir, extra_args):
        alldevs = "-d /dev/" + dev
        alldnames = dev
        for d in devices.split():
            alldevs += " -d /dev/" + d
            alldnames += " " + d

        # convert the trace (assumed to be in this test's base
        # directory) into btreplay's required format
        utils.system("./btreplay/btrecord -d .. -D %s %s" % (tmpdir, dev))

        # time a replay that omits "thinktime" between requests
        # (by use of the -N flag)
        utils.system(self.ldlib + " /usr/bin/time ./btreplay/btreplay -d "+\
                tmpdir+" -N -W "+dev+" "+extra_args+" 2>&1")

        # trace a replay that reproduces inter-request delays, and
        # analyse the trace with btt to determine the average request
        # completion latency
        utils.system("./blktrace -D %s %s >/dev/null &" % (tmpdir, alldevs))
        utils.system(self.ldlib + " ./btreplay/btreplay -d %s -W %s %s" %
                                                   (tmpdir, dev, extra_args))
        utils.system("killall -INT blktrace")

        # wait until blktrace is really done
        slept = 0.0
        while utils.system("ps -C blktrace > /dev/null",
                     ignore_status=True) == 0:
            time.sleep(0.1)
            slept += 0.1
            if slept > 30.0:
                utils.system("killall -9 blktrace")
                raise error.TestError("blktrace failed to exit in 30 seconds")
        utils.system("./blkparse -q -D %s -d %s/trace.bin -O %s >/dev/null" %
                                                    (tmpdir, tmpdir, alldnames))
        utils.system("./btt/btt -i %s/trace.bin" % tmpdir)

    def execute(self, iterations = 1, dev="", devices="", extra_args = '',
                                                                tmpdir = None):
        # @dev: The device against which the trace will be replayed.
        #       e.g. "sdb" or "md_d1"
        # @devices: A space-separated list of the underlying devices
        #    which make up dev, e.g. "sdb sdc". You only need to set
        #    devices if dev is an MD, LVM, or similar device;
        #    otherwise leave it as an empty string.

        if not tmpdir:
            tmpdir = self.tmpdir

        os.chdir(self.srcdir)

        profilers = self.job.profilers
        if not profilers.only():
            for i in range(iterations):
                self._run_btreplay(dev, devices, tmpdir, extra_args)

        # Do a profiling run if necessary
        if profilers.present():
            profilers.start(self)
            self._run_btreplay(dev, devices, tmpdir, extra_args)
            profilers.stop(self)
            profilers.report(self)

        self.job.stdout.filehandle.flush()
        self.__format_results(open(self.debugdir + '/stdout').read())


    def __format_results(self, results):
        out = open(self.resultsdir + '/keyval', 'w')
        lines = results.split('\n')

        for n in range(len(lines)):
            if lines[n].strip() == "==================== All Devices ====================":
                words = lines[n-2].split()
                s = words[1].strip('sytem').split(':')
                e = words[2].strip('elapsd').split(':')
                break

        systime = 0.0
        for n in range(len(s)):
            i = (len(s)-1) - n
            systime += float(s[i]) * (60**n)
        elapsed = 0.0
        for n in range(len(e)):
            i = (len(e)-1) - n
            elapsed += float(e[i]) * (60**n)

        q2c = 0.0
        for line in lines:
            words = line.split()
            if len(words) < 3:
                continue
            if words[0] == 'Q2C':
                q2c = float(words[2])
                break


        print >> out, """\
time=%f
systime=%f
avg_q2c_latency=%f
""" % (elapsed, systime, q2c)
        out.close()
