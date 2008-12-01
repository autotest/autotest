import os, sys
import common

from autotest_lib.client.common_lib import utils, packages, profiler_manager
from autotest_lib.server import profiler


class profilers(profiler_manager.profiler_manager):
    def load_profiler(self, profiler_name, args, dargs):
        newprofiler = profiler.profiler_proxy(self.job, profiler_name)
        newprofiler.initialize(*args, **dargs)
        newprofiler.setup(*args, **dargs) # lazy setup is done client-side
        return newprofiler


    def handle_reboot(self, host):
        for p in self.list:
            p.handle_reboot(host)
