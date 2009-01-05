#!/usr/bin/python

import os
import common
from autotest_lib.client.bin import utils

# To use this, you have to set PERL5LIB to:
#               autodir+'deps/boottool/lib/perl'
# or on Ubuntu we also need
#               autodir+'deps/boottool/share/perl'
# because it uses nonstandard locations

version = 1

def setup(tarball, topdir):
    srcdir = os.path.join(topdir, 'src')
    utils.extract_tarball_to_dir(tarball, srcdir)
    os.chdir(srcdir)
    utils.system ('perl Makefile.PL PREFIX=' + topdir)
    utils.system ('make')
    utils.system ('make install')
    os.chdir(topdir)


pwd = os.getcwd()
tarball = os.path.join(pwd, 'Linux-Bootloader-1.2.tar.gz')
utils.update_version(pwd+'/src', False, version, setup, tarball, pwd)
