#!/usr/bin/python

import os
from autotest.client import utils

version = 2


def setup(tarball, topdir):
    srcdir = os.path.join(topdir, 'src')
    utils.extract_tarball_to_dir(tarball, srcdir)
    os.chdir(srcdir)
    utils.make()
    utils.make('prefix=%s install' % topdir)
    os.chdir(topdir)

# https://git.fedorahosted.org/cgit/libaio.git/snapshot/libaio-0.3.110-1.tar.gz

pwd = os.getcwd()
tarball = os.path.join(pwd, 'libaio-0.3.110-1.tar.gz')
utils.update_version(pwd + '/src', False, version, setup, tarball, pwd)
