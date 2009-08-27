#!/usr/bin/python -i
"""Inspector for parser_result.store from specified scenerio package.

Load in parser_result.store as 'sto' and launch interactive interp.
Define some helper functions as required.
"""

import optparse, os, sys
from os import path
import common
from autotest_lib.tko.parsers.test import scenario_base


usage = 'usage: %prog [options] scenario_dirpath'
parser = optparse.OptionParser(usage=usage)
parser.add_option("-w", action="store_true", dest="open_for_write")

(options, args) = parser.parse_args()
if len(args) < 1:
    parser.print_help()
    sys.exit(1)

scenario_dirpath = path.normpath(args[0])
if not path.exists(scenario_dirpath) or not path.isdir(scenario_dirpath):
    print 'Invalid scenarios_dirpath:', scenario_dirpath
    parser.print_help()
    sys.exit(1)

sto = scenario_base.load_parser_result_store(
    scenario_dirpath, options.open_for_write)


def compare(left_tag, right_tag):
    missing = set([left_tag, right_tag]).difference(sto.keys())
    if missing:
        print 'Store does not have the following tag(s): ', ','.join(missing)
        print 'Doing nothing.'
        return

    for diffline in scenario_base.compare_parser_results(
        sto[left_tag], sto[right_tag]):
        print diffline
