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

    utils.configure('--extra-cflags="%s"' % cflags,
                    configure = configure_cmd)
    utils.make('-j %d' % utils.count_cpus(), make = make_cmd)
    utils.make('prefix=%s/fio install' % topdir, make = make_cmd)

pwd = os.getcwd()
tarball = os.path.join(pwd, 'fio-2.1.13-77-g0f9940a.tar.gz')
utils.update_version(pwd + '/src', False, version, setup, tarball, pwd)
