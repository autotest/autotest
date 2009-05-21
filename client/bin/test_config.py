"""
Wrapper around ConfigParser to manage testcases configuration.
"""

__author__ = 'rsalveti@linux.vnet.ibm.com (Ricardo Salveti de Araujo)'

from ConfigParser import ConfigParser
from StringIO import StringIO
from os import path
import types, re, string
from autotest_lib.client.common_lib import utils

__all__ = ['config_loader']

class config_loader:
    """Base class of the configuration parser"""
    def __init__(self, cfg, tmpdir = '/tmp'):
        """\
        Instantiate ConfigParser and provide the file like object that we'll
        use to read configuration data from.
        Args:
                * cfg: Where we'll get configuration data. It can be either:
                        * A URL containing the file
                        * A valid file path inside the filesystem
                        * A string containing configuration data
                * tmpdir: Where we'll dump the temporary conf files. The default
                is the /tmp directory.
        """
        # Base Parser
        self.parser = ConfigParser()
        # File is already a file like object
        if hasattr(cfg, 'read'):
            self.cfg = cfg
            self.parser.readfp(self.cfg)
        elif isinstance(cfg, types.StringTypes):
            # Config file is a URL. Download it to a temp dir
            if cfg.startswith('http') or cfg.startswith('ftp'):
                self.cfg = path.join(tmpdir, path.basename(cfg))
                utils.urlretrieve(cfg, self.cfg)
                self.parser.read(self.cfg)
            # Config is a valid filesystem path to a file.
            elif path.exists(path.abspath(cfg)):
                if path.isfile(cfg):
                    self.cfg = path.abspath(cfg)
                    self.parser.read(self.cfg)
                else:
                    e_msg = 'Invalid config file path: %s' % cfg
                    raise IOError(e_msg)
            # Config file is just a string, convert it to a python file like
            # object using StringIO
            else:
                self.cfg = StringIO(cfg)
                self.parser.readfp(self.cfg)


    def get(self, section, option, default=None):
        """Get the value of a option.

        Section of the config file and the option name.
        You can pass a default value if the option doesn't exist.
        """
        if not self.parser.has_option(section, option):
            return default
        return self.parser.get(section, option)


    def set(self, section, option, value):
        """Set an option.

        This change is not persistent unless saved with 'save()'.
        """
        if not self.parser.has_section(section):
            self.parser.add_section(section)
        return self.parser.set(section, option, value)


    def remove(self, section, option):
        """Remove an option."""
        if self.parser.has_section(section):
            self.parser.remove_option(section, option)


    def save(self):
        """Save the configuration file with all modifications"""
        if not self.cfg:
            return
        fileobj = file(self.cfg, 'w')
        try:
            self.parser.write(fileobj)
        finally:
            fileobj.close()


    def check(self, section):
        """
        Check if the config file has valid values
        """
        if not self.parser.has_section(section):
            return False, "Section not found: %s"%(section)

        options = self.parser.items(section)
        for i in range(options.__len__()):
            param = options[i][0]
            aux = string.split(param, '.')

            if aux.__len__ < 2:
                return False, "Invalid parameter syntax at %s"%(param)

            if not self.check_parameter(aux[0], options[i][1]):
                return False, "Invalid value at %s"%(param)

        return True, None


    def check_parameter(self, param_type, parameter):
        """
        Check if a option has a valid value
        """
        if parameter == '' or parameter == None:
            return False
        elif param_type == "ip" and self.__isipaddress(parameter):
            return True
        elif param_type == "int" and self.__isint(parameter):
            return True
        elif param_type == "float" and self.__isfloat(parameter):
            return True
        elif param_type == "str" and self.__isstr(parameter):
            return True

        return False


    def __isipaddress(self, parameter):
        """
        Verify if the ip address is valid

        @param ip String: IP Address
        @return True if a valid IP Address or False
        """
        octet1 = "([1-9][0-9]{,1}|1[0-9]{2}|2[0-4][0-9]|25[0-5])"
        octet = "([0-9]{1,2}|1[0-9]{2}|2[0-4][0-9]|25[0-5])"
        pattern = "^" + octet1 + "\.(" + octet + "\.){2}" + octet + "$"
        if re.match(pattern, parameter) == None:
            return False
        else:
            return True


    def __isint(self, parameter):
        try:
            int(parameter)
        except Exception, e_stack:
            return False
        return True


    def __isfloat(self, parameter):
        try:
            float(parameter)
        except Exception, e_stack:
            return False
        return True


    def __isstr(self, parameter):
        try:
            str(parameter)
        except Exception, e_stack:
            return False
        return True
