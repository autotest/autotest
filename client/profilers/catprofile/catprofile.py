"""
Sets up a subprocses to cat a file on a specified interval

Defaults options:
job.profilers.add('catprofile', ['/proc/meminfo','/proc/uptime'],
                  outfile=monitor, interval=1)
"""
import time, os
from autotest_lib.client.bin import profiler

class catprofile(profiler.profiler):
    version = 1

    # filenames: list of filenames to cat
    def initialize(self, filenames = ['/proc/meminfo', '/proc/slabinfo'],
                            outfile = 'monitor', interval = 1):
        self.filenames = filenames
        self.outfile = outfile
        self.interval = interval


    def start(self, test):
        self.child_pid = os.fork()
        if self.child_pid:                      # parent
            return None
        else:                                   # child
            while 1:
                lines = []
                for filename in self.filenames:
                    input = open(filename, 'r')
                    lines += '\n----- %s -----\n' % filename
                    lines += input.readlines()
                    input.close
                outfile = test.profdir + '/' + self.outfile
                output = open(outfile, 'a')
                output.write(time.asctime() + '\n')
                output.writelines(lines)
                output.write('\n=========================\n')
                output.close()
                time.sleep(self.interval)


    def stop(self, test):
        os.kill(self.child_pid, 15)


    def report(self, test):
        return None
