"""
Sets up a subprocess to run any generic command in the background every
few seconds (by default the interval is 60 secs)
"""

import time, os, subprocess
from autotest_lib.client.bin import profiler
from autotest_lib.client.common_lib import utils, error

class cmdprofile(profiler.profiler):
    version = 2
    supports_reboot = True


    def initialize(self, cmds=['ps'], interval=60, outputfile='cmdprofile',
                   outputfiles=None):

        # do some basic sanity checking on the parameters
        if not outputfiles and not outputfile:
            raise error.TestError(
                'cmdprofile cannot run if neither outputfile nor outputfile '
                'is specified')
        elif outputfiles and len(outputfiles) != len(cmds):
            raise error.TestError(
                'cmdprofile paramter outputfiles has length %d and cmds has '
                'length %d, but both lists must have the same length' %
                (len(outputfiles), len(cmds)))

        self.interval = interval
        self.cmds = cmds
        if outputfiles:
            # outputfiles overrides outputfile
            self.outputfiles = outputfiles
        else:
            self.outputfiles = [outputfile] * len(cmds)


    def start(self, test):
        self.pid = os.fork()
        if self.pid:  # parent
            return
        else:  # child
            while True:
                for cmd, outputfile in zip(self.cmds, self.outputfiles):
                    logfile = open(os.path.join(test.profdir, outputfile), 'a')
                    utils.run(cmd, stdout_tee=logfile, stderr_tee=logfile)
                    logfile.write('\n')
                    logfile.close()
                time.sleep(self.interval)


    def stop(self, test):
        utils.nuke_pid(self.pid)
