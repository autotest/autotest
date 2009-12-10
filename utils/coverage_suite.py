#!/usr/bin/python

import os, sys
import unittest_suite
from autotest_lib.client.common_lib import utils


root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


invalid_dirs = ['client/tests/', 'client/site_tests/', 'tko/migrations/',
                'server/tests/', 'server/site_tests/', 'server/self-test/',
                'contrib/', 'utils/', 'ui/', 'frontend/migrations',
                'frontend/afe/simplejson/', 'metrics/', 'old_cli/',
                'client/common_lib/test_utils/', 'client/profilers/',
                'site_packages']
# append site specific invalid_dirs list, if any
invalid_dirs.extend(utils.import_site_symbol(
    __file__, 'autotest_lib.utils.site_coverage_suite', 'invalid_dirs', []))


invalid_files = ['unittest_suite.py', 'coverage_suite.py', '__init__.py',
                 'common.py']
# append site specific invalid_files list, if any
invalid_files.extend(utils.import_site_symbol(
    __file__, 'autotest_lib.utils.site_coverage_suite', 'invalid_files', []))


def is_valid_directory(dirpath):
    dirpath += '/'
    for invalid_dir in invalid_dirs:
        if dirpath.startswith(os.path.join(root, invalid_dir)):
            return False

    return True


def is_test_filename(filename):
    return (filename.endswith('_unittest.py') or filename.endswith('_test.py'))


def is_valid_filename(f):
    # has to be a .py file
    if not f.endswith('.py'):
        return False

    # but there are exceptions
    if is_test_filename(f):
        return False
    elif f in invalid_files:
        return False
    else:
        return True


def run_unittests(prog, dirname, files):
    for f in files:
        if is_test_filename(f):
            testfile = os.path.abspath(os.path.join(dirname, f))
            cmd = "%s -x %s" % (prog, testfile)
            utils.system_output(cmd, ignore_status=True, timeout=100)


def main():
    coverage = os.path.join(root, "contrib/coverage.py")

    # remove preceeding coverage data
    cmd = "%s -e" % (coverage)
    os.system(cmd)

    # I know this looks weird but is required for accurate results
    cmd = "cd %s && find . -name '*.pyc' | xargs rm" % root
    os.system(cmd)

    # now walk through directory grabbing list of files
    if len(sys.argv) == 2:
        start = os.path.join(root, sys.argv[1])
    else:
        start = root

    # run unittests through coverage analysis
    os.path.walk(start, run_unittests, coverage)

    module_strings = []
    for dirpath, dirnames, files in os.walk(start):
        if is_valid_directory(dirpath):
            for f in files:
                if is_valid_filename(f):
                    temp = os.path.join(dirpath, f)
                    module_strings.append(temp)

    # analyze files
    cmd = "%s -r -m %s" % (coverage, " ".join(module_strings))
    os.system(cmd)


if __name__ == "__main__":
    main()
