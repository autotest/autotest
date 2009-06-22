#!/usr/bin/python
"""
This is not meant to be executed unless copied into a
scenario package and renamed with a _unittest suffix.
"""

import os, unittest
from os import path
import common
from autotest_lib.tko.parsers.test import scenario_base

GOLDEN = 'golden'


class ParserScenerioTestCase(scenario_base.BaseScenarioTestCase):
    def test_regression(self):
        """We want to ensure that result matches the golden.

        This test is enabled if there is a golden entry
        in the parser_result_store.
        """
        self.skipIf(
            GOLDEN not in self.parser_result_store,
            'No golden data to test against')

        golden = self.parser_result_store[GOLDEN]
        fresh_parser_result = self.harness.execute()
        fresh_copy = scenario_base.copy_parser_result(
            fresh_parser_result)
        self.assertEquals(golden, fresh_copy)


if __name__ == '__main__':
    unittest.main()
