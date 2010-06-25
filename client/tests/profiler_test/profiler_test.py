import time
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import test, utils


class profiler_test(test.test):
    version = 2


    def initialize(self, profiler=None, profiler_args=(), profiler_dargs=None):
        """
        Initialize this test with the profiler name, args and dargs.

        @param profiler: Profiler name.
        @param profiler_args: Profiler non-keyword arguments.
        @param profiler_dargs: Profiler keyword arguments.
        """
        if not profiler:
            raise error.TestError('No profiler specified.')
        self._profiler = profiler
        self._profiler_args = profiler_args
        self._profiler_dargs = profiler_dargs or {}


    def execute(self, seconds=5):
        """
        Add and start the profiler, sleep some seconds, stop and delete it.

        We override "execute" and not "run_once" because we need to control
        profilers here and in "run_once" it would be too late for that.

        @param seconds: Number of seconds to sleep while the profiler is
                running.
        """
        profilers = self.job.profilers
        profilers.add(self._profiler, *self._profiler_args,
                      **self._profiler_dargs)
        profilers.start(self)

        time.sleep(seconds)

        profilers.stop(self)
        profilers.report(self)
        # TODO: check for profiler result files?
        profilers.delete(self._profiler)
