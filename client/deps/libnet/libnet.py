#!/usr/bin/python
from common.check_version import check_python_version
check_python_version()

import os
from autotest_utils import *

version = 1

def setup(tarball, topdir): 
	srcdir = os.path.join(topdir, 'src')
	if not os.path.exists(tarball):
		get_file('http://www.packetfactory.net/libnet/dist/libnet.tar.gz', tarball)
	extract_tarball_to_dir(tarball, 'src')
	os.chdir(srcdir)
	system ('./configure --prefix=%s/libnet' % topdir)
	system('make')
	system('make install')

	os.chdir(topdir)
	
pwd = os.getcwd()
tarball = os.path.join(pwd, 'libnet.tar.gz')
update_version(pwd+'/src', False, version, setup, tarball, pwd)
