"""
Runs vmstat X where X is the interval in seconds

Defaults options:
job.profilers.add('vmstat', interval=1)
"""
import time, os, subprocess
from autotest_lib.client.bin import profiler


class vmstat(profiler.profiler):
    version = 1

    def initialize(self, interval = 1):
        self.interval = interval


    def start(self, test):
        cmd = "/usr/bin/vmstat %d" % self.interval
        logfile = open(os.path.join(test.profdir, "vmstat"), 'w')
        p = subprocess.Popen(cmd, shell=True, stdout=logfile, \
                                        stderr=subprocess.STDOUT)
        self.pid = p.pid


    def stop(self, test):
        os.kill(self.pid, 15)


    def report(self, test):
        return None
