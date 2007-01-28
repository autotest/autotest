#!/usr/bin/python
from check_version import check_python_version
check_python_version()

import os,os.path,shutil,re
from autotest_utils import *

files = ['/proc/pci', '/proc/meminfo', '/proc/slabinfo', '/proc/version', 
	'/proc/cpuinfo', '/proc/cmdline']
# commands = ['lshw']        # this causes problems triggering CDROM drives
commands = ['uname -a', 'lspci -vvn']
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


for command in commands:
	run_command(command, re.sub(r'\s', '_', command))


for file in files:
	if (os.path.exists(file)):
		shutil.copyfile(file, os.path.basename(file))

