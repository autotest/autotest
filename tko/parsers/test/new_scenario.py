#!/usr/bin/python
"""Create new scenario test instance from an existing results directory.

This automates creation of regression tests for the results parsers.
There are 2 primary use cases for this.

1) Bug fixing: Parser broke on some input in the field and we want
to start with a test that operates on that input and fails. We
then apply fixes to the parser implementation until it passes.

2) Regression alarms: We take input from various real scenarios that
work as expected with the parser. These will be used to ensure
we do not break the expected functionality of the parser while
refactoring it.

While much is done automatically, a scenario harness is meant to
be easily extended and configured once generated.
"""

import optparse, os, shutil, sys
from os import path

import common
from autotest_lib.tko.parsers.test import scenario_base
from autotest_lib.client.common_lib import autotemp

usage = 'usage: %prog [options] results_dirpath scenerios_dirpath'
parser = optparse.OptionParser(usage=usage)
parser.add_option(
    '-n', '--name',
    help='Name for new scenario instance. Will use dirname if not specified')
parser.add_option(
    '-p', '--parser_result_tag',
    default='v1',
    help='Storage tag to use for initial parser result.')
parser.add_option(
    '-t', '--template_type',
    default='base',
    help='Type of unittest module to copy into new scenario.')


def main():
    (options, args) = parser.parse_args()
    if len(args) < 2:
        parser.print_help()
        sys.exit(1)

    results_dirpath = path.normpath(args[0])
    if not path.exists(results_dirpath) or not path.isdir(results_dirpath):
        print 'Invalid results_dirpath:', results_dirpath
        parser.print_help()
        sys.exit(1)

    scenarios_dirpath = path.normpath(args[1])
    if not path.exists(scenarios_dirpath) or not path.isdir(scenarios_dirpath):
        print 'Invalid scenarios_dirpath:', scenarios_dirpath
        parser.print_help()
        sys.exit(1)

    results_dirname = path.basename(results_dirpath)
    # Not everything is a valid python package name, fix if necessary
    package_dirname = scenario_base.fix_package_dirname(
        options.name or results_dirname)

    scenario_package_dirpath = path.join(
        scenarios_dirpath, package_dirname)
    if path.exists(scenario_package_dirpath):
        print (
            'Scenario package already exists at path: %s' %
            scenario_package_dirpath)
        parser.print_help()
        sys.exit(1)

    # Create new scenario package
    os.mkdir(scenario_package_dirpath)

    # Create tmp_dir
    tmp_dirpath = autotemp.tempdir(unique_id='new_scenario')
    copied_dirpath = path.join(tmp_dirpath.name, results_dirname)
    # Copy results_dir
    shutil.copytree(results_dirpath, copied_dirpath)

    # scenario_base.sanitize_results_data(copied_dirpath)

    # Launch parser on copied_dirpath, collect emitted test objects.
    harness = scenario_base.new_parser_harness(copied_dirpath)
    try:
        parser_result = harness.execute()
    except Exception, e:
        parser_result = e

    scenario_base.store_parser_result(
        scenario_package_dirpath, parser_result,
        options.parser_result_tag)

    scenario_base.store_results_dir(
        scenario_package_dirpath, copied_dirpath)

    scenario_base.write_config(
        scenario_package_dirpath,
        status_version=harness.status_version,
        parser_result_tag=options.parser_result_tag,
        )

    scenario_base.install_unittest_module(
        scenario_package_dirpath, options.template_type)
    tmp_dirpath.clean()


if __name__ == '__main__':
    main()
