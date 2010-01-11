#
# Copyright 2008 Google Inc. All Rights Reserved.

"""
The test module contains the objects and methods used to
manage tests in Autotest.

The valid action is:
list:       lists test(s)

The common options are:
--tlist / -T: file containing a list of tests

See topic_common.py for a High Level Design and Algorithm.
"""


import os, sys

from autotest_lib.cli import topic_common, action_common


class test(topic_common.atest):
    """Test class
    atest test list <options>"""
    usage_action = 'list'
    topic = msg_topic = 'test'
    msg_items = '[tests]'

    def __init__(self):
        """Add to the parser the options common to all the test actions"""
        super(test, self).__init__()

        self.parser.add_option('-T', '--tlist',
                               help='File listing the tests',
                               type='string',
                               default=None,
                               metavar='TEST_FLIST')

        self.topic_parse_info = topic_common.item_parse_info(
            attribute_name='tests',
            filename_option='tlist',
            use_leftover=True)


    def get_items(self):
        return self.tests


class test_help(test):
    """Just here to get the atest logic working.
    Usage is set by its parent"""
    pass


class test_list(action_common.atest_list, test):
    """atest test list [--description] [--experimental|--all] [<tests>]"""
    def __init__(self):
        super(test_list, self).__init__()

        self.parser.add_option('-d', '--description',
                               help='Display the test descriptions',
                               action='store_true',
                               default=False)
        self.parser.add_option('--all',
                               help='Display all the tests',
                               action='store_true',
                               default=False)
        self.parser.add_option('-e', '--experimental',
                               help='Display the experimental tests only',
                               action='store_true',
                               default=False)


    def parse(self):
        (options, leftover) = super(test_list, self).parse()

        if self.tests and (options.experimental or options.all):
            self.invalid_syntax('Do not specify a test name with --all or '
                                '--experimental')

        self.description = options.description
        self.all = options.all
        self.experimental = options.experimental

        return (options, leftover)


    def execute(self):
        filters = {}
        check_results = {}
        if self.tests:
            filters['name__in'] = self.tests
            check_results['name__in'] = 'name'

        if not self.all:
            filters['experimental'] = self.experimental
            check_results['experimental'] = None

        return super(test_list, self).execute(op='get_tests',
                                              filters=filters,
                                              check_results=check_results)


    def output(self, results):
        keys = ['name', 'test_type', 'test_class']

        if self.all:
            keys.append('experimental')

        if self.verbose:
            keys.append('path')

        if self.description:
            keys.append('description')

        super(test_list, self).output(results, keys)
