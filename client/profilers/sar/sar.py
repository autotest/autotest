"""
Sets up a subprocess to run sar from the sysstat suite

Default options:
sar -A -f
"""
import os, shutil, subprocess, time
from autotest_lib.client.bin import utils, profiler, os_dep


class sar(profiler.profiler):
    """
    The sar command writes to standard output the contents of selected
    cumulative activity counters in the operating system. This profiler
    executes sar and redirects its output in a file located in the profiler
    results dir.
    """
    version = 1

    def initialize(self, interval=1):
        """
        Set sar interval and verify what flags the installed sar supports.

        @param interval: Interval used by sar to produce system data.
        """
        self.interval = interval
        self.sar_path = os_dep.command('sar')
        # If using older versions of sar, command below means: Measure default
        # params using interval of 1 second continuously. For newer versions,
        # behavior has changed - to generate reports continuously just omit the
        # count parameter.
        t_cmd = self.sar_path + " 1 0"
        t_process = subprocess.Popen(t_cmd, shell=True,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
        # Wait a little to see if process is going to fail or work
        time.sleep(3)
        if t_process.poll():
            # Sar process returned, so 0 doesn't mean generate continuously
            self.cmd = self.sar_path + " -o %s %d"
        else:
            # Sar process didn't return, so 0 means generate continuously
            # Just terminate the process
            self.cmd = self.sar_path + " -o %s %d 0"
            os.kill(t_process.pid, 15)


    def start(self, test):
        """
        Starts sar subprocess.

        @param test: Autotest test on which this profiler will operate on.
        """
        logfile = open(os.path.join(test.profdir, "sar"), 'w')
        # Save the sar data as binary, convert to text after the test.
        raw = os.path.join(test.profdir, "sar.raw")
        cmd = self.cmd % (raw, self.interval)
        self.sar_process = subprocess.Popen(cmd, shell=True, stdout=logfile,
                                            stderr=subprocess.STDOUT)


    def stop(self, test):
        """
        Stops profiler execution by sending a SIGTERM to sar process.

        @param test: Autotest test on which this profiler will operate on.
        """
        try:
            os.kill(self.sar_process.pid, 15)
        except OSError:
            pass

    def report(self, test):
        """
        Report function. Convert the binary sar data to text.

        @param test: Autotest test on which this profiler will operate on.
        """
        raw = os.path.join(test.profdir, "sar.raw")
        output = os.path.join(test.profdir, "sar")
        utils.system('/usr/bin/sar -A -f %s > %s' % (raw, output))
