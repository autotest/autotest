"""
Run iostat with a default interval of 1 second.
"""
import time, os, subprocess
from autotest_lib.client.bin import profiler
from autotest_lib.client.common_lib import utils, error


class iostat(profiler.profiler):
    version = 2

    def initialize(self, interval = 1, options = ''):
        # Usage: iostat [ options... ] [ <interval> [ <count> ] ]
        # e.g, iostat -tmx 2
        self.interval = interval
        self.options = options


    def start(self, test):
        cmd = "/usr/bin/iostat %s %d" % (self.options, self.interval)
        filename = "iostat." + time.strftime("%Y-%m-%d-%H-%M-%S")
        logfile = open(os.path.join(test.profdir, filename), 'w')
        p = subprocess.Popen(cmd, shell=True, stdout=logfile,
                             stderr=subprocess.STDOUT)
        self.pid = p.pid


    def stop(self, test):
        try:
            term_profiler = "kill -15 %d" % self.pid
            # send SIGTERM to iostat and give it a 5-sec timeout
            utils.system(term_profiler, timeout=5)
        except error.CmdError: # probably times out
            pass
        # do a ps again to see if iostat is still there
        ps_cmd = "ps -p %d | grep iostat" % self.pid
        out = utils.system_output(ps_cmd, ignore_status=True)
        if out != '':
            kill_profiler = 'kill -9 %d' % self.pid
            utils.system(kill_profiler, ignore_status=True)


    def report(self, test):
        return None
