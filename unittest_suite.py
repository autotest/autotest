#!/usr/bin/python

import os, sys, unittest
import common
from autotest_lib.client.common_lib import utils

root = os.path.abspath(os.path.dirname(__file__))

failures = []

def parse_output(output):
    lines = output.splitlines()
    i = 0;
    while i < len(lines):
        if lines[i].startswith('FAIL:'):
            failures.append(lines[i])
            i += 1
            if i == len(lines):
                break
            if lines[i].startswith('-'):
                failures.append(lines[i])
                while True:
                    i += 1
                    if lines[i].startswith('-'):
                        break
                    else:
                        failures.append(lines[i])
        else:
            i += 1


def run_unittests(dummy, dirname, files):
    for f in files:
        if f.endswith('_unittest.py'):
            testfile = os.path.abspath(os.path.join(dirname, f))
            print "running test %s" % testfile
            test = "%s -v" % testfile
            output = utils.system_output(test, ignore_status=True)
            parse_output(output)


if __name__ == "__main__":
    if len(sys.argv) == 2:
        start = os.path.join(root, sys.argv[1])
    else:
        start = root

    os.path.walk(start, run_unittests, None)

    print "\n\n"
    if len(failures):
        print "Failures---------------------------------------------"
        for line in failures:
            print line
    else:
        print "All tests passed!"
