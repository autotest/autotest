import os, subprocess, re, commands, logging
from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error

class memory_api(test.test):
    version = 1

    def setup(self):
        os.mkdir(self.tmpdir)
        utils.system("%s %s -o %s" %
                      (utils.get_cc(),
                       os.path.join(self.bindir, "memory_api.c"),
                       os.path.join(self.tmpdir, "memory_api")))
        utils.system("%s %s -o %s" %
                      (utils.get_cc(),
                       os.path.join(self.bindir, "mremaps.c"),
                       os.path.join(self.tmpdir, "mremaps")))


    def initialize(self):
        self.job.require_gcc()


    def run_once(self, memsize = "1000000000", args=''):

        vma_re = re.compile("([0-9,a-f]+)-([0-9,a-f]+)")
        memory_re = re.compile("(\d+) bytes @(0x[0-9,a-f]+)")

        vma_max_shift = 0
        if os.access("/proc/sys/vm/vma_max_shift", os.R_OK):
            vma_max_shift = int(
                      open("/proc/sys/vm/vma_max_shift").read().rstrip())
        p1 = subprocess.Popen('%s/memory_api ' % self.tmpdir  + memsize,
                              shell=True, stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE)
        while p1.poll() is None:
            output = p1.stdout.readline().rstrip()
            m = memory_re.search(output)
            mem_start = 0
            mem_len = 0
            if m:
                mem_start = int(m.group(2), 16)
                mem_len = int(m.group(1))
            else:
                continue
            map_output = open("/proc/%s/maps_backing" % p1.pid).readlines()
            vma_count = 0
            vma_start = 0
            vma_len = 0
            expected_vma_count = 1
            for line in map_output:
                m = vma_re.search(line)
                if m:
                    vma_start = int("0x%s" % m.group(1),16)
                    vma_end = int("0x%s" % m.group(2),16)
                    if ((vma_start >= mem_start) and
                        (vma_start < (mem_start + mem_len))):
                        vma_count+=1

            if (('file' not in output) and (vma_max_shift != 0)):
                expected_vma_count = mem_len >> vma_max_shift
                if (mem_len % (1 << vma_max_shift)):
                    expected_vma_count += 1
            if expected_vma_count != vma_count:
                raise error.TestFail("VmaCountMismatch")
            logging.info("%s %s %d %d", hex(mem_start), hex(mem_len), vma_count,
                         expected_vma_count)
            if p1.poll() is None:
                p1.stdin.write("\n")
                p1.stdin.flush()

        if p1.poll() != 0:
            raise error.TestFail("Unexpected application abort")

        utils.system('%s/mremaps ' % self.tmpdir  + '100000000')
