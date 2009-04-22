#!/usr/bin/python
#
# Copyright 2008 Google Inc. All Rights Reserved.

"""Test for atest."""

import unittest, os, sys, StringIO

import common
from autotest_lib.cli import cli_mock


class main_unittest(cli_mock.cli_unittest):
    def _test_help(self, argv, out_words_ok, err_words_ok):
        saved_outputs = None
        for help in ['-h', '--help', 'help']:
            outputs = self.run_cmd(argv + [help], exit_code=0,
                                   out_words_ok=out_words_ok,
                                   err_words_ok=err_words_ok)
            if not saved_outputs:
                saved_outputs = outputs
            else:
                self.assertEqual(outputs, saved_outputs)


    def test_main_help(self):
        """Main help level"""
        self._test_help(argv=['atest'],
                        out_words_ok=['atest [acl|host|job|label|atomicgroup'
                                      '|test|user] [action] [options]'],
                        err_words_ok=[])


    def test_main_help_topic(self):
        """Topic level help"""
        self._test_help(argv=['atest', 'host'],
                        out_words_ok=['atest host ',
                                      '[create|delete|list|stat|mod|jobs]'
                                      ' [options]'],
                        err_words_ok=[])


    def test_main_help_action(self):
        """Action level help"""
        self._test_help(argv=['atest:', 'host', 'mod'],
                        out_words_ok=['atest host mod [options]'],
                        err_words_ok=[])


    def test_main_no_topic(self):
        self.run_cmd(['atest'], exit_code=1,
                     out_words_ok=['atest '
                                   '[acl|host|job|label|atomicgroup|test|user] '
                                   '[action] [options]'],
                     err_words_ok=['No topic argument'])


    def test_main_bad_topic(self):
        self.run_cmd(['atest', 'bad_topic'], exit_code=1,
                     out_words_ok=['atest [acl|host|job|label|atomicgroup'
                                   '|test|user] [action] [options]'],
                     err_words_ok=['Invalid topic bad_topic\n'])


    def test_main_bad_action(self):
        self.run_cmd(['atest', 'host', 'bad_action'], exit_code=1,
                     out_words_ok=['atest host [create|delete|list|stat|'
                                   'mod|jobs] [options]'],
                     err_words_ok=['Invalid action bad_action'])


if __name__ == '__main__':
    unittest.main()
