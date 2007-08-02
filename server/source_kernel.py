#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the SourceKernel class

	SourceKernel: an linux kernel built from source
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)
"""


import kernel



class SourceKernel(kernel.Kernel):
	"""
	This class represents a linux kernel built from source.
	
	It is used to obtain a built kernel or create one from source and 
	install it on a Host.
	
	Implementation details:
	This is a leaf class in an abstract class hierarchy, it must 
	implement the unimplemented methods in parent classes.
	"""
	def __init__(self):
		super(kernel.Kernel, self).__init__()
		self.__patch_list = []
		self.__config_file = None


	def configure(self, configFile):
		self.__config_file = configFile


	def patch(self, patchFile):
		self.__patch_list.append(patchFile)


	def build(self, host):
		at = autotest.Autotest()
		at.install(host)
		ctlfile = self.control_file(self.__kernel, self.__patch_list,
					    self.__config_file)
		at.run(ctlfile, host.get_tmp_dir(), host)


	def __control_file(self, kernel, patch_list, config):
		ctl = ("def step_init():\n"
		       "\tjob.next_step([step_test])\n"
		       "\ttestkernel = job.kernel('%s')\n" % kernel)

		if len(patch_list):
			 patches = ', '.join(["'%s'" % x for x in patch_list])
			 ctl += "\ttestkernel.patch(%s)" % patches

		if config:
			ctl += "\ttestkernel.config('%s')" % config
		else:
			ctl += "\ttestkernel.config('', None, True)"

		ctl += "\ttestkernel.build()"

		# copy back to server

		return ctl
