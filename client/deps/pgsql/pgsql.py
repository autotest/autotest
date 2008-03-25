#!/usr/bin/python
from common.check_version import check_python_version
check_python_version()

import os
from autotest_utils import *

version = 4

def setup(tarball, topdir): 
	srcdir = os.path.join(topdir, 'src')
	if not os.path.exists(tarball):
		get_file('ftp://ftp.postgresql.org/pub/source/v8.3.1/postgresql-8.3.1.tar.bz2', tarball)
	extract_tarball_to_dir(tarball, 'src')
	os.chdir(srcdir)
	system ('./configure --without-readline --without-zlib --enable-debug --prefix=%s/pgsql' % topdir)
	system('make -j %d' % count_cpus())
	system('make install')
	
	os.chdir(topdir)
	
pwd = os.getcwd()
tarball = os.path.join(pwd, 'postgresql-8.3.1.tar.bz2')
update_version(pwd+'/src', False, version, setup, tarball, pwd)


