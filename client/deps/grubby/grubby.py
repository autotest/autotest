#!/usr/bin/python

import os
from autotest.client import utils

version = 1


def setup(tarball, topdir):
    srcdir = os.path.join(topdir, 'src')
    utils.extract_tarball_to_dir(tarball, srcdir)
    os.chdir(srcdir)
    utils.make()
    os.environ['MAKEOPTS'] = 'mandir=/usr/share/man'
    utils.make('install')
    os.chdir(topdir)

pwd = os.getcwd()
tarball = os.path.join(pwd, 'grubby-8.15.tar.bz2')
utils.update_version(os.path.join(pwd, 'src'),
                     False, version, setup, tarball, pwd)
