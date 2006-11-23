#!/usr/bin/python
import os
from autotest_utils import *

version = 1

def setup(tarball, topdir): 
	srcdir = os.path.join(topdir, 'src')
	extract_tarball_to_dir(tarball, srcdir)
	os.chdir(srcdir)
	system ('make')
	system ('make prefix=%s install' % topdir)
	os.chdir(topdir)


# old source was
# http://www.kernel.org/pub/linux/kernel/people/bcrl/aio/libaio-0.3.92.tar.bz2
# now grabbing from debian
# http://ftp.debian.org/debian/pool/main/liba/libaio/libaio_0.3.106.orig.tar.gz

pwd = os.getcwd()
tarball = os.path.join(pwd, 'libaio_0.3.106.orig.tar.gz')
update_version(pwd+'/src', version, setup, tarball, pwd)

