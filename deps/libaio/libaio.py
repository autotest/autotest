#!/usr/bin/python
import os
from autotest_utils import *

version = 1
def do_actual_extract(): 
	extract_tarball_to_dir(tarball, 'src')

dir = os.getcwd()

# http://www.kernel.org/pub/linux/kernel/people/bcrl/aio/libaio-0.3.92.tar.bz2
tarball = 'libaio-0.3.92.tar.bz2'

tmpdir = 'tmp'
tarball = unmap_url(dir, tarball, tmpdir)
update_version(dir+'/src', version, do_actual_extract)
system ('cd src && make && make prefix='+dir+' install')

