#!/usr/bin/python

import os
from autotest.client import utils

version = 1

def setup(tarball, topdir):
    srcdir = os.path.join(topdir, 'src')
    utils.extract_tarball_to_dir(tarball, srcdir)
    os.chdir(srcdir)
    utils.system('patch -p1 < ../00_arches.patch')
    utils.make()
    utils.make('prefix=%s install' % topdir)
    os.chdir(topdir)


# old source was
# http://www.kernel.org/pub/linux/kernel/people/bcrl/aio/libaio-0.3.92.tar.bz2
# now grabbing from debian
# http://ftp.debian.org/debian/pool/main/liba/libaio/libaio_0.3.106.orig.tar.gz
# architecture patch from here
# http://git.hadrons.org/?p=debian/pkgs/libaio.git;a=tree;f=debian/patches

pwd = os.getcwd()
tarball = os.path.join(pwd, 'libaio_0.3.106.orig.tar.gz')
utils.update_version(pwd+'/src', False, version, setup, tarball, pwd)
