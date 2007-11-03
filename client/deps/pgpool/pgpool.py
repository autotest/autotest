#!/usr/bin/python
from check_version import check_python_version
check_python_version()

import os
from autotest_utils import *

version = 1

def setup(tarball, topdir): 
	# FIXME - Waiting to be able to specify dependency.
	#self.job.setup_dep(['pgsql'])
	srcdir = os.path.join(topdir, 'src')
	if not os.path.exists(tarball):
		get_file('http://pgfoundry.org/frs/download.php/1083/pgpool-II-1.0.1.tar.gz', tarball)
	extract_tarball_to_dir(tarball, 'src')
	os.chdir(srcdir)
	# FIXEME - Waiting to be able to use self.autodir instead of
	# os.environ['AUTODIR']
	system('./configure --prefix=%s/pgpool --with-pgsql=%s/deps/pgsql/pgsql' \
			% (topdir, os.environ['AUTODIR']))
	system('make -j %d' % count_cpus())
	system('make install')

	os.chdir(topdir)
	
pwd = os.getcwd()
tarball = os.path.join(pwd, 'pgpool-II-1.0.1.tar.gz')
update_version(pwd+'/src', False, version, setup, tarball, pwd)
