#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Jorge Niedbalski R. <jnr@pyrosome.org>'

from nose.selector import Selector

from nose.plugins import Plugin
from nose.plugins.attrib import AttributeSelector
from nose.plugins.xunit import Xunit
from nose.plugins.cover import Coverage

import logging
import os
import nose
import sys

# we can replace this with a @attr(duration='long') on each test
try:
    import autotest.common as common
except ImportError:
    import common

from autotest.utils.unittest_suite import LONG_TESTS


logger = logging.getLogger(__name__)

class AutoTestSelector(Selector):

    def wantDirectory(self, dirname):
        return True

    def wantModule(self, module):
        return True

    def wantFile(self, filename):
        if not filename.endswith('_unittest.py'):
            return False

        if not self.config.options.full and os.path.basename(filename) in LONG_TESTS:
            logger.debug('Skipping test: %s' % filename)
            return False

        skip_tests = []
        if self.config.options.skip_tests:
            skip_tests = self.config.options.skip_tests.split()

        if filename[:-3] in skip_tests:
            logger.debug('Skipping test: %s' % filename)
            return False

        if self.config.options.debug:
            logger.debug('Adding %s as a valid test' % filename)

        return True


class AutoTestRunner(Plugin):

    enabled = True
    name = 'autotest_runner'

    def configure(self, options, config):
        self.result_stream = sys.stdout

        config.logStream = self.result_stream
        self.testrunner = nose.core.TextTestRunner(stream=self.result_stream,
                                                   descriptions=True,
                                                   verbosity=2,
                                                   config=config)

    def options(self, parser, env):
        parser.add_option("--autotest-full",
                          dest='full',
                          action='store_true',
                          default=False,
                          help='whether to run the shortened version of the test')

        parser.add_option("--autotest-debug",
                          dest="debug",
                          default=False,
                          help='Run in debug mode')

        parser.add_option("--autotest-skip-tests",
                          dest="skip_tests",
                          default=[],
                          help='A space separated list of tests to skip')

    def prepareTestLoader(self, loader):
        loader.selector = AutoTestSelector(loader.config)


def run_test():
    nose.main(addplugins=[AutoTestRunner(),
                          AttributeSelector(),
                          Xunit(),
                          Coverage()])


def main():
    run_test()

if __name__ == '__main__':
    main()
