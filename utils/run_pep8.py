#!/usr/bin/python -u
'''
Usage: run_pep8.py [options] [list of files]

Options:
-h, --help    show this help message and exit
-q, --quiet   Ignore pep8 errors
-d, --dryrun  Analyze, but don't make any changes to files
'''

import os
import sys

import common
from autotest.client.shared import utils
from autotest.client import os_dep

# do a basic check to see if python-pep8 is installed
try:
    PEP8_EXEC = os_dep.command("pep8")
except ValueError:
    print "Unable to find command <pep8>, it may need to be installed"
    sys.exit(1)

# Classes of errors we ignore on quiet runs
# TODO: I am not sure which ERROR we need to ignore.
IGNORED_ERRORS = ''
PEP8_VERBOSE = True
PEP8_DRYRUN = False


def set_verbosity(verbose):
    global PEP8_VERBOSE
    PEP8_VERBOSE = verbose


def set_dryrun(dryrun):
    global PEP8_DRYRUN
    PEP8_DRYRUN = dryrun


def check(path):
    cmd = ""
    if PEP8_DRYRUN:
        cmd += PEP8_EXEC
    else:
        try:
            AUTOPEP8_EXEC = os_dep.command("autopep8")
            cmd += "%s -r -i " % AUTOPEP8_EXEC
        except ValueError:
            print ("Unable to find command <autopep8>, "
                   "please add option --dryrun.")
            sys.exit(1)

    if not PEP8_VERBOSE and IGNORED_ERRORS:
        cmd += " --ignore %s" % IGNORED_ERRORS
    cmd += " %s " % path
    return utils.run(cmd)


def check_file(path):
    if not path.endswith('.py'):
        print "%s is not a python file." % path
        return 1
    check(path)


def check_dir(path):
    if not os.path.isdir(path):
        print "%s is not a directory." % path
        return 1
    check(path)


if __name__ == "__main__":
    import optparse
    usage = "usage: %prog [options] [list of files]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-q", "--quiet",
                      action="store_true", dest="quiet",
                      help="Ignore pep8 errors %s" % IGNORED_ERRORS)
    parser.add_option("-d", "--dryrun",
                      action="store_true", dest="dryrun",
                      help="Analyze, but don't make any changes to files")
    options, args = parser.parse_args()
    verbose = not options.quiet
    set_verbosity(verbose)
    set_dryrun(options.dryrun)
    file_list = args
    if len(file_list) > 0:
        for path in file_list:
            if os.path.isdir(path):
                check_dir(path)
            else:
                check_file(path)
    else:
        check_dir('.')
