import shutil, re, os, os.path, string
from autotest_utils import *

class boottool:
	def __init__(self, boottool_exec=None):
		if boottool_exec:
			self.boottool_exec = boottool_exec
		else:
			autodir = os.environ['AUTODIR']
			self.boottool_exec = autodir + '/tools/boottool'

	def run_boottool(self, params):
		return system_output('%s %s' % (self.boottool_exec, params))

	def bootloader(self):
		return self.run_boottool('--bootloader-probe')

	def architecture(self):
		return self.run_boottool('--arch-probe')

	def list_titles(self):
		print self.run_boottool('--info all | grep title')

	def print_entry(self, index):
		print self.run_boottool('--info=%s' % index)

	def get_default(self):
		self.run_boottool('--default')

	def set_default(self, index):
		self.run_boottool('--set-default=%s' % index)

	# 'kernel' can be an position number or a title
	def add_args(self, kernel, args):
		self.run_boottool('--update-kernel=%s --args=%s' % \
							(kernel, args) )

	def remove_args(self, kernel, args):
		self.run_boottool('--update-kernel=%s --remove-args=%s' % \
							(kernel, args) )

	def add_kernel(self, path, title='autotest', initrd=''):
		# boot tool needs a dummy argument for add_args to work
		parameters = '--add-kernel=%s --title=%s --args=dummy' % \
							(path, title)
		# add an initrd now or forever hold your peace
		if initrd:
			parameters += ' --initrd=%s' % initrd
		self.run_boottool(parameters)


	def remove_kernel(self, kernel):
		self.run_boottool('--remove-kernel=%s' % kernel)

	def boot_once(self, title):
		self.run_boottool('--boot-once --title=%s' % title)

	def info(self, index):
		return self.run_boottool('--info=%s' % index)


# TODO:  backup()
# TODO:  set_timeout()

