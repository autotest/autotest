import os
import re
from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils

import tracers
import base_tracer

class tracing_microbenchmark(test.test):
    version = 1
    preserve_srcdir = True

    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make CROSS_COMPILE=""')

    def initialize(self, tracer='ftrace', calls=100000, **kwargs):
        self.job.require_gcc()
        tracer_class = getattr(tracers, tracer)
        if not issubclass(tracer_class, base_tracer.Tracer):
            raise TypeError
        self.tracer = tracer_class()

        getuid_microbench = os.path.join(self.srcdir, 'getuid_microbench')
        self.cmd = '%s %d' % (getuid_microbench, calls)

    def warmup(self, buffer_size_kb=8000, **kwargs):
        self.tracer.warmup(buffer_size_kb)

    def cleanup(self):
        self.tracer.cleanup()

    def run_once(self, **kwargs):
        self.results = {}

        self.tracer.start_tracing()
        self.cmd_result = utils.run(self.cmd)
        self.tracer.stop_tracing()

        self.tracer.gather_stats(self.results)
        self.tracer.reset_tracing()

    def postprocess_iteration(self):
        result_re = re.compile(r'(?P<calls>\d+) calls '
                               r'in (?P<time>\d+\.\d+) s '
                               '\((?P<ns_per_call>\d+\.\d+) ns/call\)')
        match = result_re.match(self.cmd_result.stdout)
        self.results.update(match.groupdict())

        self.write_perf_keyval(self.results)
