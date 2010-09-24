#!/usr/bin/python

import os
from autotest_lib.client.bin import utils

version = 2

def setup(srcdir, tarball='libcap-2.16.tar.gz'):
    topdir = os.getcwd()
    utils.extract_tarball_to_dir(tarball, srcdir)
    os.chdir(srcdir)
    utils.make('-C libcap LIBATTR=no')
    os.chdir(topdir)

srcdir = os.path.abspath('./src')
utils.update_version(srcdir, False, version, setup, srcdir)
