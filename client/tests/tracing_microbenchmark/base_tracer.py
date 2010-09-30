import os
from autotest_lib.client.bin import utils


class Tracer(object):
    """
    Common interface for tracing.
    """

    tracing_dir = None

    def trace_config(self, path, value):
        """
        Write value to a tracing config file under self.tracing_dir.
        """
        path = os.path.join(self.tracing_dir, path)
        utils.open_write_close(path, value)

    def warmup(self, buffer_size_kb):
        pass
    def cleanup(self):
        pass
    def start_tracing(self):
        pass
    def stop_tracing(self):
        pass
    def gather_stats(self, results):
        pass
    def reset_tracing(self):
        pass
