"""
Wrapper around ConfigParser to manage testcases configuration.
"""

__author__ = 'rsalveti@linux.vnet.ibm.com (Ricardo Salveti de Araujo)'

from ConfigParser import ConfigParser
from StringIO import StringIO
from os import path
import types
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
