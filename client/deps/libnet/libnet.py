#!/usr/bin/python

import os
import common
from autotest_lib.client.bin import utils

version = 1

def setup(tarball, topdir):
    srcdir = os.path.join(topdir, 'src')
    if not os.path.exists(tarball):
        utils.get_file('http://www.packetfactory.net/libnet/dist/libnet.tar.gz',
                       tarball)
    utils.extract_tarball_to_dir(tarball, 'src')
    os.chdir(srcdir)
    utils.system ('./configure --prefix=%s/libnet' % topdir)
    utils.system('make')
    utils.system('make install')

    os.chdir(topdir)

pwd = os.getcwd()
tarball = os.path.join(pwd, 'libnet.tar.gz')
utils.update_version(pwd+'/src', False, version, setup, tarball, pwd)
