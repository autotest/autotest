try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

import os

from autotest.client.shared import logging_config
from autotest.client.shared.settings import settings


class ClientLoggingConfig(logging_config.LoggingConfig):

    def add_debug_file_handlers(self, log_dir, log_name=None):
        if not log_name:
            log_name = settings.get_value('CLIENT', 'default_logging_name',
                                          type=str, default='client')
        self._add_file_handlers_for_all_levels(log_dir, log_name)

    def configure_logging(self, results_dir=None, verbose=False):
        super(ClientLoggingConfig, self).configure_logging(
            use_console=self.use_console,
            verbose=verbose)

        if results_dir:
            log_dir = os.path.join(results_dir, 'debug')
            if not os.path.exists(log_dir):
                os.mkdir(log_dir)
            self.add_debug_file_handlers(log_dir)
