#!/usr/bin/python
#
# Copyright 2008 Google Inc. All Rights Reserved.

"""Tests for test."""

import unittest, sys, os

import common
from autotest_lib.cli import cli_mock, topic_common, test


class test_list_unittest(cli_mock.cli_unittest):
    values = [{u'description': u'unknown',
               u'test_type': u'Client',
               u'test_class': u'Canned Test Sets',
               u'path': u'client/tests/test0/control',
               u'synch_type': u'Asynchronous',
               u'id': 138,
               u'name': u'test0',
               u'experimental': False},
              {u'description': u'unknown',
               u'test_type': u'Server',
               u'test_class': u'Kernel',
               u'path': u'server/tests/test1/control',
               u'synch_type': u'Asynchronous',
               u'id': 139,
               u'name': u'test1',
               u'experimental': False},
              {u'description': u'unknown',
               u'test_type': u'Client',
               u'test_class': u'Canned Test Sets',
               u'path': u'client/tests/test2/control.readprofile',
               u'synch_type': u'Asynchronous',
               u'id': 140,
               u'name': u'test2',
               u'experimental': False},
              {u'description': u'unknown',
               u'test_type': u'Server',
               u'test_class': u'Canned Test Sets',
               u'path': u'server/tests/test3/control',
               u'synch_type': u'Asynchronous',
               u'id': 142,
               u'name': u'test3',
               u'experimental': False},
              {u'description': u'Random stuff to check that things are ok',
               u'test_type': u'Client',
               u'test_class': u'Hardware',
               u'path': u'client/tests/test4/control.export',
               u'synch_type': u'Asynchronous',
               u'id': 143,
               u'name': u'test4',
               u'experimental': True}]


    def test_test_list_tests_default(self):
        self.run_cmd(argv=['atest', 'test', 'list'],
                     rpcs=[('get_tests', {'experimental': False},
                            True, self.values)],
                     out_words_ok=['test0', 'test1', 'test2',
                                   'test3', 'test4'],
                     out_words_no=['Random', 'control.export'])


    def test_test_list_tests_all(self):
        self.run_cmd(argv=['atest', 'test', 'list', '--all'],
                     rpcs=[('get_tests', {},
                            True, self.values)],
                     out_words_ok=['test0', 'test1', 'test2',
                                   'test3', 'test4'],
                     out_words_no=['Random', 'control.export'])


    def test_test_list_tests_exp(self):
        self.run_cmd(argv=['atest', 'test', 'list', '--experimental'],
                     rpcs=[('get_tests', {'experimental': True},
                            True,
                            [{u'description': u'Random stuff',
                              u'test_type': u'Client',
                              u'test_class': u'Hardware',
                              u'path': u'client/tests/test4/control.export',
                              u'synch_type': u'Asynchronous',
                              u'id': 143,
                              u'name': u'test4',
                              u'experimental': True}])],
                     out_words_ok=['test4'],
                     out_words_no=['Random', 'control.export'])


    def test_test_list_tests_select_one(self):
        filtered = [val for val in self.values if val['name'] in ['test3']]
        self.run_cmd(argv=['atest', 'test', 'list', 'test3'],
                     rpcs=[('get_tests', {'name__in': ['test3'],
                                          'experimental': False},
                            True, filtered)],
                     out_words_ok=['test3'],
                     out_words_no=['test0', 'test1', 'test2', 'test4',
                                   'unknown'])


    def test_test_list_tests_select_two(self):
        filtered = [val for val in self.values
                    if val['name'] in ['test3', 'test1']]
        self.run_cmd(argv=['atest', 'test', 'list', 'test3,test1'],
                     rpcs=[('get_tests', {'name__in': ['test1', 'test3'],
                                          'experimental': False},
                            True, filtered)],
                     out_words_ok=['test3', 'test1', 'Server'],
                     out_words_no=['test0', 'test2', 'test4',
                                   'unknown', 'Client'])


    def test_test_list_tests_select_two_space(self):
        filtered = [val for val in self.values
                    if val['name'] in ['test3', 'test1']]
        self.run_cmd(argv=['atest', 'test', 'list', 'test3', 'test1'],
                     rpcs=[('get_tests', {'name__in': ['test1', 'test3'],
                                          'experimental': False},
                            True, filtered)],
                     out_words_ok=['test3', 'test1', 'Server'],
                     out_words_no=['test0', 'test2', 'test4',
                                   'unknown', 'Client'])


    def test_test_list_tests_all_verbose(self):
        self.run_cmd(argv=['atest', 'test', 'list', '-v'],
                     rpcs=[('get_tests', {'experimental': False},
                            True, self.values)],
                     out_words_ok=['test0', 'test1', 'test2',
                                   'test3', 'test4', 'client/tests',
                                   'server/tests'],
                     out_words_no=['Random'])


    def test_test_list_tests_all_desc(self):
        self.run_cmd(argv=['atest', 'test', 'list', '-d'],
                     rpcs=[('get_tests', {'experimental': False},
                            True, self.values)],
                     out_words_ok=['test0', 'test1', 'test2',
                                   'test3', 'test4', 'unknown', 'Random'],
                     out_words_no=['client/tests', 'server/tests'])


    def test_test_list_tests_all_desc_verbose(self):
        self.run_cmd(argv=['atest', 'test', 'list', '-d', '-v'],
                     rpcs=[('get_tests', {'experimental': False},
                            True, self.values)],
                     out_words_ok=['test0', 'test1', 'test2',
                                   'test3', 'test4', 'client/tests',
                                   'server/tests', 'unknown', 'Random' ])


if __name__ == '__main__':
    unittest.main()
