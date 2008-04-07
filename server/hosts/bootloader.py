#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the Bootloader class.

	Bootloader: a program to boot Kernels on a Host.
"""

__author__ = """
mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)
"""

import os.path
import sys
import weakref

import utils

from common.error import *


BOOTTOOL_SRC = '../client/tools/boottool'  # Get it from autotest client


class Bootloader(object):
	"""
	This class represents a bootloader.

	It can be used to add a kernel to the list of kernels that can be 
	booted by a bootloader. It can also make sure that this kernel will 
	be the one chosen at next reboot.
	"""

	def __init__(self, host, xen_mode=False):
		super(Bootloader, self).__init__()
		self.__host = weakref.ref(host)
		self.__boottool_path = None
		self.xen_mode = xen_mode


	def get_type(self):
		return self.__run_boottool('--bootloader-probe').stdout.strip()


	def get_architecture(self):
		return self.__run_boottool('--arch-probe').stdout.strip()


	def get_titles(self):
		return self.__run_boottool('--info all | grep title | '
			'cut -d " " -f2-').stdout.strip().split('\n')


	def get_default(self):
		return self.__run_boottool('--default').stdout.strip()


	def __get_info(self, info_id):
		retval = self.__run_boottool('--info=%s' % info_id).stdout

		results = []
		info = {}
		for line in retval.splitlines():
			if not line.strip():
				if info:
					results.append(info)
					info = {}
			else:
				key, val = line.split(":", 1)
				info[key.strip()] = val.strip()
		if info:
			results.append(info)

		return results


	def get_info(self, index):
		results = self.__get_info(index)
		if results:
			return results[0]
		else:
			return {}


	def get_all_info(self):
		return self.__get_info('all')


	def set_default(self, index):
		self.__run_boottool('--set-default=%s' % index)


	# 'kernel' can be a position number or a title
	def add_args(self, kernel, args):
		parameters = '--update-kernel=%s --args="%s"' % (kernel, args)
		
		#add parameter if this is a Xen entry
		if self.xen_mode:
			parameters += ' --xen'
		
		self.__run_boottool(parameters)


	def add_xen_hypervisor_args(self, kernel, args):
		self.__run_boottool('--xen --update-xenhyper=%s --xha="%s"' \
				    % (kernel, args))


	def remove_args(self, kernel, args):
		params = '--update-kernel=%s --remove-args=%s' % (kernel, args)
		
		#add parameter if this is a Xen entry
		if self.xen_mode:
			params += ' --xen'
		
		self.__run_boottool(params)


	def remove_xen_hypervisor_args(self, kernel, args):
		self.__run_boottool('--xen --update-xenhyper=%s '
			'--remove-args="%s"') % (kernel, args)


	def add_kernel(self, path, title='autoserv', root=None, args=None, 
		initrd=None, xen_hypervisor=None, default=True):
		"""
		If an entry with the same title is already present, it will be 
		replaced.
		"""
		if title in self.get_titles():
			self.__run_boottool('--remove-kernel "%s"' % (
				utils.sh_escape(title),))
		
		parameters = '--add-kernel "%s" --title "%s"' % (
			utils.sh_escape(path), utils.sh_escape(title),)
		
		if root:
			parameters += ' --root "%s"' % (utils.sh_escape(root),)
		
		if args:
			parameters += ' --args "%s"' % (utils.sh_escape(args),)
		
		# add an initrd now or forever hold your peace
		if initrd:
			parameters += ' --initrd "%s"' % (
				utils.sh_escape(initrd),)
		
		if default:
			parameters += ' --make-default'
		
		# add parameter if this is a Xen entry
		if self.xen_mode:
			parameters += ' --xen'
			if xen_hypervisor:
				parameters += ' --xenhyper "%s"' % (
					utils.sh_escape(xen_hypervisor),)
		
		self.__run_boottool(parameters)


	def remove_kernel(self, kernel):
		self.__run_boottool('--remove-kernel=%s' % kernel)


	def boot_once(self, title):
		self.__run_boottool('--boot-once --title=%s' % title)


	def install_boottool(self):
		if self.__host() is None:
			raise AutoservError("Host does not exist anymore")
		tmpdir = self.__host().get_tmp_dir()
		self.__host().send_file(os.path.abspath(os.path.join(
			utils.get_server_dir(), BOOTTOOL_SRC)), tmpdir)
		self.__boottool_path= os.path.join(tmpdir, 
			os.path.basename(BOOTTOOL_SRC))


	def __get_boottool_path(self):
		if not self.__boottool_path:
			self.install_boottool()
		return self.__boottool_path


	def __set_boottool_path(self, path):
		self.__boottool_path = path

	
	boottool_path = property(__get_boottool_path, __set_boottool_path)


	def __run_boottool(self, cmd):
		return self.__host().run(self.boottool_path + ' ' + cmd)
