import common
import logging, os
from autotest_lib.client.common_lib import logging_config

class SchedulerLoggingConfig(logging_config.LoggingConfig):
    GLOBAL_LEVEL = logging.INFO

    @classmethod
    def get_log_name(cls):
        return cls.get_timestamped_log_name('scheduler')


    def configure_logging(self, log_dir=None, logfile_name=None):
        super(SchedulerLoggingConfig, self).configure_logging(use_console=True)

        if log_dir is None:
            log_dir = self.get_server_log_dir()
        if not logfile_name:
            logfile_name = self.get_log_name()

        self.add_file_handler(logfile_name, logging.DEBUG, log_dir=log_dir)
