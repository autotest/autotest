"""
Trace kernel events with Linux Tracing Toolkit (lttng).
You need to install the lttng patched kernel in order to use the profiler.

Examples:
    job.profilers.add('lttng') will enable all of the trace points.
    job.profilers.add('lttng', []) will disable all of the trace points.
    job.profilers.add('lttng', ['kernel_arch_syscall_entry',
                                'kernel_arch_syscall_exit'])
                               will only trace syscall events.
Take a look at /proc/ltt for the list of the tracing events currently
supported by lttng and their output formats.

To view the collected traces, copy results/your-test/profiler/lttng
to a machine that has Linux Tracing Toolkit Viewer (lttv) installed:
    test$ scp -r results/your-test/profiler/lttng user@localmachine :/home/tmp/
Then you can examine the traces either in text mode or in GUI:
    localmachine$ lttv -m textDump -t /home/tmp/lttng
or
    localmachine$ lttv-gui -t /home/tmp/lttng &
"""

import os, shutil
from autotest_lib.client.bin import autotest_utils, profiler
from autotest_lib.client.common_lib import utils, error

class lttng(profiler.profiler):
    version = 1

    # http://ltt.polymtl.ca/lttng/ltt-control-0.51-12082008.tar.gz
    def setup(self, tarball='ltt-control-0.51-12082008.tar.gz'):
        self.tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        autotest_utils.extract_tarball_to_dir(self.tarball, self.srcdir)
        os.chdir(self.srcdir)

        utils.system('./configure')
        utils.system('make')


    # tracepoints: list of trace points to enable
    def initialize(self, tracepoints = None):
        self.job.require_gcc()

        self.tracepoints = tracepoints
        self.ltt_bindir = os.path.join(self.srcdir, 'lttctl')
        self.lttctl = os.path.join(self.ltt_bindir, 'lttctl')
        self.lttd = os.path.join(self.srcdir, 'lttd', 'lttd')
        self.armall = os.path.join(self.ltt_bindir, 'ltt-armall')
        self.disarmall = os.path.join(self.ltt_bindir, 'ltt-disarmall')
        self.mountpoint = '/mnt/debugfs'

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
        output = os.path.join(test.profdir, 'lttng')
        utils.system('%s -n test -d -l %s/ltt -t %s' % 
                                      (self.lttctl, self.mountpoint, output))


    def stop(self, test):
        utils.system(self.lttctl + ' -n test -R')
