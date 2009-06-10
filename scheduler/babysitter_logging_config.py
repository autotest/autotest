import common
import logging
from autotest_lib.client.common_lib import logging_config

class BabysitterLoggingConfig(logging_config.LoggingConfig):
    def configure_logging(self):
        super(BabysitterLoggingConfig, self).configure_logging(use_console=True)

        self.add_file_handler(self.get_timestamped_log_name('babysitter'),
                              logging.DEBUG,
                              log_dir=self.get_server_log_dir())
