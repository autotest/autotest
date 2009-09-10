#!/usr/bin/python
"""
Program that replaces the CD keys present on a KVM autotest configuration file.

@copyright: Red Hat 2008-2009
@author: uril@redhat.com (Uri Lublin)
"""

import shutil, os, sys
import common


def file_to_lines(filename):
    f = open(filename, 'r')
    lines = f.readlines()
    f.close
    return lines

def lines_to_file(filename, lines):
    f = open(filename, 'w')
    f.writelines(lines)
    f.close()

def replace_var_with_val(lines, variables):
    new = []
    for line in lines:
        for (var,val) in variables:
            if var in line:
                print 'replacing %s with %s in "%s"' % (var, val, line[:-1])
                line = line.replace(var, val)
                print ' ... new line is "%s"' % (line[:-1])
        new.append(line)
    return new

def filter_comments(line):
    return not line.strip().startswith('#')

def filter_empty(line):
    return len(line.strip()) != 0

def line_to_pair(line):
    x,y = line.split('=', 1)
    return (x.strip(), y.strip())

def read_vars(varfile):
    varlines = file_to_lines(varfile)
    varlines = filter(filter_comments, varlines)
    varlines = filter(filter_empty,    varlines)
    vars = map(line_to_pair, varlines)
    return vars

def main(cfgfile, varfile):
    # first save a copy of the original file (if does not exist)
    backupfile = '%s.backup' % cfgfile
    if not os.path.exists(backupfile):
        shutil.copy(cfgfile, backupfile)

    vars = read_vars(varfile)
    datalines = file_to_lines(cfgfile)
    newlines = replace_var_with_val(datalines, vars)
    lines_to_file(cfgfile, newlines)


if __name__ == '__main__':
    def die(msg, val):
        print msg
        sys.exit(val)
    if len(sys.argv) != 3:
        die('usage: %s <kvm_tests-config-file> <varfile>', 1)
    cfgfile = sys.argv[1]
    varfile = sys.argv[2]
    if not os.path.exists(cfgfile):
        die('bad cfgfile "%s"' % cfgfile, 2)
    if not os.path.exists(varfile):
        die('bad varfile "%s"' % varfile, 2)
    main(cfgfile, varfile)
