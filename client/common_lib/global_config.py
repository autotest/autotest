"""A singleton class for accessing global config values

provides access to global configuration file
"""

__author__ = 'raphtee@google.com (Travis Miller)'

import os
import ConfigParser
import error

class ConfigError(error.AutotestError):
	pass


class global_config(object):

	config = None

	def get_config_value(self, section, key, default=None):
	        if self.config == None:
	        	self.parse_config_file()
	        	
	        try:
	        	return self.config.get(section, key)
	        except: 
	        	if default == None:
				raise ConfigError("config value not found")
			else:
				return default
	
		
	def parse_config_file(self):
		dirname = os.path.dirname(sys.modules[__name__].__file__)
		root = os.path.abspath(os.path.join(dirname, "../../"))
		config_file = os.path.join(root, "global_config.ini")
		self.config = ConfigParser.ConfigParser()
		self.config.read(config_file)

		

# insure the class is a singleton.  Now the symbol global_config 
# will point to the one and only one instace of the class
global_config = global_config()
