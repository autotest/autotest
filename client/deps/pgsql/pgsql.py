#!/usr/bin/python

import os
import common
from autotest_lib.client.bin import utils

version = 4

def setup(tarball, topdir):
    srcdir = os.path.join(topdir, 'src')
    if not os.path.exists(tarball):
        utils.get_file('ftp://ftp.postgresql.org/pub/source/v8.3.1/postgresql-8.3.1.tar.bz2', tarball)
    utils.extract_tarball_to_dir(tarball, 'src')
    os.chdir(srcdir)
    utils.system ('./configure --without-readline --without-zlib --enable-debug --prefix=%s/pgsql' % topdir)
    utils.system('make -j %d' % utils.count_cpus())
    utils.system('make install')

    os.chdir(topdir)

pwd = os.getcwd()
tarball = os.path.join(pwd, 'postgresql-8.3.1.tar.bz2')
utils.update_version(pwd+'/src', False, version, setup, tarball, pwd)
