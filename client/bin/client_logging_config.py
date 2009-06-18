import common
import logging, os
from autotest_lib.client.common_lib import logging_config

class ClientLoggingConfig(logging_config.LoggingConfig):
    def add_debug_file_handlers(self, log_dir, log_name=None):
        if not log_name:
            log_name = 'client'
        self._add_file_handlers_for_all_levels(log_dir, log_name)


    def configure_logging(self, results_dir=None, verbose=False):
        super(ClientLoggingConfig, self).configure_logging(use_console=True,
                                                           verbose=verbose)

        if results_dir:
            log_dir = os.path.join(results_dir, 'debug')
            if not os.path.exists(log_dir):
                os.mkdir(log_dir)
            self.add_debug_file_handlers(log_dir)
