import logging, os, sys, time

# set up a simple catchall configuration for use during import time.  some code
# may log messages at import time and we don't want those to get completely
# thrown away.  we'll clear this out when actual configuration takes place.
logging.basicConfig(level=logging.DEBUG)

class AllowBelowSeverity(logging.Filter):
    """
    Allows only records less severe than a given level (the opposite of what
    the normal logging level filtering does.
    """
    def __init__(self, level):
        self.level = level


    def filter(self, record):
        return record.levelno < self.level


class LoggingConfig(object):
    global_level = logging.DEBUG
    stdout_level = logging.INFO
    stderr_level = logging.ERROR

    file_formatter = logging.Formatter(
        fmt='%(asctime)s %(levelname)-5.5s|%(module)10.10s:%(lineno)4.4d| '
            '%(message)s',
        datefmt='%m/%d %H:%M:%S')

    console_formatter = logging.Formatter(
        fmt='%(asctime)s %(levelname)-5.5s| %(message)s',
        datefmt='%H:%M:%S')

    def __init__(self):
        self.logger = logging.getLogger()
        self.global_level = logging.DEBUG


    @classmethod
    def get_timestamped_log_name(cls, base_name):
        return '%s.log.%s' % (base_name, time.strftime('%Y-%m-%d-%H.%M.%S'))


    @classmethod
    def get_autotest_root(cls):
        common_lib_dir = os.path.dirname(__file__)
        return os.path.abspath(os.path.join(common_lib_dir, '..', '..'))


    @classmethod
    def get_server_log_dir(cls):
        return os.path.join(cls.get_autotest_root(), 'logs')


    def add_stream_handler(self, stream, level=logging.DEBUG):
        handler = logging.StreamHandler(stream)
        handler.setLevel(level)
        handler.setFormatter(self.console_formatter)
        self.logger.addHandler(handler)
        return handler


    def add_console_handlers(self):
        stdout_handler = self.add_stream_handler(sys.stdout,
                                                 level=self.stdout_level)
        # only pass records *below* STDERR_LEVEL to stdout, to avoid duplication
        stdout_handler.addFilter(AllowBelowSeverity(self.stderr_level))

        self.add_stream_handler(sys.stderr, self.stderr_level)


    def add_file_handler(self, file_path, level=logging.DEBUG, log_dir=None):
        if log_dir:
            file_path = os.path.join(log_dir, file_path)
        handler = logging.FileHandler(file_path)
        handler.setLevel(level)
        handler.setFormatter(self.file_formatter)
        self.logger.addHandler(handler)
        return handler


    def _add_file_handlers_for_all_levels(self, log_dir, log_name):
        for level in (logging.DEBUG, logging.INFO, logging.WARNING,
                      logging.ERROR):
            file_name = '%s.%s' % (log_name, logging.getLevelName(level))
            self.add_file_handler(file_name, level=level, log_dir=log_dir)


    def add_debug_file_handlers(self, log_dir, log_name=None):
        raise NotImplemented


    def _clear_all_handlers(self):
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)


    def configure_logging(self, use_console=True, verbose=False):
        self._clear_all_handlers() # see comment at top of file
        self.logger.setLevel(self.global_level)

        if verbose:
            self.stdout_level = logging.DEBUG
        if use_console:
            self.add_console_handlers()


class TestingConfig(LoggingConfig):
    def add_stream_handler(self, *args, **kwargs):
        pass


    def add_file_handler(self, *args, **kwargs):
        pass


    def configure_logging(self, **kwargs):
        pass
