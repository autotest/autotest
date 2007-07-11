#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This module defines the Kernel class

	Kernel: an os kernel
"""

__author__ = """mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)"""


import os
import os.path
import time
import urllib

import kernel
import errors
import utils


class DEBKernel(kernel.Kernel):
	"""This class represents a .deb pre-built kernel.

	It is used to obtain a built kernel and install it on a Host.

	Implementation details:
	This is a leaf class in an abstract class hierarchy, it must
	implement the unimplemented methods in parent classes.
	"""
	def __init__(self):
		super(DEBKernel, self).__init__()


	def get_from_file(self, filename):
		if os.path.exists(filename):
			self.__filename = filename
		else:
			raise errors.AutoservError('%s not found' % filename)


	def get_from_url(self, url):
		tmpdir = utils.get_tmp_dir()
		tmpfile = os.path.join(tmpdir, os.path.basename(url))
		urllib.urlretrieve(url, tmpfile)
		self.__filename = tmpfile


	def install(self, host):
		# this directory will get cleaned up for us automatically
		remote_tmpdir = host.get_tmp_dir()
		basename = os.path.basename(self.__filename)
		remote_filename = os.path.join(remote_tmpdir, basename)
		host.send_file(self.__filename, remote_filename)
		try:
			result = host.run('dpkg -i %s'
					  % remote_filename)
			if result.exit_status:
				raise AutoservError('dpkg failed \
				installing %s:\n\n%s'% (remote_filename,
							result.stderr))
		except NameError, e:
			raise AutoservError('A kernel must first be \
			specified via get_from_file or get_from_url')
