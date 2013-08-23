#!/usr/bin/python
#
# Authors:
#  Steve Conklin <sconklin@canonical.com>
#  Brad Figg <brad.figg@canonical.com>
# Copyright (C) 2012 Canonical Ltd.
#
# Based on scan_results.py, which is @copyright: Red Hat 2008-2009
#
# This script is distributed under the terms and conditions of the GNU General
# Public License, Version 2 or later. See http://www.gnu.org/copyleft/gpl.html
# for details.
#

"""
Program that parses the autotest results and generates JUnit test results in XML format.
"""
from sys                             import argv, stdout, stderr, exit
import os
from datetime                        import date
#from traceback                       import format_exc
#from string                          import maketrans
#import uuid

import JUnit_api as api

import json

def dbg(ostr):
    stderr.write('dbg: %s' % ostr)
    stderr.flush()
    return

def dump(obj):
    stderr.write(json.dumps(obj, sort_keys=True, indent=4))
    stderr.write('\n')

# text_clean
#
def text_clean(text):
   '''
   This always seems like such a hack, however, there are some characters that we can't
   deal with properly so this function just removes them from the text passed in.
   '''
   retval = text
   retval = retval.replace('\xe2\x80\x98', "'")
   retval = retval.replace('\xe2\x80\x99', "'")
   retval = retval.replace('\xe2', "")
   return retval

# file_load
#
def file_load(file_name):
    """
    Load the indicated file into a string and return the string.
    """

    retval = None
    if os.path.exists(file_name):
        with open(file_name, 'r') as f:
            retval = f.read()
    else:
        stderr.write("  ** Warning: The requested file (%s) does not exist.\n" % file_name)

    return retval

def parse_results(text):
    """
    Parse text containing Autotest results.

    @return: A list of result 4-tuples.
    """
    result_list = []
    start_time_list = []
    info_list = []

    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        parts = line.split("\t")

        # Found a START line -- get start time
        if (line.startswith("START") and len(parts) >= 5 and
            parts[3].startswith("timestamp")):
            start_time = float(parts[3].split("=")[1])
            start_time_list.append(start_time)
            info_list.append("")

        # Found an END line -- get end time, name and status
        elif (line.startswith("END") and len(parts) >= 5 and
              parts[3].startswith("timestamp")):
            end_time = float(parts[3].split("=")[1])
            start_time = start_time_list.pop()
            info = info_list.pop()
            test_name = parts[2]
            test_status = parts[0].split()[1]
            # Remove "kvm." prefix
            if test_name.startswith("kvm."):
                test_name = test_name[4:]
            result_list.append((test_name, test_status,
                                int(end_time - start_time), info))

        # Found a FAIL/ERROR/GOOD line -- get failure/success info
        elif (len(parts) >= 6 and parts[3].startswith("timestamp") and
              parts[4].startswith("localtime")):
            info_list[-1] = parts[5]

    return result_list


def main(basedir, resfiles):
    result_lists = []
    name_width = 40

    try:
        hn = open(os.path.join(basedir, "sysinfo/hostname")).read()
    except:
        hn = "localhost"


    testsuites = api.testsuites()
    ts = api.testsuite(name="Autotest tests")
    properties = api.propertiesType()
    ts.hostname = hn
    ts.timestamp = date.isoformat(date.today())

    # collect some existing report file contents as properties
    if False: # Not sure, the properties don't seem to do anything for us right now.
        to_collect = [
            "cmdline","cpuinfo","df","gcc_--version",
            "installed_packages","interrupts",
            "ld_--version","lspci_-vvn","meminfo",
            "modules","mount","partitions",
            "proc_mounts","slabinfo","uname",
            "uptime","version"
            ]

        for propitem in to_collect:
            try:
                rawcontents = open(os.path.join(basedir, "sysinfo", propitem)).read()
                # the xml processor can only handle ascii
                contents = ''.join([x for x in rawcontents if ord(x) < 128])
            except:
                contents = "Unable to open the file %s" % os.path.join(basedir, "sysinfo", propitem)
            tp = api.propertyType(propitem, contents)
            properties.add_property(tp)

    f = os.path.join(basedir, "status")
    raw_text = open(f).read()

    text = text_clean(raw_text)
    raw_text = None

    results = parse_results(text)
    name_width = max([name_width] + [len(r[0]) for r in results])

    testcases = []
    tests = 0
    failures = 0
    errors = 0
    time = 0
    if len(results):
        for r in results:

            # handle test case xml generation
            tname = r[0]
            # first, see if this is the overall test result
            if tname.strip() == '----':
                testsuite_result = r[1]
                testsuite_time = r[2]
                continue

            # otherwise, it's a test case
            tc = api.testcaseType()
            if '.' in tname:
                (suite, name) = tname.split('.', 1)
            else:
                suite = tname
                name = tname
            tc.name = name
            tc.classname = 'autotest.%s' % suite
            tc.time = int(r[2])
            tests = tests + 1
            if r[1] == 'GOOD':
            # success, we append the testcase without an error or fail
                pass
            # Count NA as fails, disable them if you don't want them
            elif r[1] == 'TEST_NA':
                failures = failures+1
                fid = os.path.join(basedir, tname, 'debug', '%s.DEBUG' % tname)
                contents = text_clean(file_load(fid))
                tcfailure = api.failureType(message='Test %s is Not Applicable: %s' % (tname, r[3]), type_ = 'Failure', valueOf_ = "\n<![CDATA[\n%s\n]]>\n" % contents)
                tc.failure = tcfailure
            elif r[1] == 'ERROR':
                failures = failures+1
                fid = os.path.join(basedir, tname, 'debug', '%s.DEBUG' % tname)
                contents = text_clean(file_load(fid))
                tcfailure = api.failureType(message='Test %s has failed' % tname, type_ = 'Failure', valueOf_ = "\n<![CDATA[\n%s\n]]>\n" % contents)
                tc.failure = tcfailure
            else:
                # we don't know what this is
                errors = errors+1
                tcerror = api.errorType(message='Unexpected value for result in test result for test %s' % tname, type_ = 'Logparse', valueOf_ = "result=%s" % r[1])
                tc.error = tcerror
            testcases.append(tc)
    else:
        # no results to be found
        tc = api.testcaseType()
        tc.name = 'Logfilter'
        tc.classname = 'logfilter'
        tc.time = 0
        tcerror = api.errorType(message='LOGFILTER: No test cases found while parsing log', type_ = 'Logparse', valueOf_ = 'nothing to show')
        tc.error = tcerror
        testcases.append(tc)

    #if testsuite_result == "GOOD":
    #    if failures or error:
    #        raise RuntimeError("LOGFILTER internal error - Overall test results parsed as good, but test errors found")
    for tc in testcases:
        ts.add_testcase(tc)
    ts.failures = failures
    ts.errors = errors
    ts.time = testsuite_time
    ts.tests = tests
    ts.set_properties(properties)
    # TODO find and include stdout and stderr
    testsuites.add_testsuite(ts)
    testsuites.export(stdout, 0)

if __name__ == "__main__":
    if len(argv) < 2 or (argv[1] in ('-h', '--help')):
        print("Usage: %s <autotest-output>" % (argv[0]))
        exit(0)

    basedir = argv[1]
    if not os.path.isdir(basedir):
        print("  ** Error: The specified path (%s) either does not exist or isn't a directory." % (basedir))

    main(basedir, argv[1:])

# vi:set ts=4 sw=4 expandtab:
