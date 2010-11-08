"""
Uses perf_events to count cycles and instructions

Defaults options:
job.profilers.add('cpistat', interval=1)
"""
import time, os, subprocess
from autotest_lib.client.bin import profiler

class cpistat(profiler.profiler):
    version = 1

    def initialize(self, interval = 1):
        self.interval = interval


    def start(self, test):
        cmd = os.path.join(self.bindir, 'site_cpistat')
        if not os.path.exists(cmd):
            cmd = os.path.join(self.bindir, 'cpistat')
        logfile = open(os.path.join(test.profdir, "cpistat"), 'w')
        p = subprocess.Popen(cmd, stdout=logfile,
                             stderr=subprocess.STDOUT)
        self.pid = p.pid


    def stop(self, test):
        os.kill(self.pid, 15)
