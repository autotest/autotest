"""
What's eating the battery life of my laptop? Why isn't it many more
hours? Which software component causes the most power to be burned?
These are important questions without a good answer... until now.
"""
import time, os
from autotest_lib.client.bin import utils, profiler

class powertop(profiler.profiler):
    version = 1
    preserve_srcdir = True

    # filenames: list of filenames to cat
    def setup(self, *args, **dargs):
        os.chdir(self.srcdir)
        utils.make()


    def start(self, test):
        self.child_pid = os.fork()
        if self.child_pid:                      # parent
            return None
        else:                                   # child
            powertop = os.path.join(self.srcdir, 'powertop') + ' -d'
            outputfile = os.path.join(test.profdir, 'powertop')
            while True:
                output = open(outputfile, 'a')
                output.write(time.asctime() + '\n')
                data = utils.system_output('%s >> %s' % (powertop, outputfile))
                output.write(data)
                output.write('\n=========================\n')
                output.close()


    def stop(self, test):
        os.kill(self.child_pid, 15)


    def report(self, test):
        return None
