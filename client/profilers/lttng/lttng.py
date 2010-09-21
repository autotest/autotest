"""
Trace kernel events with Linux Tracing Toolkit (lttng).
You need to install the lttng patched kernel in order to use the profiler.

Examples:
    job.profilers.add('lttng', tracepoints = None): enable all trace points.
    job.profilers.add('lttng', tracepoints = []): disable all trace points.
    job.profilers.add('lttng', tracepoints = ['kernel_arch_syscall_entry',
                                              'kernel_arch_syscall_exit'])
                               will only trace syscall events.
Take a look at /proc/ltt for the list of the tracing events currently
supported by lttng and their output formats.

To view the collected traces, copy results/your-test/profiler/lttng
to a machine that has Linux Tracing Toolkit Viewer (lttv) installed:
    test$ scp -r results/your-test/profiler/lttng user@localmachine:/home/tmp/
Then you can examine the traces either in text mode or in GUI:
    localmachine$ lttv -m textDump -t /home/tmp/lttng
or
    localmachine$ lttv-gui -t /home/tmp/lttng &
"""

import os, shutil, time
from autotest_lib.client.bin import utils, profiler
from autotest_lib.client.common_lib import error

class lttng(profiler.profiler):
    version = 1

    # http://ltt.polymtl.ca/lttng/ltt-control-0.51-12082008.tar.gz
    def setup(self, tarball='ltt-control-0.51-12082008.tar.gz', **dargs):
        self.tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(self.tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.configure()
        utils.make()


    # tracepoints: list of trace points to enable
    # outputsize: size limit for lttng output file. -1: no limit.
    def initialize(self, outputsize=1048576, tracepoints=None, **dargs):
        self.job.require_gcc()

        self.tracepoints = tracepoints
        self.ltt_bindir = os.path.join(self.srcdir, 'lttctl')
        self.lttctl = os.path.join(self.ltt_bindir, 'lttctl')
        self.lttd = os.path.join(self.srcdir, 'lttd', 'lttd')
        self.armall = os.path.join(self.ltt_bindir, 'ltt-armall')
        self.disarmall = os.path.join(self.ltt_bindir, 'ltt-disarmall')
        self.mountpoint = '/mnt/debugfs'
        self.outputsize = outputsize

        os.putenv('LTT_DAEMON', self.lttd)

        if not os.path.exists(self.mountpoint):
            os.mkdir(self.mountpoint)

        utils.system('mount -t debugfs debugfs ' + self.mountpoint,
                                                            ignore_status=True)
        utils.system('modprobe ltt-control')
        utils.system('modprobe ltt-statedump')
        # clean up from any tracing we left running
        utils.system(self.lttctl + ' -n test -R', ignore_status=True)
        utils.system(self.disarmall, ignore_status=True)

        if tracepoints is None:
            utils.system(self.armall, ignore_status=True)
        else:
            for tracepoint in self.tracepoints:
                if tracepoint in ('list_process_state',
                                  'user_generic_thread_brand', 'fs_exec',
                                  'kernel_process_fork', 'kernel_process_free',
                                  'kernel_process_exit',
                                  'kernel_arch_kthread_create',
                                  'list_statedump_end', 'list_vm_map'):
                    channel = 'processes'
                elif tracepoint in ('list_interrupt',
                                    'statedump_idt_table',
                                    'statedump_sys_call_table'):
                    channel = 'interrupts'
                elif tracepoint in ('list_network_ipv4_interface',
                                    'list_network_ip_interface'):
                    channel = 'network'
                elif tracepoint in ('kernel_module_load', 'kernel_module_free'):
                    channel = 'modules'
                else:
                    channel = ''
                print 'Connecting ' + tracepoint
                utils.write_one_line('/proc/ltt', 'connect ' + tracepoint
                                     + ' default dynamic ' + channel)

    def start(self, test):
        self.output = os.path.join(test.profdir, 'lttng')
        utils.system('%s -n test -d -l %s/ltt -t %s' %
                                  (self.lttctl, self.mountpoint, self.output))


    def stop(self, test):
        utils.system(self.lttctl + ' -n test -R')
        time.sleep(10)
        if self.outputsize != -1:
            # truncate lttng output file to the specified limit
            for filename in os.listdir(self.output):
                file_path = os.path.join(self.output, filename)
                if os.path.isdir(file_path):
                    continue
                size = os.stat(file_path)[6] # grab file size
                if size > self.outputsize:
                    f = open(file_path, 'r+')
                    f.truncate(self.outputsize)
                    f.close()
        tarball = os.path.join(test.profdir, 'lttng.tar.bz2')
        utils.system("tar -cvjf %s -C %s %s" % (tarball, test.profdir, 'lttng'))
        utils.system('rm -rf ' + self.output)
