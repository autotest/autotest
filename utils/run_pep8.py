#!/usr/bin/python -u
'''
Usage: run_pep8.py [options] [list of files]

Options:
-h, --help  show this help message and exit
-f, --fix   Auto fix files in place
'''

import os

import common
from autotest.client.shared import utils, logging_manager, logging_config
from autotest.client import os_dep


class Pep8LoggingConfig(logging_config.LoggingConfig):

    """
    Used with the sole purpose of providing convenient logging setup
    for the KVM test auxiliary programs.
    """

    def configure_logging(self, results_dir=None, verbose=False):
        super(Pep8LoggingConfig, self).configure_logging(use_console=True,
                                                         verbose=verbose)


class SetupError(Exception):
    pass

# do a basic check to see if python-pep8 is installed
try:
    # pep8 just analyzes code, it can't fix it
    PEP8_EXEC = os_dep.command("pep8")
    # autopep8 can automatically fix a number of non compliances
    AUTOPEP8_EXEC = os_dep.command("autopep8")
except ValueError:
    PEP8_EXEC = None
    AUTOPEP8_EXEC = None

DEPS_SATISFIED = (PEP8_EXEC is not None) and (AUTOPEP8_EXEC is not None)
E_MSG = ("The utilities 'pep8' and 'autopep8' are not available. You have "
         "to install them using the tools provided by your distro")

# Classes of errors we ignore on quiet runs
# TODO: I am not sure which ERROR we need to ignore.
IGNORED_ERRORS = 'E501,W601'


def _check(path):
    cmd = PEP8_EXEC
    if IGNORED_ERRORS:
        cmd += " --ignore %s" % IGNORED_ERRORS
    cmd += " %s" % path
    return utils.system(cmd, ignore_status=True) == 0


def check(path):
    if DEPS_SATISFIED:
        _check(path)
    else:
        raise SetupError(E_MSG)


def _fix(path):
    cmd = AUTOPEP8_EXEC
    if IGNORED_ERRORS:
        cmd += " --ignore %s" % IGNORED_ERRORS
    if os.path.isdir(path):
        cmd += " --recursive --in-place"
    else:
        cmd += " --in-place"
    cmd += " %s" % path
    return utils.system(cmd, ignore_status=True) == 0


def fix(path):
    if DEPS_SATISFIED:
        _fix(path)
    else:
        raise SetupError(E_MSG)


if __name__ == "__main__":
    logging_manager.configure_logging(Pep8LoggingConfig(),
                                      verbose=True)
    import optparse
    usage = "usage: %prog [options] [list of files]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-f", "--fix",
                      action="store_true", dest="fix",
                      help="Auto fix files in place")
    options, args = parser.parse_args()

    if options.fix:
        func = fix
    else:
        func = check

    if len(args) > 0:
        for path_to_check in args:
            func(path_to_check)
    else:
        func(".")
