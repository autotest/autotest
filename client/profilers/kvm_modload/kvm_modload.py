"""
Loads KVM virtualization kernel module before a test cycle and unloads it after.
Intended to help in qualifying KVM in the kernel by comparing runs of kernel
tests with and without this "profiler".

author: jsmiller@google.com
"""

import os, subprocess
from autotest_lib.client.bin import kvm_control, profiler, utils


class kvm_modload(profiler.profiler):
    version = 4


    def initialize(self, interval=None, options=None):
        pass


    def log_lsmod(self, log):
        log.write("lsmod: \n")
        cmd_status = utils.run("lsmod")
        if cmd_status.stdout:
            log.write(cmd_status.stdout)
            log.write("\n")
        if cmd_status.stderr:
            log.write(cmd_status.stderr)
            log.write("\n")


    def start(self, test):
        load_status = kvm_control.load_kvm()
        self.logfile = open(os.path.join(test.profdir, "kvm_modload"), 'w')
        self.logfile.write("Loaded KVM module with status %s.\n" %
          repr(load_status))
        self.log_lsmod(self.logfile)


    def stop(self, test):
        unload_status = kvm_control.unload_kvm()
        self.logfile.write("Unloaded KVM module with status %s.\n" %
          repr(unload_status))
        self.log_lsmod(self.logfile)
        self.logfile.close()


    def report(self, test):
        output = os.path.join(test.profdir, "kvm_modload")
