import os, re
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class unixbench5(test.test):
    """
    This test measure system wide performance by running the following tests:
      - Dhrystone - focuses on string handling.
      - Whetstone - measure floating point operations.
      - Execl Throughput - measure the number of execl calls per second.
      - File Copy
      - Pipe throughput
      - Pipe-based context switching
      - Process creation - number of times a process can fork and reap
      - Shell Scripts - number of times a process can start and reap a script
      - System Call Overhead - estimates the cost of entering and leaving the
        kernel.

    @see: http://code.google.com/p/byte-unixbench/
    @author: Dale Curtis <dalecurtis@google.com>
    """
    version = 1


    def initialize(self):
        self.job.require_gcc()
        self.err = []


    def setup(self, tarball='unixbench-5.1.3.tgz'):
        """
        Compiles unixbench.

        @tarball: Path or URL to a unixbench tarball
        @see: http://byte-unixbench.googlecode.com/files/unixbench-5.1.3.tgz
        """
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('patch -p0 < ../Makefile.patch')
        utils.make()


    def run_once(self, args=''):
        vars = 'UB_TMPDIR="%s" UB_RESULTDIR="%s"' % (self.tmpdir,
                                                     self.resultsdir)
        os.chdir(self.srcdir)
        self.report_data = utils.system_output(vars + ' ./Run ' + args)
        self.results_path = os.path.join(self.resultsdir,
                                         'raw_output_%s' % self.iteration)
        utils.open_write_close(self.results_path, self.report_data)


    def cleanup(self):
        """
        Check error index list and throw TestError if necessary.
        """
        if self.err:
            e_msg = ("No measured results for output lines: %s\nOutput:%s" %
                     (" ".join(self.err), self.report_data))
            raise error.TestError(e_msg)


    def process_section(self, section, suffix):
        keyval = {}
        subsections = section.split('\n\n')

        if len(subsections) < 3:
            raise error.TestError('Invalid output format. Unable to parse')

        # Process the subsection containing performance results first.
        for index, line in enumerate(subsections[1].strip().split('\n')):
            # Look for problems first.
            if re.search('no measured results', line, flags=re.IGNORECASE):
                self.err.append(str(index + 1))

            # Every performance result line ends with 6 values, with the sixth
            # being the actual result. Make sure there are at least that words
            # in the line before processing.
            words = line.lower().split()
            if len(words) >= 6:
                key = re.sub('\W', '', '_'.join(words[:-6]))
                keyval[key + suffix] = words[-6]

        # The final score should be the last item in the third subsection.
        keyval['score' + suffix] = subsections[2].strip().split()[-1]

        self.write_perf_keyval(keyval)


    def postprocess_iteration(self):
        # Break up sections around dividing lines.
        sections = self.report_data.split('-'*72)

        # First section is junk to us, second has results for single CPU run.
        if len(sections) > 1:
            self.process_section(section=sections[1], suffix='')

            # Only machines with > 1 CPU will have a 3rd section.
            if len(sections) > 2:
                self.process_section(section=sections[2], suffix='_multi')
        else:
            raise error.TestError('Invalid output format. Unable to parse')


""" Here is a sample output:

   #    #  #    #  #  #    #          #####   ######  #    #   ####   #    #
   #    #  ##   #  #   #  #           #    #  #       ##   #  #    #  #    #
   #    #  # #  #  #    ##            #####   #####   # #  #  #       ######
   #    #  #  # #  #    ##            #    #  #       #  # #  #       #    #
   #    #  #   ##  #   #  #           #    #  #       #   ##  #    #  #    #
    ####   #    #  #  #    #          #####   ######  #    #   ####   #    #

   Version 5.1.2                      Based on the Byte Magazine Unix Benchmark

   Multi-CPU version                  Version 5 revisions by Ian Smith,
                                      Sunnyvale, CA, USA
   December 22, 2007                  johantheghost at yahoo period com


1 x Dhrystone 2 using register variables  1 2 3 4 5 6 7 8 9 10

1 x Double-Precision Whetstone  1 2 3 4 5 6 7 8 9 10

1 x Execl Throughput  1 2 3

1 x File Copy 1024 bufsize 2000 maxblocks  1 2 3

1 x File Copy 256 bufsize 500 maxblocks  1 2 3

1 x File Copy 4096 bufsize 8000 maxblocks  1 2 3

1 x Pipe Throughput  1 2 3 4 5 6 7 8 9 10

1 x Pipe-based Context Switching  1 2 3 4 5 6 7 8 9 10

1 x Process Creation  1 2 3

1 x System Call Overhead  1 2 3 4 5 6 7 8 9 10

1 x Shell Scripts (1 concurrent)  1 2 3

1 x Shell Scripts (8 concurrent)  1 2 3

2 x Dhrystone 2 using register variables  1 2 3 4 5 6 7 8 9 10

2 x Double-Precision Whetstone  1 2 3 4 5 6 7 8 9 10

2 x Execl Throughput  1 2 3

2 x File Copy 1024 bufsize 2000 maxblocks  1 2 3

2 x File Copy 256 bufsize 500 maxblocks  1 2 3

2 x File Copy 4096 bufsize 8000 maxblocks  1 2 3

2 x Pipe Throughput  1 2 3 4 5 6 7 8 9 10

2 x Pipe-based Context Switching  1 2 3 4 5 6 7 8 9 10

2 x Process Creation  1 2 3

2 x System Call Overhead  1 2 3 4 5 6 7 8 9 10

2 x Shell Scripts (1 concurrent)  1 2 3

2 x Shell Scripts (8 concurrent)  1 2 3

========================================================================
   BYTE UNIX Benchmarks (Version 5.1.2)

   System: localhost: GNU/Linux
   OS: GNU/Linux -- 2.6.32.26+drm33.12 -- #1 SMP Wed Jan 12 16:16:05 PST 2011
   Machine: i686 (GenuineIntel)
   Language: en_US.utf8 (charmap=, collate=)
   CPU 0: Intel(R) Atom(TM) CPU N455 @ 1.66GHz (3325.2 bogomips)
          Hyper-Threading, x86-64, MMX, Physical Address Ext, SYSENTER/SYSEXIT
   CPU 1: Intel(R) Atom(TM) CPU N455 @ 1.66GHz (3325.0 bogomips)
          Hyper-Threading, x86-64, MMX, Physical Address Ext, SYSENTER/SYSEXIT
   14:11:59 up 1 day,  1:10,  0 users,  load average: 0.47, 0.48, 0.51; runlevel

------------------------------------------------------------------------
Benchmark Run: Fri Jan 14 2011 14:11:59 - 14:41:26
2 CPUs in system; running 1 parallel copy of tests

Dhrystone 2 using register variables        2264000.6 lps   (10.0 s, 7 samples)
Double-Precision Whetstone                      507.0 MWIPS (10.1 s, 7 samples)
Execl Throughput                                796.7 lps   (30.0 s, 2 samples)
File Copy 1024 bufsize 2000 maxblocks        110924.1 KBps  (30.1 s, 2 samples)
File Copy 256 bufsize 500 maxblocks           32600.5 KBps  (30.1 s, 2 samples)
File Copy 4096 bufsize 8000 maxblocks        284236.5 KBps  (30.0 s, 2 samples)
Pipe Throughput                              301672.5 lps   (10.0 s, 7 samples)
Pipe-based Context Switching                  29475.3 lps   (10.0 s, 7 samples)
Process Creation                               3124.6 lps   (30.0 s, 2 samples)
Shell Scripts (1 concurrent)                   1753.0 lpm   (60.0 s, 2 samples)
Shell Scripts (8 concurrent)                    305.9 lpm   (60.1 s, 2 samples)
System Call Overhead                         592781.7 lps   (10.0 s, 7 samples)

System Benchmarks Index Values               BASELINE       RESULT    INDEX
Dhrystone 2 using register variables         116700.0    2264000.6    194.0
Double-Precision Whetstone                       55.0        507.0     92.2
Execl Throughput                                 43.0        796.7    185.3
File Copy 1024 bufsize 2000 maxblocks          3960.0     110924.1    280.1
File Copy 256 bufsize 500 maxblocks            1655.0      32600.5    197.0
File Copy 4096 bufsize 8000 maxblocks          5800.0     284236.5    490.1
Pipe Throughput                               12440.0     301672.5    242.5
Pipe-based Context Switching                   4000.0      29475.3     73.7
Process Creation                                126.0       3124.6    248.0
Shell Scripts (1 concurrent)                     42.4       1753.0    413.4
Shell Scripts (8 concurrent)                      6.0        305.9    509.8
System Call Overhead                          15000.0     592781.7    395.2
                                                                   ========
System Benchmarks Index Score                                         238.0

------------------------------------------------------------------------
Benchmark Run: Fri Jan 14 2011 14:41:26 - 15:09:23
2 CPUs in system; running 2 parallel copies of tests

Dhrystone 2 using register variables        3411919.6 lps   (10.0 s, 7 samples)
Double-Precision Whetstone                      964.3 MWIPS (10.1 s, 7 samples)
Execl Throughput                               2053.5 lps   (30.0 s, 2 samples)
File Copy 1024 bufsize 2000 maxblocks        158308.0 KBps  (30.0 s, 2 samples)
File Copy 256 bufsize 500 maxblocks           46249.5 KBps  (30.0 s, 2 samples)
File Copy 4096 bufsize 8000 maxblocks        389881.9 KBps  (30.0 s, 2 samples)
Pipe Throughput                              410193.1 lps   (10.0 s, 7 samples)
Pipe-based Context Switching                 113780.0 lps   (10.0 s, 7 samples)
Process Creation                               7609.0 lps   (30.0 s, 2 samples)
Shell Scripts (1 concurrent)                   2355.0 lpm   (60.0 s, 2 samples)
Shell Scripts (8 concurrent)                    308.1 lpm   (60.2 s, 2 samples)
System Call Overhead                        1057063.2 lps   (10.0 s, 7 samples)

System Benchmarks Index Values               BASELINE       RESULT    INDEX
Dhrystone 2 using register variables         116700.0    3411919.6    292.4
Double-Precision Whetstone                       55.0        964.3    175.3
Execl Throughput                                 43.0       2053.5    477.6
File Copy 1024 bufsize 2000 maxblocks          3960.0     158308.0    399.8
File Copy 256 bufsize 500 maxblocks            1655.0      46249.5    279.5
File Copy 4096 bufsize 8000 maxblocks          5800.0     389881.9    672.2
Pipe Throughput                               12440.0     410193.1    329.7
Pipe-based Context Switching                   4000.0     113780.0    284.5
Process Creation                                126.0       7609.0    603.9
Shell Scripts (1 concurrent)                     42.4       2355.0    555.4
Shell Scripts (8 concurrent)                      6.0        308.1    513.5
System Call Overhead                          15000.0    1057063.2    704.7
                                                                   ========
System Benchmarks Index Score                                         407.4

"""
