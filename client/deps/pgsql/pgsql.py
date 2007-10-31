#!/usr/bin/python
from check_version import check_python_version
check_python_version()

import os
from autotest_utils import *

version = 2

def setup(tarball, topdir): 
	srcdir = os.path.join(topdir, 'src')
	if not os.path.exists(tarball):
		get_file('ftp://ftp.us.postgresql.org/pub/mirrors/postgresql/v8.2.5/postgresql-8.2.5.tar.bz2', tarball)
	extract_tarball_to_dir(tarball, 'src')
	os.chdir(srcdir)
	system ('./configure --enable-debug --prefix=%s/pgsql' % topdir)
	system('make -j %d' % count_cpus())
	system('make install')
	
	os.chdir(topdir)
	
pwd = os.getcwd()
tarball = os.path.join(pwd, 'postgresql-8.2.5.tar.bz2')
update_version(pwd+'/src', False, version, setup, tarball, pwd)


