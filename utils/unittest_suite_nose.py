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

REQUIRES_DJANGO = set((
    'monitor_db_unittest.py',
    'monitor_db_functional_unittest.py',
    'monitor_db_cleanup_unittest.py',
    'frontend_unittest.py',
    'csv_encoder_unittest.py',
    'rpc_interface_unittest.py',
    'models_unittest.py',
    'scheduler_models_unittest.py',
    'metahost_scheduler_unittest.py',
    'site_metahost_scheduler_unittest.py',
    'rpc_utils_unittest.py',
    'site_rpc_utils_unittest.py',
    'execution_engine_unittest.py',
    'service_proxy_lib_unittest.py',
    'reservations_unittest.py',
    'autotest_remote_unittest.py',
))

REQUIRES_MYSQLDB = set((
    'migrate_unittest.py',
    'db_utils_unittest.py',
))

REQUIRES_GWT = set((
    'client_compilation_unittest.py',
))

REQUIRES_SIMPLEJSON = set((
    'resources_unittest.py',
    'serviceHandler_unittest.py',
))

REQUIRES_AUTH = set((
    'trigger_unittest.py',
))

REQUIRES_PROTOBUFS = set((
    'job_serializer_unittest.py',
))

REQUIRES_XML_ETREE = set((
    'autotest_firewalld_add_service_unittest.py',
))

LONG_RUNTIME = set((
    'base_barrier_unittest.py',
    'logging_manager_unittest.py',
    'base_syncdata_unittest.py'
))

LONG_TESTS = (REQUIRES_DJANGO |
              REQUIRES_MYSQLDB |
              REQUIRES_GWT |
              REQUIRES_SIMPLEJSON |
              REQUIRES_AUTH |
              REQUIRES_PROTOBUFS |
              REQUIRES_XML_ETREE |
              LONG_RUNTIME)

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
