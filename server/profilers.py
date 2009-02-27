import os, sys
import common

from autotest_lib.client.common_lib import utils, packages, profiler_manager
from autotest_lib.server import profiler


class profilers(profiler_manager.profiler_manager):
    def __init__(self, job):
        super(profilers, self).__init__(job)
        self.add_log = {}


    def load_profiler(self, profiler_name, args, dargs):
        newprofiler = profiler.profiler_proxy(self.job, profiler_name)
        newprofiler.initialize(*args, **dargs)
        newprofiler.setup(*args, **dargs) # lazy setup is done client-side
        return newprofiler


    def add(self, profiler, *args, **dargs):
        super(profilers, self).add(profiler, *args, **dargs)
        self.add_log[profiler] = (args, dargs)


    def delete(self, profiler):
        super(profilers, self).delete(profiler)
        del self.add_log[profiler]


    def handle_reboot(self, host):
        for p in self.list:
            p.handle_reboot(host)
