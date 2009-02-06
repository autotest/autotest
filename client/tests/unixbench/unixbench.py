import os, re
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class unixbench(test.test):
    version = 2

    def initialize(self):
        self.job.require_gcc()
        self.err = None


    # http://www.tux.org/pub/tux/niemi/unixbench/unixbench-4.1.0.tgz
    def setup(self, tarball = 'unixbench-4.1.0.tar.bz2'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('patch -p1 < ../unixbench.patch')
        utils.system('make')


    def run_once(self, args='', stepsecs=0):
        vars = ('TMPDIR=\"%s\" RESULTDIR=\"%s\"' %
               (self.tmpdir, self.resultsdir))
        if stepsecs:
            # change time per subtest from unixbench's defaults of
            #   10 secs for small tests, 30 secs for bigger tests
            vars += ' systime=%i looper=%i seconds=%i'\
                    ' dhrytime=%i arithtime=%i' \
                    % ((stepsecs,)*5)

        os.chdir(self.srcdir)
        utils.system(vars + ' ./Run ' + args)

        report_path = os.path.join(self.resultsdir, 'report')
        self.report_data = open(report_path).readlines()[9:]


    def cleanup(self):
        # check err string and possible throw
        if self.err is not None:
            raise error.TestError(self.err)


    def check_for_error(self, words):
        l = len(words)
        if l >= 3 and words[-3:l] == ['no', 'measured', 'results']:
            # found a problem so record it in err string
            key = '_'.join(words[:-3])
            if self.err is None:
                self.err = key
            else:
                self.err = self.err + " " + key
            return True
        else:
            return False


    def postprocess_iteration(self):
        keyval = {}
        for line in self.report_data:
            if not line.strip():
                break

            words = line.split()
            # look for problems first
            if self.check_for_error(words):
                continue

            # we should make sure that there are at least
            # 6 guys before we start accessing the array
            if len(words) >= 6:
                key = '_'.join(words[:-6])
                key = re.sub('\W', '', key)
                value = words[-6]
                keyval[key] = value
        for line in self.report_data:
            if 'FINAL SCORE' in line:
                keyval['score'] = line.split()[-1]
                break
        self.write_perf_keyval(keyval)


""" Here is a sample report file:

  BYTE UNIX Benchmarks (Version 4.1.0)
  System -- Linux adrianbg 2.6.18.5 #1 SMP Thu J  Start Benchmark Run: Tue Sep 1
   9 interactive users.
   21:03:50 up 5 days,  7:38,  9 users,  load average: 0.71, 0.40, 0.25
  lrwxrwxrwx 1 root root 4 Aug 15 09:53 /bin/sh -> bash
  /bin/sh: symbolic link to `bash'
  /dev/sda6            192149596  91964372  90424536  51% /home
Dhrystone 2 using register variables     7918001.7 lps   (10.0 secs, 10 samples)
System Call Overhead                     1427272.7 lps   (10.0 secs, 10 samples)
Process Creation                          11508.6 lps   (30.0 secs, 3 samples)
Execl Throughput                           4159.7 lps   (29.7 secs, 3 samples)
File Read 1024 bufsize 2000 maxblocks    1708109.0 KBps  (30.0 secs, 3 samples)
File Write 1024 bufsize 2000 maxblocks   788024.0 KBps  (30.0 secs, 3 samples)
File Copy 1024 bufsize 2000 maxblocks    452986.0 KBps  (30.0 secs, 3 samples)
File Read 256 bufsize 500 maxblocks      508752.0 KBps  (30.0 secs, 3 samples)
File Write 256 bufsize 500 maxblocks     214772.0 KBps  (30.0 secs, 3 samples)
File Copy 256 bufsize 500 maxblocks      143989.0 KBps  (30.0 secs, 3 samples)
File Read 4096 bufsize 8000 maxblocks    2626923.0 KBps  (30.0 secs, 3 samples)
File Write 4096 bufsize 8000 maxblocks   1175070.0 KBps  (30.0 secs, 3 samples)
File Copy 4096 bufsize 8000 maxblocks    793041.0 KBps  (30.0 secs, 3 samples)
Shell Scripts (1 concurrent)               4417.4 lpm   (60.0 secs, 3 samples)
Shell Scripts (8 concurrent)               1109.0 lpm   (60.0 secs, 3 samples)
Shell Scripts (16 concurrent)               578.3 lpm   (60.0 secs, 3 samples)
Arithmetic Test (type = short)           1843690.0 lps   (10.0 secs, 3 samples)
Arithmetic Test (type = int)             1873615.8 lps   (10.0 secs, 3 samples)
Arithmetic Test (type = long)            1888345.9 lps   (10.0 secs, 3 samples)
Arithmetic Test (type = float)           616260.3 lps   (10.0 secs, 3 samples)
Arithmetic Test (type = double)          615942.1 lps   (10.0 secs, 3 samples)
Arithoh                                  18864899.5 lps   (10.0 secs, 3 samples)
Dc: sqrt(2) to 99 decimal places         161726.0 lpm   (30.0 secs, 3 samples)
Recursion Test--Tower of Hanoi            89229.3 lps   (20.0 secs, 3 samples)


                     INDEX VALUES
TEST                                        BASELINE     RESULT      INDEX

Dhrystone 2 using register variables        116700.0  7918001.7      678.5
Double-Precision Whetstone                      55.0     1948.2      354.2
Execl Throughput                                43.0     4159.7      967.4
File Copy 1024 bufsize 2000 maxblocks         3960.0   452986.0     1143.9
File Copy 256 bufsize 500 maxblocks           1655.0   143989.0      870.0
File Copy 4096 bufsize 8000 maxblocks         5800.0   793041.0     1367.3
Pipe Throughput                              12440.0  1048491.9      842.8
Pipe-based Context Switching                  4000.0   300778.3      751.9
Process Creation                               126.0    11508.6      913.4
Shell Scripts (8 concurrent)                     6.0     1109.0     1848.3
System Call Overhead                         15000.0  1427272.7      951.5
                                                                 =========
     FINAL SCORE                                                     902.1
"""
