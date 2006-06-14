#!/usr/bin/python
import os
from autotest_utils import *
version = 1
def do_actual_extract(): 
	print 'func being called'	
	extract_tarball_to_dir(tarball, 'src')

dir = os.getcwd()
tarball = 'libaio-0.3.92.tar.bz2'
# http://www.kernel.org/pub/linux/kernel/people/bcrl/aio/libaio-0.3.92.tar.bz2
tmpdir = 'tmp'
tarball = unmap_url(dir, tarball, tmpdir)
update_version(dir+'/src', version, do_actual_extract)
system ('cd src && make && make prefix='+dir+' install')

