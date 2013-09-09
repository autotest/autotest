import os
import glob

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
    lddirs = []
    # read lddirs from  main ld.so.conf file
    for line in open('/etc/ld.so.conf', 'r').readlines():
        line = line.strip()
        if line.startswith('include '):
            glob_pattern = line.split('include ')[1]
            if not os.path.isabs(glob_pattern):
                # prepend with a base path of '/etc'
                glob_pattern = os.path.join('/etc', glob_pattern)
            glob_result = glob.glob(glob_pattern)
            for conf_file in glob_result:
                for conf_file_line in open(conf_file, 'r').readlines():
                    if os.path.isdir(conf_file_line.strip()):
                        lddirs.append(conf_file_line.strip())
        else:
            if os.path.isdir(line):
                lddirs.append(line)

    lddirs = set(lddirs)
    lddirs = list(lddirs)

    for dir in ['/lib', '/usr/lib', '/lib64', '/usr/lib64'] + lddirs:
        file = os.path.join(dir, lib)
        if os.path.exists(file):
            return file
    raise ValueError('Missing library: %s' % lib)


def libraries(*libs):
    results = []
    for lib in libs:
        results.append(library(lib))


def header(hdr):
    for dir in ['/usr/include', '/usr/local/include']:
        file = os.path.join(dir, hdr)
        if os.path.exists(file):
            return file
    raise ValueError('Missing header: %s' % hdr)


def headers(*hdrs):
    results = []
    for hdr in hdrs:
        results.append(header(hdr))
