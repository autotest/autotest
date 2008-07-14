"""
Run iostat with a default interval of 1 second. 
"""
import time, os, subprocess
from autotest_lib.client.bin import profiler


class iostat(profiler.profiler):
    version = 1

    def initialize(self, interval = 1):
        self.interval = interval


    def start(self, test):
        cmd = "/usr/bin/iostat -tmx %d" % self.interval
        logfile = open(os.path.join(test.profdir, "iostat"), 'w')
        p = subprocess.Popen(cmd, shell=True, stdout=logfile, \
                                        stderr=subprocess.STDOUT)
        self.pid = p.pid


    def stop(self, test):
        os.kill(self.pid, 15)


    def report(self, test):
        return None
