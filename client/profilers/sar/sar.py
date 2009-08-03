"""
Sets up a subprocess to run sar from the sysstat suite

Default options:
sar -A -f
"""


import os, shutil, subprocess
from autotest_lib.client.bin import utils, profiler


class sar(profiler.profiler):
    version = 1

    def initialize(self, interval = 1):
        self.interval = interval


    def start(self, test):
        logfile = open(os.path.join(test.profdir, "sar"), 'w')
        # Save the sar data as binary, convert to text after the test.
        raw = os.path.join(test.profdir, "sar.raw")
        cmd = "/usr/bin/sar -o %s %d 0" % (raw, self.interval)
        p = subprocess.Popen(cmd, shell=True, stdout=logfile, \
                             stderr=subprocess.STDOUT)
        self.pid = p.pid


    def stop(self, test):
        os.kill(self.pid, 15)


    def report(self, test):
        # Convert the binary sar data to text.
        raw = os.path.join(test.profdir, "sar.raw")
        output = os.path.join(test.profdir, "sar")
        utils.system('/usr/bin/sar -A -f %s > %s' % (raw, output))
