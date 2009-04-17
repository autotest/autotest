#!/usr/bin/python

import os
import common
import shutil
from autotest_lib.client.bin import utils

version = 1

def setup(tarball_systemtap, tarball_elfutils, topdir):
    srcdir = os.path.join(topdir, 'src')

    utils.extract_tarball_to_dir(tarball_systemtap, 'src')
    utils.extract_tarball_to_dir(tarball_elfutils, 'elfutils')
    shutil.move('elfutils', 'src')

    os.chdir(srcdir)

    utils.system('./configure --with-elfutils=elfutils ' \
                 '--prefix=%s/systemtap' % topdir)
    utils.system('make -j %d' % utils.count_cpus())
    utils.system('make install')

    os.chdir(topdir)

pwd = os.getcwd()
# http://sourceware.org/systemtap/ftp/releases/systemtap-0.9.5.tar.gz
tarball_systemtap = os.path.join(pwd, 'systemtap-0.9.5.tar.gz')
# https://fedorahosted.org/releases/e/l/elfutils/elfutils-0.140.tar.bz2
tarball_elfutils = os.path.join(pwd, 'elfutils-0.140.tar.bz2')
utils.update_version(pwd+'/src', False, version, setup, tarball_systemtap,
                     tarball_elfutils, pwd)
