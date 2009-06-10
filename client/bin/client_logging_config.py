import common
import logging, os
from autotest_lib.client.common_lib import logging_config

class ClientLoggingConfig(logging_config.LoggingConfig):
    def add_debug_file_handlers(self, log_dir, log_name=None):
        if not log_name:
            log_name = 'client.log'
        self.add_file_handler(log_name, logging.DEBUG, log_dir=log_dir)


    def configure_logging(self, results_dir=None):
        super(ClientLoggingConfig, self).configure_logging(use_console=True)

        if results_dir:
            self.add_debug_file_handlers(results_dir)
