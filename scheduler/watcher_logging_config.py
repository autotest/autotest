try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
import logging

from autotest.client.shared import logging_config


class WatcherLoggingConfig(logging_config.LoggingConfig):

    def __init__(self, use_console=True):
        super(WatcherLoggingConfig, self).__init__(use_console=use_console)

    def configure_logging(self):
        super(WatcherLoggingConfig, self).configure_logging(
            use_console=self.use_console)

        self.add_file_handler(self.get_timestamped_log_name('scheduler-watcher'),
                              logging.DEBUG,
                              log_dir=self.get_server_log_dir())
