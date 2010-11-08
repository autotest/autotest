import os
from autotest_lib.client.bin import utils

import base_tracer
try:
    from site_tracers import *
except ImportError:
    pass


off = base_tracer.Tracer


class ftrace(base_tracer.Tracer):

    mountpoint = '/sys/kernel/debug'
    tracing_dir = os.path.join(mountpoint, 'tracing')

    def warmup(self, buffer_size_kb):
        if not os.path.exists(self.tracing_dir):
            utils.system('mount -t debugfs debugfs %s' % self.mountpoint)

        # ensure clean state:
        self.trace_config('tracing_enabled', '0')
        self.trace_config('current_tracer', 'nop')
        self.trace_config('events/enable', '0')
        self.trace_config('trace', '')
        # set ring buffer size:
        self.trace_config('buffer_size_kb', str(buffer_size_kb))
        # enable tracepoints:
        self.trace_config('events/syscalls/sys_enter_getuid/enable', '1')

    def cleanup(self):
        # reset ring buffer size:
        self.trace_config('buffer_size_kb', '1408')
        # disable tracepoints:
        self.trace_config('events/enable', '0')

    def start_tracing(self):
        self.trace_config('tracing_enabled', '1')

    def stop_tracing(self):
        self.trace_config('tracing_enabled', '0')

    def reset_tracing(self):
        self.trace_config('trace', '')

    def gather_stats(self, results):
        per_cpu = os.path.join(self.tracing_dir, 'per_cpu')
        for cpu in os.listdir(per_cpu):
            cpu_stats = os.path.join(per_cpu, cpu, 'stats')
            for line in utils.read_file(cpu_stats).splitlines():
                key, val = line.split(': ')
                key = key.replace(' ', '_')
                val = int(val)
                cpu_key = '%s_%s' % (cpu, key)
                total_key = 'total_' + key
                results[cpu_key] = val
                results[total_key] = (results.get(total_key, 0) +
                                      results[cpu_key])
