#!/usr/bin/python

import os, sys
import unittest_suite
import common
from autotest_lib.client.common_lib import utils

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def is_valid_directory(dirpath):
    if dirpath.find('client/tests') >= 0:
        return False
    elif dirpath.find('client/site_tests') >= 0:
        return False
    elif dirpath.find('tko/migrations') >= 0:
        return False
    elif dirpath.find('server/tests') >= 0:
        return False
    elif dirpath.find('server/site_tests') >= 0:
        return False
    else:
        return True


def is_valid_filename(f):
    # has to be a .py file
    if not f.endswith('.py'):
        return False

    # but there are execptions
    if f.endswith('_unittest.py'):
        return False
    elif f == '__init__.py':
        return False
    elif f == 'common.py':
        return False
    else:
        return True


def main():
    coverage = os.path.join(root, "contrib/coverage.py")
    unittest_suite = os.path.join(root, "unittest_suite.py")

    # remove preceeding coverage data
    cmd = "%s -e" % (coverage)
    utils.system_output(cmd)

    # run unittest_suite through coverage analysis
    cmd = "%s -x %s" % (coverage, unittest_suite)
    utils.system_output(cmd)

    # now walk through directory grabbing lits of files
    module_strings = []
    for dirpath, dirnames, files in os.walk(root):
        if is_valid_directory(dirpath):
            for f in files:
                if is_valid_filename(f):
                    temp = os.path.join(dirpath, f)
                    module_strings.append(temp)

    # analyze files
    cmd = "%s -r -m %s" % (coverage, " ".join(module_strings))
    utils.system(cmd)


if __name__ == "__main__":
    main()
