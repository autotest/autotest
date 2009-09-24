"""
Sets up a subprocess to run any generic command in the background every
few seconds (by default the interval is 60 secs)
"""

import time, os, subprocess
from autotest_lib.client.bin import profiler
from autotest_lib.client.common_lib import utils

class cmdprofile(profiler.profiler):
    version = 1
    supports_reboot = True

    def initialize(self, cmds=['ps'], interval=60, outputfile='cmdprofile'):
        self.interval = interval
        self.cmds = cmds
        self.outputfile = outputfile


    def start(self, test):
        self.pid = os.fork()
        if self.pid:  # parent
            return
        else:  # child
            logfile = open(os.path.join(test.profdir, self.outputfile), 'a')
            while True:
                for cmd in self.cmds:
                    utils.run(cmd, stdout_tee=logfile, stderr_tee=logfile)
                    logfile.write('\n')
                time.sleep(self.interval)
            logfile.close()


    def stop(self, test):
        utils.nuke_pid(self.pid)
