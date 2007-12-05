"""
Wrapper around ConfigParser to manage testcases configuration.
"""

__author__ = 'rsalveti@linux.vnet.ibm.com (Ricardo Salveti de Araujo)'

from ConfigParser import ConfigParser
from os import path

__all__ = ['config_loader']

class config_loader:
	"""Base class of the configuration parser"""
	def __init__(self, filename="test.conf"):
		self.filename = filename
		if not path.isfile(self.filename):
			raise IOError, "File '%s' not found" % (self.filename)
		self.parser = ConfigParser()
		self.parser.read(self.filename)


	def get(self, section, name, default=None):
		"""Get the value of a option.

		Section of the config file and the option name.
		You can pass a default value if the option doesn't exist.
		"""
		if not self.parser.has_option(section, name):
			return default
		return self.parser.get(section, name)


	def set(self, section, option, value):
		"""Set an option.

		This change is not persistent unless saved with 'save()'.
		"""
		if not self.parser.has_section(section):
			self.parser.add_section(section)
		return self.parser.set(section, name, value)


	def remove(self, section, name):
		"""Remove an option."""
		if self.parser.has_section(section):
			self.parser.remove_option(section, name)


	def save(self):
		"""Save the configuration file with all modifications"""
		if not self.filename:
			return
		fileobj = file(self.filename, 'w')
		try:
			self.parser.write(fileobj)
		finally:
			fileobj.close()
