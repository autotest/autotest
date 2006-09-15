import shutil
import re
import os 
import os.path
import string

class boottool:
	def __init__(self, boottool_exec=None):
		if boottool_exec:
			self.boottool_exec = boottool_exec
		else:
                        # TODO:  detect boottool from PATH
			self.boottool_exec = '/usr/bin/boottool'


        def run_boottool(self, params):
                # TODO:  What is ignorestatus?
                # TODO:  Should system_output be used instead?
                return system('%s %s' % (self.boottool_exec, params), ignorestatus=1)

	def bootloader(self):
                return self.run_boottool('--bootloader-probe')

        def architecture(self):
                return self.run_boottool('--arch-probe')

	def list_titles(self):
                print self.run_boottool('--info all | grep title')

	def print_entry(self, index):
                print self.run_boottool('--info=%s' % index)

	def set_default(self, index):
                self.run_boottool('--set-default= %s' % (index) )

        # 'kernel' can be an position number or a title
        def add_args(self, kernel, args):
                self.run_boottool('--update-kernel=%s --args=%s' % (kernel, args) )

        def remove_args(self, kernel, args):
                self.run_boottool('--update-kernel=%s --remove-args=%s' % (kernel, args) )

        def add_kernel(self, path):
                self.run_boottool('--add-kernel=%s' % path)

        def remove_kernel(self, kernel):
                self.run_boottool('--remove-kernel=%s' % kernel)

        def boot_once(self, title):
                self.run_boottool('--boot-once --title=%s' % title)

        def info(self):
                self.run_boottool('--info' % )


# TODO:  backup()
# TODO:  set_timeout()

