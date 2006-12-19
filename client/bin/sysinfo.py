#!/usr/bin/python
from check_version import check_python_version
check_python_version()

import os,os.path,shutil
from autotest_utils import *

files = ['/proc/pci', '/proc/meminfo', '/proc/slabinfo', '/proc/version', 
	'/proc/cpuinfo']
commands = ['lshw', 'uname -a', 'lspci -vvn']
path = ['/usr/bin', '/bin']

def run_command(command, output):
	for dir in path:
		pathname = dir + '/' + command
		if (os.path.exists(pathname)):
			system(pathname + ' > ' + output + ' 2> /dev/null')

for command in commands:
	run_command(command, os.path.basename(command))

for file in files:
	if (os.path.exists(file)):
		shutil.copyfile(file, os.path.basename(file))

