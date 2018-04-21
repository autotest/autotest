#
# Copyright 2008 Google Inc. All Rights Reserved.
#
"""Command line interface for autotest

This module contains the generic CLI processing

See topic_common.py for a High Level Design and Algorithm.

This file figures out the topic and action from the 2 first arguments
on the command line and imports the site_<topic> or <topic> module.

It then creates a <topic>_<action> object, and calls it parses),
execute() and output() methods.

There are three return values possible:
0: the operation requested succeeded
1: the operation requested failed
2: the operation requested worked partially

EXAMPLE:

(1) host list goodsys badsys
goodsys exists and its info is displayed
badsys does not exist and a "host not found" message is displayed.

this will exit with a value of 2.

(2) host list badsys
badsys does not exist and a "host not found" message is displayed.

this will exit with a value of 1.

(3) host list goodsys
goodsys exists and its info is displayed

this will exit 0

(4) host list pattern
this will exit 0 whether pattern displays anything or not
"""

__author__ = 'jmeurin@google.com (Jean-Marc Eurin)'

import os
import re
import sys
import traceback

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.cli import topic_common


def main():
    """
    The generic syntax is:
    atest <topic> <action> <options>
    atest-<topic> <action> <options>
    atest --help
    """
    cli = os.path.basename(sys.argv[0])
    syntax_obj = topic_common.atest()

    # Normalize the various --help, -h and help to -h
    sys.argv = [re.sub('--help|help', '-h', arg) for arg in sys.argv]

    match = re.search('^atest-(\w+)$', cli)
    if match:
        topic = match.group(1)
    else:
        if len(sys.argv) > 1:
            topic = sys.argv.pop(1)
        else:
            syntax_obj.invalid_syntax('No topic argument')

    if topic == '-h':
        sys.argv.insert(1, '-h')
        syntax_obj.parse()

    # The ignore flag should *only* be used by unittests.
    ignore_site = '--ignore_site_file' in sys.argv
    if ignore_site:
        sys.argv.remove('--ignore_site_file')

    # Import the topic specific file
    cli_dir = os.path.abspath(os.path.dirname(__file__))
    if (not ignore_site and
            os.path.exists(os.path.join(cli_dir, 'site_%s.py' % topic))):
        topic = 'site_%s' % topic
    elif not os.path.exists(os.path.join(cli_dir, '%s.py' % topic)):
        syntax_obj.invalid_syntax('Invalid topic %s' % topic)
    topic_module = common.setup_modules.import_module(topic,
                                                      'autotest.cli')

    # If we have a syntax error now, it should
    # refer to the topic class.
    topic_class = getattr(topic_module, topic)
    topic_obj = topic_class()

    if len(sys.argv) > 1:
        action = sys.argv.pop(1)

        if action == '-h':
            action = 'help'
            sys.argv.insert(1, '-h')
    else:
        topic_obj.invalid_syntax('No action argument')

    # Any backward compatibility changes?
    action = topic_obj.backward_compatibility(action, sys.argv)

    # Instantiate a topic object
    try:
        action_class = getattr(topic_module, topic + '_' + action)
    except AttributeError:
        topic_obj.invalid_syntax('Invalid action %s' % action)

    action_obj = action_class()

    action_obj.parse()
    results = 0
    try:
        try:
            results = action_obj.execute()
        except topic_common.CliError:
            pass
        except Exception as err:
            traceback.print_exc()
            action_obj.generic_error("Unexpected exception: %s" % err)
        else:
            try:
                action_obj.output(results)
            except Exception:
                traceback.print_exc()
    finally:
        # set rtn = 0 if there were no errors
        # set rtn = 1 if there were only errors
        # set rtn = 2 if there was both output and error
        rtn = action_obj.show_all_failures()
        if (results):
            if (rtn):
                #  we had errors and output
                rtn = 2
        return rtn
