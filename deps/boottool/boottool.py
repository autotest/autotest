#!/usr/bin/python
import os
from autotest_utils import *

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
update_version(pwd+'/src', version, setup, tarball, pwd)

