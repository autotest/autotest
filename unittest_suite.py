#!/usr/bin/python

import os, sys, unittest
import common
from autotest_lib.client.common_lib import utils

root = os.path.abspath(os.path.dirname(__file__))

passes = []
failures = []
output_file = None


def search_after_line(lines, i):
    for j in range(i+1, len(lines)):
        if "ok" in lines[j]:
            return (False, j)
        elif "FAIL" in lines[j]:
            return ("FAIL", j)
        elif "ERROR" in lines[j]:
            return ("ERROR", j)


def parse_output(output):
    lines = output.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].startswith("test_"):
            # we found a test line so check output
            if lines[i].endswith("... ok"):
                # success!
                passes.append(lines[i])
            elif lines[i].endswith("... ERROR") or lines[i].endswith("... FAIL"):
                failures.append(lines[i])
            else:
                # annoying stdout got in the way so we need to search
                (rt, j) = search_after_line(lines, i)
                if rt == False:
                    passes.append(lines[i] + " ... ok")
                else:
                    failures.append(lines[i] + " ... %s" % rt)
                i = j
        i += 1


def run_unittests(dummy, dirname, files):
    for f in files:
        if f.endswith('_unittest.py'):
            testfile = os.path.abspath(os.path.join(dirname, f))
            print "running test %s" % testfile
            test = "%s -v" % testfile
            result = utils.run(test, ignore_status=True)
            output.write("==================================================\n")
            output.write("Unittest file=%s\n" % testfile)
            output.write("==================================================\n")
            output.write(result.stderr)
            parse_output(result.stderr)


if __name__ == "__main__":
    if len(sys.argv) == 2:
        start = os.path.join(root, sys.argv[1])
    else:
        start = root

    # open a file for dumping the output
    output = open(os.path.join(root, 'unittest_suite_output.txt'), 'w')

    os.path.walk(start, run_unittests, None)

    print "\n\n"
    for line in passes:
        print line

    print "\n\n"
    if len(failures):
        numfail = len(failures)
        numpass = len(passes)
        print "%s out of %s tests failed" % (numfail, numfail+numpass)
        print "Failures---------------------------------------------"
        for line in failures:
            print line
    else:
        print "All tests passed!"
