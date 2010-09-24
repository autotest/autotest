#!/usr/bin/python

import os
import shutil
from autotest_lib.client.bin import utils

version = 1

def setup(topdir):
    srcdir = os.path.join(topdir, 'src')

    os.chdir(srcdir)

    utils.configure('--with-elfutils=elfutils ' \
                    '--prefix=%s/systemtap' % topdir)
    utils.make('-j %d' % utils.count_cpus())
    utils.make('install')

    os.chdir(topdir)

pwd = os.getcwd()
utils.update_version(pwd+'/src', True, version, setup, pwd)
