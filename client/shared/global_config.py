"""
A singleton class for accessing global config values

provides access to global configuration file
"""

__author__ = 'raphtee@google.com (Travis Miller)'


import os, sys, ConfigParser
from autotest.client.shared import error


class ConfigError(error.AutotestError):
    '''
    Exception raised when the requested configuration item does not exist

    This applies both the missing config files or sections or items of the
    config file.
    '''
    pass


class ConfigValueError(ConfigError):
    '''
    Exception raised when the fetched configuration value can not be converted
    '''
    pass


#: Default global config file names, independent of actual path
GLOBAL_CONFIG_FILENAME = 'global_config.ini'

#: Default shadow config file names, independent of actual path
SHADOW_CONFIG_FILENAME = 'shadow_config.ini'


SHARED_DIR = os.path.dirname(sys.modules[__name__].__file__)
CLIENT_DIR = os.path.dirname(SHARED_DIR)
ROOT_DIR = os.path.dirname(CLIENT_DIR)

# Check if the config files are in the system wide directory
SYSTEM_WIDE_DIR = '/etc/autotest'
GLOBAL_CONFIG_PATH_SYSTEM_WIDE = os.path.join(SYSTEM_WIDE_DIR,
                                              GLOBAL_CONFIG_FILENAME)
SHADOW_CONFIG_PATH_SYSTEM_WIDE = os.path.join(SYSTEM_WIDE_DIR,
                                              SHADOW_CONFIG_FILENAME)
CONFIG_IN_SYSTEM_WIDE = os.path.exists(GLOBAL_CONFIG_PATH_SYSTEM_WIDE)


# Check if the config files are at autotest's root dir
# This will happen if client is executing inside a full autotest tree, or if
# other entry points are being executed
GLOBAL_CONFIG_PATH_ROOT = os.path.join(ROOT_DIR, GLOBAL_CONFIG_FILENAME)
SHADOW_CONFIG_PATH_ROOT = os.path.join(ROOT_DIR, SHADOW_CONFIG_FILENAME)
CONFIG_IN_ROOT = (os.path.exists(GLOBAL_CONFIG_PATH_ROOT) and
                  os.path.exists(SHADOW_CONFIG_PATH_ROOT))


# Check if the config files are at autotest's client dir
# This will happen if a client stand alone execution is happening
GLOBAL_CONFIG_PATH_CLIENT = os.path.join(CLIENT_DIR, GLOBAL_CONFIG_FILENAME)
CONFIG_IN_CLIENT = os.path.exists(GLOBAL_CONFIG_PATH_CLIENT)


if CONFIG_IN_SYSTEM_WIDE:
    DEFAULT_CONFIG_FILE = GLOBAL_CONFIG_PATH_SYSTEM_WIDE
    DEFAULT_SHADOW_FILE = SHADOW_CONFIG_PATH_SYSTEM_WIDE
    RUNNING_STAND_ALONE_CLIENT = False
elif CONFIG_IN_ROOT:
    DEFAULT_CONFIG_FILE = GLOBAL_CONFIG_PATH_ROOT
    DEFAULT_SHADOW_FILE = SHADOW_CONFIG_PATH_ROOT
    RUNNING_STAND_ALONE_CLIENT = False
elif CONFIG_IN_CLIENT:
    DEFAULT_CONFIG_FILE = GLOBAL_CONFIG_PATH_CLIENT
    DEFAULT_SHADOW_FILE = None
    RUNNING_STAND_ALONE_CLIENT = True
else:
    DEFAULT_CONFIG_FILE = None
    DEFAULT_SHADOW_FILE = None
    RUNNING_STAND_ALONE_CLIENT = True


class global_config(object):
    '''
    A class for accessing global config values
    '''
    _NO_DEFAULT_SPECIFIED = object()

    config = None
    config_file = DEFAULT_CONFIG_FILE
    shadow_file = DEFAULT_SHADOW_FILE
    running_stand_alone_client = RUNNING_STAND_ALONE_CLIENT


    def check_stand_alone_client_run(self):
        '''
        Checks if this code was detected to be running on an autotest client
        '''
        return self.running_stand_alone_client


    def set_config_files(self,
                         config_file=DEFAULT_CONFIG_FILE,
                         shadow_file=DEFAULT_SHADOW_FILE):
        '''
        Assigns this instance's pointers to the config files set or detected
        '''
        self.config_file = config_file
        self.shadow_file = shadow_file
        self.config = None


    def _handle_no_value(self, section, key, default):
        '''
        Returns the requested config value or its default value if set
        '''
        if default is self._NO_DEFAULT_SPECIFIED:
            msg = ("Value '%s' not found in section '%s'" %
                   (key, section))
            raise ConfigError(msg)
        else:
            return default


    def get_section_values(self, sections):
        """
        Return a config parser object containing a single section of the
        global configuration, that can be later written to a file object.

        @param section: Tuple with sections we want to turn into a config parser
                object.
        @return: ConfigParser() object containing all the contents of sections.
        """
        self._ensure_config_parsed()

        if isinstance(sections, str):
            sections = [sections]
        cfgparser = ConfigParser.ConfigParser()
        for section in sections:
            cfgparser.add_section(section)
            for option, value in self.config.items(section):
                cfgparser.set(section, option, value)
        return cfgparser


    def get_config_value(self, section, key, value_type=str,
                         default=_NO_DEFAULT_SPECIFIED, allow_blank=False):
        '''
        Returns the chosen config key value

        Optionally this method converts the value to the supplied Python type,
        sets a default value and deals with blank values.
        '''
        self._ensure_config_parsed()

        try:
            val = self.config.get(section, key)
        except ConfigParser.Error:
            return self._handle_no_value(section, key, default)

        if not val.strip() and not allow_blank:
            return self._handle_no_value(section, key, default)

        return self._convert_value(key, section, val, value_type)


    def override_config_value(self, section, key, new_value):
        """
        Override a value from the config file with a new value.
        """
        self._ensure_config_parsed()
        self.config.set(section, key, new_value)


    def reset_config_values(self):
        """
        Reset all values to those found in the config files (undoes all
        overrides).
        """
        self.parse_config_file()


    def _ensure_config_parsed(self):
        '''
        Parses the config file if it hasn't been done yet
        '''
        if self.config is None:
            self.parse_config_file()


    def merge_configs(self, shadow_config):
        '''
        Overwrite whats in config with whats in shadow_config

        This method adds section if needed, and then run through all options
        and sets every one that is found
        '''
        sections = shadow_config.sections()
        for section in sections:
            if not self.config.has_section(section):
                self.config.add_section(section)

            options = shadow_config.options(section)
            for option in options:
                val = shadow_config.get(section, option)
                self.config.set(section, option, val)


    def parse_config_file(self):
        '''
        Perform the parsing of both config files, merging common values

        After reading the global_config.ini file, if a shadow_config.ini file
        exists, it will be read and anything that is found in the previous
        config file will be overriden.
        '''
        self.config = ConfigParser.ConfigParser()
        if self.config_file and os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            raise ConfigError('%s not found' % (self.config_file))

        if self.shadow_file and os.path.exists(self.shadow_file):
            shadow_config = ConfigParser.ConfigParser()
            shadow_config.read(self.shadow_file)
            self.merge_configs(shadow_config)


    def _convert_value(self, key, section, value, value_type):
        '''
        Convert the values that are pulled from the config file

        Those values are strings by default, and this method attempts to
        convert them to other types if needed.
        '''
        # strip off leading and trailing white space
        sval = value.strip()

        # if length of string is zero then return None
        if len(sval) == 0:
            if value_type == str:
                return ""
            elif value_type == bool:
                return False
            elif value_type == int:
                return 0
            elif value_type == float:
                return 0.0
            elif value_type == list:
                return []
            else:
                return None

        if value_type == bool:
            if sval.lower() == "false":
                return False
            else:
                return True

        if value_type == list:
            # Split the string using ',' and return a list
            return [val.strip() for val in sval.split(',')]

        try:
            conv_val = value_type(sval)
            return conv_val
        except Exception:
            msg = ("Could not convert %s value %r in section %s to type %s" %
                    (key, sval, section, value_type))
            raise ConfigValueError(msg)


# ensure the class is a singleton.  Now the symbol global_config
# will point to the one and only one instace of the class
global_config = global_config()
