"""A singleton class for accessing global config values

provides access to global configuration file
"""

__author__ = 'raphtee@google.com (Travis Miller)'

import os, sys, ConfigParser
from autotest_lib.client.common_lib import error

dirname = os.path.dirname(sys.modules[__name__].__file__)
DEFAULT_CONFIG_FILE = os.path.abspath(os.path.join(dirname,
                                                "../../global_config.ini"))
DEFAULT_SHADOW_FILE = os.path.abspath(os.path.join(dirname,
                                                "../../shadow_config.ini"))


class ConfigError(error.AutotestError):
    pass


class ConfigValueError(ConfigError):
    pass


class global_config(object):
    _NO_DEFAULT_SPECIFIED = object()

    config = None
    config_file = DEFAULT_CONFIG_FILE
    shadow_file = DEFAULT_SHADOW_FILE


    def set_config_files(self, config_file=DEFAULT_CONFIG_FILE,
                            shadow_file=DEFAULT_SHADOW_FILE):
        self.config_file = config_file
        self.shadow_file = shadow_file
        self.config = None


    def _handle_no_value(self, section, key, default):
        if default is self._NO_DEFAULT_SPECIFIED:
            msg = ("Value '%s' not found in section '%s'" %
                   (key, section))
            raise ConfigError(msg)
        else:
            return default


    def get_config_value(self, section, key, type=str,
                         default=_NO_DEFAULT_SPECIFIED, allow_blank=False):
        self._ensure_config_parsed()

        try:
            val = self.config.get(section, key)
        except ConfigParser.Error:
            return self._handle_no_value(section, key, default)

        if not val.strip() and not allow_blank:
            return self._handle_no_value(section, key, default)

        return self._convert_value(key, section, val, type)


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
        if self.config is None:
            self.parse_config_file()


    def merge_configs(self, shadow_config):
        # overwrite whats in config with whats in shadow_config
        sections = shadow_config.sections()
        for section in sections:
            # add the section if need be
            if not self.config.has_section(section):
                self.config.add_section(section)
            # now run through all options and set them
            options = shadow_config.options(section)
            for option in options:
                val = shadow_config.get(section, option)
                self.config.set(section, option, val)


    def parse_config_file(self):
        if not os.path.exists(self.config_file):
            raise ConfigError('%s not found' % (self.config_file))
        self.config = ConfigParser.ConfigParser()
        self.config.read(self.config_file)

        # now also read the shadow file if there is one
        # this will overwrite anything that is found in the
        # other config
        if os.path.exists(self.shadow_file):
            shadow_config = ConfigParser.ConfigParser()
            shadow_config.read(self.shadow_file)
            # now we merge shadow into global
            self.merge_configs(shadow_config)


    # the values that are pulled from ini
    # are strings.  But we should attempt to
    # convert them to other types if needed.
    def _convert_value(self, key, section, value, value_type):
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
        except:
            msg = ("Could not convert %s value %r in section %s to type %s" %
                    (key, sval, section, value_type))
            raise ConfigValueError(msg)


# insure the class is a singleton.  Now the symbol global_config
# will point to the one and only one instace of the class
global_config = global_config()
