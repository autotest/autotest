import time, os
from autotest_lib.client.bin import test, os_dep, utils
from autotest_lib.client.common_lib import error


class btreplay(test.test):
    version = 1

    # http://brick.kernel.dk/snaps/blktrace-git-latest.tar.gz
    def setup(self, tarball = 'blktrace-git-latest.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)

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
        self.job.require_gcc()
        self.ldlib = 'LD_LIBRARY_PATH=%s/deps/libaio/lib'%(self.autodir)
        self.results = []


    def run_once(self, dev="", devices="", extra_args='', tmpdir=None):
        # @dev: The device against which the trace will be replayed.
        #       e.g. "sdb" or "md_d1"
        # @devices: A space-separated list of the underlying devices
        #    which make up dev, e.g. "sdb sdc". You only need to set
        #    devices if dev is an MD, LVM, or similar device;
        #    otherwise leave it as an empty string.

        if not tmpdir:
            tmpdir = self.tmpdir

        os.chdir(self.srcdir)

        alldevs = "-d /dev/" + dev
        alldnames = dev
        for d in devices.split():
            alldevs += " -d /dev/" + d
            alldnames += " " + d

        # convert the trace (assumed to be in this test's base
        # directory) into btreplay's required format
        #
        # TODO: The test currently halts here as there is no trace in the
        # test's base directory.
        cmd = "./btreplay/btrecord -d .. -D %s %s" % (tmpdir, dev)
        self.results.append(utils.system_output(cmd, retain_output=True))

        # time a replay that omits "thinktime" between requests
        # (by use of the -N flag)
        cmd = self.ldlib + " /usr/bin/time ./btreplay/btreplay -d "+\
              tmpdir+" -N -W "+dev+" "+extra_args+" 2>&1"
        self.results.append(utils.system_output(cmd, retain_output=True))

        # trace a replay that reproduces inter-request delays, and
        # analyse the trace with btt to determine the average request
        # completion latency
        utils.system("./blktrace -D %s %s >/dev/null &" % (tmpdir, alldevs))
        cmd = self.ldlib + " ./btreplay/btreplay -d %s -W %s %s" %\
              (tmpdir, dev, extra_args)
        self.results.append(utils.system_output(cmd, retain_output=True))
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
        cmd = "./btt/btt -i %s/trace.bin" % tmpdir
        self.results.append(utils.system_output(cmd, retain_output=True))


    def postprocess(self):
        for n in range(len(self.results)):
            if self.results[n].strip() == "==================== All Devices ====================":
                words = self.results[n-2].split()
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
        for line in self.results:
            words = line.split()
            if len(words) < 3:
                continue
            if words[0] == 'Q2C':
                q2c = float(words[2])
                break

        self.write_perf_keyval({'time':elapsed, 'systime':systime,
                                'avg_q2c_latency':q2c})
