import os, re, time, subprocess, sys
from autotest_lib.client.bin import test, autotest_utils
from autotest_lib.client.common_lib import utils


class parallel_dd(test.test):
    version = 1


    def raw_write(self):
        print "Timing raw write of %d megabytes" % self.megabytes
        sys.stdout.flush()
        dd = 'dd if=/dev/zero of=%s bs=4K count=%d' % \
                                        (self.fs.device, self.blocks)
        print dd
        utils.system(dd + ' > /dev/null')


    def raw_read(self):
        print "Timing raw read of %d megabytes" % self.megabytes
        sys.stdout.flush()
        dd = 'dd if=%s of=/dev/null bs=4K count=%d' % \
                                        (self.fs.device, self.blocks)
        print dd
        utils.system(dd + ' > /dev/null')


    def fs_write(self):
        p = []
        # Write out 'streams' files in parallel background tasks
        for i in range(self.streams):
            file = 'poo%d' % (i+1)
            file = os.path.join(self.job.tmpdir, file)
            dd = 'dd if=/dev/zero of=%s bs=4K count=%d' % \
                                    (file, self.blocks_per_file)
            print dd
            p.append(subprocess.Popen(dd + ' > /dev/null',
                                      shell=True))
        print "Waiting for %d streams" % self.streams
        # Wait for everyone to complete
        for i in range(self.streams):
            print "Waiting for %d" % p[i].pid
            sys.stdout.flush()
            os.waitpid(p[i].pid, 0)
        sys.stdout.flush()
        sys.stderr.flush()


    def fs_read(self):
        for i in range(self.streams):
            file = os.path.join(self.job.tmpdir, 'poo%d' % (i+1))
            dd = 'dd if=%s of=/dev/null bs=4K count=%d' % \
                                    (file, self.blocks_per_file)
            utils.system(dd + ' > /dev/null')


    def test(self, tag):
        start = time.time()
        self.raw_write()
        self.raw_write_rate = self.megabytes / (time.time() - start)

        start = time.time()
        self.raw_read()
        self.raw_read_rate = self.megabytes / (time.time() - start)

        self.fs.mkfs(self.fstype)
        self.fs.mount()
        start = time.time()
        try:
            self.fs_write()
        except:
            try:
                self.fs.unmount()
            finally:
                raise
        self.fs.unmount()
        self.fs_write_rate = self.megabytes / (time.time() - start)

        self.fs.mount()
        start = time.time()
        try:
            self.fs_read()
        except:
            try:
                self.fs.unmount()
            finally:
                raise
            read_in()
        self.fs_read_rate = self.megabytes / (time.time() - start)
        self.fs.unmount()


    def execute(self, fs, fstype = 'ext2', iterations = 2, megabytes = 1000, streams = 2):
        self.megabytes = megabytes
        self.blocks = megabytes * 256
        self.blocks_per_file = self.blocks / streams
        self.fs = fs
        self.fstype = fstype
        self.streams = streams

        print "Dumping %d megabytes across %d streams, %d times" % \
                                        (megabytes, streams, iterations)

        keyval = open(os.path.join(self.resultsdir, 'keyval'), 'w')
        for i in range(iterations):
            self.test('%d' % i)
            t = "raw_write=%d\n" % self.raw_write_rate
            t += "raw_read=%d\n" % self.raw_read_rate
            t += "fs_write=%d\n" % self.fs_write_rate
            t += "fs_read=%d\n" % self.fs_read_rate
            t += "\n"
            print t
            keyval.write(t)
        keyval.close()


        profilers = self.job.profilers
        if profilers.present():
            profilers.start(self)
            self.test('profile')
            profilers.stop(self)
            profilers.report(self)
