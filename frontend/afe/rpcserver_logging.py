import logging
try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.client.shared.settings import settings


LOGGING_ENABLED = settings.get_value('SERVER', 'rpc_logging', type=bool)

MEGABYTE = 1024 * 1024

rpc_logger = None


def configure_logging():
    MAX_LOG_SIZE = settings.get_value('SERVER', 'rpc_max_log_size_mb', type=int)
    NUMBER_OF_OLD_LOGS = settings.get_value('SERVER', 'rpc_num_old_logs',
                                            type=int)
    log_path = settings.get_value('SERVER', 'rpc_log_path')

    formatter = logging.Formatter(
        fmt='[%(asctime)s %(levelname)-5.5s] %(message)s',
        datefmt='%m/%d %H:%M:%S')
    handler = logging.handlers.RotatingFileHandler(log_path,
                                                   maxBytes=MAX_LOG_SIZE * MEGABYTE,
                                                   backupCount=NUMBER_OF_OLD_LOGS)
    handler.setFormatter(formatter)

    global rpc_logger
    rpc_logger = logging.getLogger('rpc_logger')
    rpc_logger.addHandler(handler)
    rpc_logger.propagate = False
    rpc_logger.setLevel(logging.DEBUG)


if LOGGING_ENABLED:
    configure_logging()
