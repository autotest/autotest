#!/usr/bin/python
import os
from autotest_utils import *

version = 1

def setup(tarball, topdir): 
	srcdir = os.path.join(topdir, 'src')
	if not os.path.exists(tarball):
		get_file('http://mirror.x10.com/mirror/mysql/Downloads/MySQL-5.0/mysql-5.0.24a.tar.gz', tarball)
	extract_tarball_to_dir(tarball, 'src')
	os.chdir(srcdir)
	system ('./configure --prefix=%s/mysql --enable-thread-safe-client' \
			% topdir)
	system('make -j %d' % count_cpus())
	system('make install')

	#
	# MySQL doesn't create this directory on it's own.  This is where database
	# logs and files are created.
	#
	os.mkdir(topdir + '/mysql/var')
	#
	# Initialize the database.
	#
	system('%s/mysql/bin/mysql_install_db' % topdir)
	
	os.chdir(topdir)
	
pwd = os.getcwd()
tarball = os.path.join(pwd, 'mysql-5.0.24a.tar.gz')
update_version(pwd+'/src', version, setup, tarball, pwd)


