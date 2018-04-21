#!/usr/bin/python
"""
Program that parses autotest metrics results and prints them to stdout,
so that the jenkins measurement-plots plugin can parse them.

 Authors:
  Steve Conklin <sconklin@canonical.com>
  Brad Figg <brad.figg@canonical.com>
 Copyright (C) 2012 Canonical Ltd.

 This script is distributed under the terms and conditions of the GNU General
 Public License, Version 2 or later. See http://www.gnu.org/copyleft/gpl.html
 for details.
"""
import json
import os
from datetime import datetime
from getopt import getopt, GetoptError
from sys import argv, stderr


def main(path):

    # under here is a "results" directory
    # The file we care about are:
    # results/default/testname/results/keyval

    metrics = {}
    results = {}

    metricFileList = []
    try:
        jobname = os.environ["JOB_NAME"]
    except KeyError:
        raise KeyError("Env variable JOB_NAME is not set, are you running this inside a jenkins job?")
    try:
        testname = os.environ["TEST_NAME"]
    except KeyError:
        raise KeyError("Env variable TEST_NAME is not set, are you running this inside the kernel test scripts?")

    if path is None:
        path = "autotest/client"

    # grab the metadata
        file_name = "test-attributes.json"
    if os.path.exists(file_name):
        f_obj = open(file_name, 'r')
        meta = json.load(f_obj)
        f_obj.close()
    else:
        meta = {}
        print("ERROR: file <%s> not found, no metadata included in metrics" % file_name, file=stderr)

    # Save a processing timestamp
    meta['results_processed'] = datetime.utcnow().strftime("%A, %d. %B %Y %H:%M UTC")
    meta['metrics_testname'] = testname

    # Gather results
    resultsdir = os.path.join(path, "results/default")
    # Now iterate over each subdirectory in the resultsdir, looking for keyval file
    subtestresults = os.listdir(resultsdir)
    for subtest in subtestresults:
        keyvalpath = os.path.join(resultsdir, subtest, "results/keyval")
        if os.path.exists(keyvalpath):
            metricFileList.append(keyvalpath)

    for filenm in metricFileList:
        fd = open(filenm, "r")
        lines = fd.readlines()
        for line in lines:
            p = line.strip().split('=')
            if len(p) != 2:
                continue
            metrics[p[0]] = p[1]

    results['meta'] = meta
    results['metrics'] = metrics
    print(json.dumps(results, sort_keys=True, indent=4))

    return


def usage():
    print("                                                                                             ")
    print("    %s                                                                                       " % argv[0])
    print("        reads result files from an autotest benchmark, and outputs the information as        ")
    print("        json data.                                                                           ")
    print("                                                                                             ")
    print("    Usage:                                                                                   ")
    print("        %s                                                                                   " % argv[0])
    print("                                                                                             ")
    print("    Options:                                                                                 ")
    print("        --help           Prints this text.                                                   ")
    print("                                                                                             ")
    print("        --path=<results_path>            The path to the results files                       ")
    print("                                         (defaults to workspace/[jobname]/autotest/client).    ")
    print("                                                                                             ")


if __name__ == "__main__":
    # process command line
    optsShort = ''
    optsLong = ['help', 'path=']
    opts, args = getopt(argv[1:], optsShort, optsLong)
    path = None
    attrs = {}

    try:
        for opt, val in opts:
            if (opt == '--help'):
                usage()
            elif opt in ('--path'):
                path = val.strip()

    except GetoptError:
        usage()

    main(path)
