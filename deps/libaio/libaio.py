#!/usr/bin/python
import os
from autotest_utils import *

version = 1
def do_actual_extract(): 
	extract_tarball_to_dir(tarball, 'src')

dir = os.getcwd()

# old source was
# http://www.kernel.org/pub/linux/kernel/people/bcrl/aio/libaio-0.3.92.tar.bz2
# now grabbing from debian
# http://ftp.debian.org/debian/pool/main/liba/libaio/libaio_0.3.106.orig.tar.gz
tarball = 'libaio_0.3.106.orig.tar.gz'

tmpdir = 'tmp'
tarball = unmap_url(dir, tarball, tmpdir)
update_version(dir+'/src', version, do_actual_extract)

os.chdir('src')
system ('make')
system ('make prefix=%s install' % (dir))

