#!/usr/bin/python
from check_version import check_python_version
check_python_version()

import os,os.path,shutil,re,glob
from autotest_utils import *
dirname = os.path.dirname(sys.modules['sysinfo'].__file__)
if os.path.exists(os.path.join(dirname,'site_sysinfo.py')):
	import site_sysinfo
	local = True
else:
	local = False

# stuff to log in before_each_step()
files = ['/proc/pci', '/proc/meminfo', '/proc/slabinfo', '/proc/version', 
	'/proc/cpuinfo', '/proc/cmdline']
# commands = ['lshw']        # this causes problems triggering CDROM drives
commands = ['uname -a', 'lspci -vvn', 'gcc --version', 'ld --version', 'hostname']
path = ['/usr/bin', '/bin']


def run_command(command, output):
	parts = command.split(None, 1)
	cmd = parts[0]
	if len(parts) > 1:
		args = parts[1]
	else:
		args = ''
	for dir in path:
		pathname = dir + '/' + cmd
		if (os.path.exists(pathname)):
			system("%s %s > %s 2> /dev/null" % (pathname, args, output))


def before_each_step():
	# make separate directories for each step:
	# if files exist here, this is not the first step.
	# this is a safe assumption because we always create at least one file
	if not glob.glob('*'):
		_before_each_step() # first step goes in cwd
		return

	previous_reboots = glob.glob('reboot*')
	if previous_reboots:
		previous_reboots = [int(i[len('reboot'):]) for i in previous_reboots]
		boot = 1 + max(previous_reboots)
	else:
		boot = 1

	os.mkdir('reboot%d' % boot)
	pwd = os.getcwd()

	try:
		os.chdir('reboot%d' % boot)
		_before_each_step()
	finally:
		os.chdir(pwd)


def _before_each_step():
	"""system info to log before each step of the job"""

	for command in commands:
		run_command(command, re.sub(r'\s', '_', command))

	for file in files:
		if (os.path.exists(file)):
			shutil.copyfile(file, os.path.basename(file))


	system('dmesg -c > dmesg', ignorestatus=1)
	system('df -m > df', ignorestatus=1)
	if local:
		site_sysinfo.before_each_step()


def after_each_test():
	"""log things that change after each test (see test.py)"""

	system('dmesg -c > dmesg', ignorestatus=1)
	system('df -m > df', ignorestatus=1)
	if local:
		site_sysinfo.after_each_test()


if __name__ == '__main__':
	before_each_step()
