import os

"""
One day, when this module grows up, it might actually try to fix things.
'apt-cache search | apt-get install' ... or a less terrifying version of
the same. With added distro-independant pixie dust.
"""

def command(cmd):
    # this could use '/usr/bin/which', I suppose. But this seems simpler
    for dir in os.environ['PATH'].split(':'):
        file = os.path.join(dir, cmd)
        if os.path.exists(file):
            return file
    raise ValueError('Missing command: %s' % cmd)


def commands(*cmds):
    results = []
    for cmd in cmds:
        results.append(command(cmd))


def library(lib):
    lddirs = [x.rstrip() for x in open('/etc/ld.so.conf', 'r').readlines()]
    for dir in ['/lib', '/usr/lib'] + lddirs:
        file = os.path.join(dir, lib)
        if os.path.exists(file):
            return file
    raise ValueError('Missing library: %s' % lib)


def libraries(*libs):
    results = []
    for lib in libs:
        results.append(library(lib))
