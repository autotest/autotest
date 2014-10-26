#!/usr/bin/python

import os
from autotest.client import utils

version = 1
#DEPS: libaio

def setup(tarball, topdir):
    srcdir = os.path.join(topdir, 'src')
    depsdir = os.path.join(topdir, '../')

    utils.extract_tarball_to_dir(tarball, srcdir)
    os.chdir(srcdir)

    ldflags = '-L' + depsdir + 'libaio/lib'
    cflags = '-I' +  depsdir + 'libaio/include'
    env = []
    env.append('LDFLAGS="' + ldflags + '"')
    env.append(' CFLAGS="' + cflags + '"')
    env.append(' LLDFLAGS=-all-static')
    configure_cmd = '%s ./configure' % ''.join(env)
    make_cmd = '%s make' % ''.join(env)

    utils.configure('--prefix=%s/e2fsprogs' % topdir, configure = configure_cmd)
    utils.make(' -j %d' % utils.count_cpus(), make = make_cmd)
    utils.make('install', make = make_cmd)

    os.chdir(topdir)

#ftp://ftp.kernel.org/pub/linux/kernel/people/tytso/e2fsprogs/v1.42.12/e2fsprogs-1.42.12.tar.gz
pwd = os.getcwd()
tarball = os.path.join(pwd, 'e2fsprogs-1.42.12.tar.gz')
utils.update_version(pwd + '/src', False, version, setup, tarball, pwd)
