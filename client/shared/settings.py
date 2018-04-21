"""
A singleton class for accessing global config values.

provides access to global configuration file.
"""

__author__ = 'raphtee@google.com (Travis Miller)'

import configparser
import os
import sys

from autotest.client.shared import error
from pkg_resources import resource_filename


class SettingsError(error.AutotestError):
    pass


class SettingsValueError(SettingsError):
    pass


settings_filename = 'global_config.ini'
shadow_config_filename = 'shadow_config.ini'

shared_dir = os.path.dirname(sys.modules[__name__].__file__)
client_dir = os.path.dirname(shared_dir)
root_dir = os.path.dirname(client_dir)

# Get the system-wide installed config files
if "AUTOTEST_TOP_PATH" in os.environ:
    _autotest_top_path = os.environ["AUTOTEST_TOP_PATH"]
    settings_path_system_wide = os.path.join(_autotest_top_path,
                                             settings_filename)
    shadow_config_path_system_wide = os.path.join(_autotest_top_path,
                                                  shadow_config_filename)
else:
    settings_path_system_wide = resource_filename("autotest",
                                                  settings_filename)
    shadow_config_path_system_wide = resource_filename("autotest",
                                                       shadow_config_filename)
    # When not in virtual env prefer /etc config files (compatibility)
    if not hasattr(sys, "real_prefix"):
        _settings_path_etc = os.path.join("/etc/autotest", settings_filename)
        _shadow_config_path_etc = os.path.join("/etc/autotest",
                                               shadow_config_filename)
        if os.path.exists(_settings_path_etc):
            settings_path_system_wide = _settings_path_etc
        if os.path.exists(_shadow_config_path_etc):
            settings_path_system_wide = _shadow_config_path_etc

config_in_system_wide = os.path.exists(settings_path_system_wide)

# Check if the config files are at autotest's root dir
# This will happen if client is executing inside a full autotest tree, or if
# other entry points are being executed
settings_path_root = os.path.join(root_dir, settings_filename)
shadow_config_path_root = os.path.join(root_dir, shadow_config_filename)
config_in_root = (os.path.exists(settings_path_root) and
                  os.path.exists(shadow_config_path_root))

# Check if the config files are at autotest's client dir
# This will happen if a client stand alone execution is happening
settings_path_client = os.path.join(client_dir, 'global_config.ini')
config_in_client = os.path.exists(settings_path_client)

if config_in_system_wide:
    DEFAULT_CONFIG_FILE = settings_path_system_wide
    DEFAULT_SHADOW_FILE = shadow_config_path_system_wide
    RUNNING_STAND_ALONE_CLIENT = False
elif config_in_root:
    DEFAULT_CONFIG_FILE = settings_path_root
    DEFAULT_SHADOW_FILE = shadow_config_path_root
    RUNNING_STAND_ALONE_CLIENT = False
elif config_in_client:
    DEFAULT_CONFIG_FILE = settings_path_client
    DEFAULT_SHADOW_FILE = None
    RUNNING_STAND_ALONE_CLIENT = True
else:
    DEFAULT_CONFIG_FILE = None
    DEFAULT_SHADOW_FILE = None
    RUNNING_STAND_ALONE_CLIENT = True


class Settings(object):
    _NO_DEFAULT_SPECIFIED = object()

    config = None
    config_file = DEFAULT_CONFIG_FILE
    shadow_file = DEFAULT_SHADOW_FILE
    running_stand_alone_client = RUNNING_STAND_ALONE_CLIENT

    def check_stand_alone_client_run(self):
        return self.running_stand_alone_client

    def set_config_files(self, config_file=DEFAULT_CONFIG_FILE,
                         shadow_file=DEFAULT_SHADOW_FILE):
        self.config_file = config_file
        self.shadow_file = shadow_file
        self.config = None

    def _handle_no_value(self, section, key, default):
        if default is self._NO_DEFAULT_SPECIFIED:
            msg = ("Value '%s' not found in section '%s'" %
                   (key, section))
            raise SettingsError(msg)
        else:
            return default

    def get_section_values(self, sections):
        """
        Return a config parser object containing a single section of the
        global configuration, that can be later written to a file object.

        :param section: Tuple with sections we want to turn into a config parser
                object.
        :return: ConfigParser() object containing all the contents of sections.
        """
        self._ensure_config_parsed()

        if isinstance(sections, str):
            sections = [sections]
        cfgparser = configparser.ConfigParser()
        for section in sections:
            cfgparser.add_section(section)
            for option, value in self.config.items(section):
                cfgparser.set(section, option, value)
        return cfgparser

    def get_value(self, section, key, type=str, default=_NO_DEFAULT_SPECIFIED,
                  allow_blank=False):
        self._ensure_config_parsed()

        try:
            val = self.config.get(section, key)
        except configparser.Error:
            return self._handle_no_value(section, key, default)

        if not val.strip() and not allow_blank:
            return self._handle_no_value(section, key, default)

        return self._convert_value(key, section, val, type)

    def override_value(self, section, key, new_value):
        """
        Override a value from the config file with a new value.
        """
        self._ensure_config_parsed()
        self.config.set(section, key, new_value)

    def reset_values(self):
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
        self.config = configparser.ConfigParser()
        if self.config_file and os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            raise SettingsError('%s not found' % (self.config_file))

        # now also read the shadow file if there is one
        # this will overwrite anything that is found in the
        # other config
        if self.shadow_file and os.path.exists(self.shadow_file):
            shadow_config = configparser.ConfigParser()
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
        except Exception:
            msg = ("Could not convert %s value %r in section %s to type %s" %
                   (key, sval, section, value_type))
            raise SettingsValueError(msg)


# insure the class is a singleton.  Now the symbol settings
# will point to the one and only one instace of the class
settings = Settings()
