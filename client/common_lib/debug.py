"""
Functions to retrieve debug information, that will be used throughout the code 
to determine how to log messages on each one of the 3 defined code sessions 
('server', 'client', 'tests'). With a given debug level set, on that particular
part of the code, all messages with level >= to the debug level set will be 
shown (ie, if INFO is set only INFO and higher priority messages will be shown).

The configuration file is very simple and its path is (client/debug.ini). Here
is an example of a configuration file:

[debug]
server = CRITICAL
client = INFO
test = DEBUG
"""

__author__ = 'lucasmr@br.ibm.com (Lucas Meneghel Rodrigues)'


import ConfigParser, logging, os, sys


_root_logger = logging.getLogger()


class AutotestDebugParser:
    """
    Represents the autotest debug file parser, that we will use to read debug
    level information from the file. It is implemented as a Borg class
    (more information on http://code.activestate.com/recipes/66531/) so we just
    need to read the debug configuration file once at each autotest or
    autoserv execution.
    """
    # This dictionary stores state common to all instances of this class.
    # It will be later rebound to the __dict__ attribute
    _shared_state = {}
    _parser = None
    def __init__(self):
        self.__dict__ = self._shared_state
        if not self._parser:
            self.debug_file_missing = False
            common_lib_dir = os.path.abspath(os.path.dirname(__file__))
            client_dir = os.path.dirname(common_lib_dir)
            self.debug_file_path = os.path.join(client_dir, 'debug.ini')
            if not os.path.isfile(self.debug_file_path):
                self.debug_file_missing = True
            self._parser = ConfigParser.ConfigParser()
            self._parser.read(self.debug_file_path)


    def get_module_level(self, module):
        """
        Determines the debug level set for the given module by getting this
        information from the AutotestDebugParser.
    
        @param module: String - Autotest module we will get the debug level for.
        It can be either ('server', 'client', 'tests')
        """
        if self.debug_file_missing:
            failure_reason = 'missing'
        else:
            failure_reason = 'misconfigured'

        try:
            raw_debug_string = self._parser.get('debug', module)
        except ConfigParser.Error, e:
            _root_logger.warning('Could not read level from debug.ini: %s' % e)
            _root_logger.warning('Debug config file %s is %s.' %
                                 (self.debug_file_path, failure_reason))
            _root_logger.warning('Assuming INFO level.')
            raw_debug_string = 'INFO'

        if raw_debug_string not in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 
                                    'CRITICAL'):
            _root_logger.warning('Debug level for %s: %s.' % (module,
                                                              raw_debug_string))
            _root_logger.warning('Debug config file %s is misconfigured.' %
                                 self.debug_file_path)
            _root_logger.warning('Assuming INFO level.')
            return logging.INFO
        else:
            return getattr(logging, raw_debug_string)


def configure(module, format_string='%(asctime)s %(message)s'):
    """
    Configure messages for the given autotest module.

    @param module: String - Autotest module we will get the debug level for.
    It can be either ('server', 'client', 'tests')

    @param format_string: String - The format string for the debug messages.
    The format is well documented on the logging documentation,
    http://docs.python.org/lib/module-logging.html.
    """
    _root_logger.debug('Configuring logger for %s level' % module)
    logging.basicConfig(format=format_string)
    parser = AutotestDebugParser()
    debug_level = parser.get_module_level(module)
    _root_logger.setLevel(debug_level)


def get_logger(module=None, format_string='%(asctime)s %(message)s'):
    """
    Returns the root logger properly configured for the given autotest module,
    so we can log events here.

    @param module: String - Autotest module we will get the debug level for.
    It can be either ('server', 'client', 'tests')

    @param format_string: String - The format string for the debug messages.
    The format is well documented on the logging documentation,
    http://docs.python.org/lib/module-logging.html.
    """
    if module:
        configure(module, format_string)
    return _root_logger
