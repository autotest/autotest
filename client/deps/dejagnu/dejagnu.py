#!/usr/bin/python

import os
from autotest_lib.client.bin import utils

version = 1

def setup(tarball, topdir):
    srcdir = os.path.join(topdir, 'src')
    utils.extract_tarball_to_dir(tarball, 'src')
    os.chdir(srcdir)
    utils.configure('--prefix=%s/dejagnu' % topdir)
    utils.make()
    utils.make('install')

    os.chdir(topdir)

pwd = os.getcwd()
# http://ftp.gnu.org/pub/gnu/dejagnu/dejagnu-1.4.4.tar.gz
tarball = os.path.join(pwd, 'dejagnu-1.4.4.tar.bz2')
utils.update_version(pwd+'/src', False, version, setup, tarball, pwd)
