#!/usr/bin/python

import os, common
from autotest_lib.client.common_lib import utils
from autotest_lib.client.bin import autotest_utils

version = 2

def setup(srcdir, tarball='libcap-2.16.tar.gz'):
    topdir = os.getcwd()
    autotest_utils.extract_tarball_to_dir(tarball, srcdir)
    os.chdir(srcdir)
    utils.system('make -C libcap LIBATTR=no')
    os.chdir(topdir)

srcdir = os.path.abspath('./src')
utils.update_version(srcdir, False, version, setup, srcdir)
