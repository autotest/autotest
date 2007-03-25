#!/usr/bin/python
from check_version import check_python_version
check_python_version()

import os
from autotest_utils import *

# To use this, you have to set PERL5LIB to:
# 		autodir+'deps/boottool/lib/perl' 
# or on Ubuntu we also need
# 		autodir+'deps/boottool/share/perl'
# because it uses nonstandard locations

version = 1

def setup(tarball, topdir): 
	srcdir = os.path.join(topdir, 'src')
	extract_tarball_to_dir(tarball, srcdir)
	os.chdir(srcdir)
	system ('perl Makefile.PL PREFIX=' + topdir)
	system ('make')
	system ('make install')
	os.chdir(topdir)


pwd = os.getcwd()
tarball = os.path.join(pwd, 'Linux-Bootloader-1.2.tar.gz')
update_version(pwd+'/src', False, version, setup, tarball, pwd)

