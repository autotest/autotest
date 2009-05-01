#!/usr/bin/python
# (C) Copyright IBM Corp. 2006
# Author: Dustin Kirkland <dustin.kirkland@us.ibm.com>
# Description:
#  Input:  Two or more files containing results from different executions of
#          the LTP. The input can either be file names or the url location
#          of the ltp.results file.
#  Output: A report on the following:
#          - The total number of tests executed in each run
#          - The testname, sequence number, and output of each run
#            where the results of those runs differ
#  Return:
#          0 if all runs had identical results
#          Non-zero if results differ, or bad input


import sys, string, re
from autotest_lib.client.common_lib import utils

def usage():
    print "\nUsage: \n\
ltp-diff results1 results2 ... locationN \n\
Note: location[1,2,N] may be local files or URLs of LTP results\n"
    sys.exit(1)

def get_results(results_files):
    """
    Download the results if needed.
    Return results of each run in a numerically-indexed dictionary
    of dictionaries keyed on testnames.
    Return dictionary keyed on unique testnames across all runs.
    """
    r = re.compile('(\S+\s+\S+)\s+(\S+)\s+:')
    i = 0
    runs = {}
    testnames = {}
    for file in results_files:
        runs[i] = {}
        try:
            fh = utils.urlopen(file)
            results = fh.readlines()
            fh.close()
        except:
            print "ERROR: reading results resource [%s]" % (file)
            usage()
        for line in results:
            try:
                s = r.match(line)
                testname = s.group(1)
                status = s.group(2)
                runs[i][testname] = status
                testnames[testname] = 1
            except:
                pass
        i += 1
    return (runs, testnames)



def compare_results(runs):
    """
    Loop through all testnames alpahbetically.
    Print any testnames with differing results across runs.
    Return 1 if any test results across runs differ.
    Return 0 if all test results match.
    """
    rc = 0
    print "LTP Test Results to Compare"
    for i in range(len(runs)):
        print "  Run[%d]: %d" % (i, len(runs[i].keys()))
    print ""
    header = 0
    all_testnames = testnames.keys()
    all_testnames.sort()
    for testname in all_testnames:
        differ = 0
        for i in range(1,len(runs)):
            # Must handle testcases that executed in one run
            # but not another by setting status to "null"
            if not runs[i].has_key(testname):
                runs[i][testname] = "null"
            if not runs[i-1].has_key(testname):
                runs[i-1][testname] = "null"
            # Check for the results inconsistencies
            if runs[i][testname] != runs[i-1][testname]:
                differ = 1
        if differ:
            if header == 0:
                # Print the differences header only once
                print "Tests with Inconsistent Results across Runs"
                print "  %-35s:\t%s" % ("Testname,Sequence", "Run Results")
                header = 1

            # Print info if results differ
            rc = 1
            testname_cleaned = re.sub('\s+', ',', testname)
            print "  %-35s:\t" % (testname_cleaned),
            all_results = ""
            for i in range(len(runs)):
                all_results += runs[i][testname]
                if i+1<len(runs):
                    all_results += "/"
            print all_results
    if rc == 0:
        print "All LTP results are identical"
    return rc


########
# Main #
########
sys.argv.pop(0)
if (len(sys.argv) < 2):
    usage()
(runs, testnames) = get_results(sys.argv)
rc = compare_results(runs)
sys.exit(rc)
