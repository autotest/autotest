#!/usr/bin/python
#
# Copyright 2008 Google Inc. All Rights Reserved.

"""Tests for label."""

import unittest, sys, os

import common
from autotest_lib.cli import cli_mock, topic_common


class label_list_unittest(cli_mock.cli_unittest):
    values = [{u'id': 180,          # Valid label
               u'platform': False,
               u'name': u'label0',
               u'invalid': False,
               u'kernel_config': u'',
               u'only_if_needed': False},
              {u'id': 338,          # Valid label
               u'platform': False,
               u'name': u'label1',
               u'invalid': False,
               u'kernel_config': u'',
               u'only_if_needed': False},
              {u'id': 340,          # Invalid label
               u'platform': False,
               u'name': u'label2',
               u'invalid': True,
               u'kernel_config': u'',
               u'only_if_needed': False},
              {u'id': 350,          # Valid platform
               u'platform': True,
               u'name': u'plat0',
               u'invalid': False,
               u'kernel_config': u'',
               u'only_if_needed': False},
              {u'id': 420,          # Invalid platform
               u'platform': True,
               u'name': u'plat1',
               u'invalid': True,
               u'kernel_config': u'',
               u'only_if_needed': False}]


    def test_label_list_labels_only(self):
        self.run_cmd(argv=['atest', 'label', 'list', '--ignore_site_file'],
                     rpcs=[('get_labels', {}, True, self.values)],
                     out_words_ok=['label0', 'label1', 'label2'],
                     out_words_no=['plat0', 'plat1'])


    def test_label_list_labels_only_valid(self):
        self.run_cmd(argv=['atest', 'label', 'list', '-d',
                           '--ignore_site_file'],
                     rpcs=[('get_labels', {}, True, self.values)],
                     out_words_ok=['label0', 'label1'],
                     out_words_no=['label2', 'plat0', 'plat1'])


    def test_label_list_labels_and_platforms(self):
        self.run_cmd(argv=['atest', 'label', 'list', '--all',
                           '--ignore_site_file'],
                     rpcs=[('get_labels', {}, True, self.values)],
                     out_words_ok=['label0', 'label1', 'label2',
                                   'plat0', 'plat1'])


    def test_label_list_platforms_only(self):
        self.run_cmd(argv=['atest', 'label', 'list', '-t',
                           '--ignore_site_file'],
                     rpcs=[('get_labels', {}, True, self.values)],
                     out_words_ok=['plat0', 'plat1'],
                     out_words_no=['label0', 'label1', 'label2'])


    def test_label_list_platforms_only_valid(self):
        self.run_cmd(argv=['atest', 'label', 'list',
                           '-t', '--valid-only', '--ignore_site_file'],
                     rpcs=[('get_labels', {}, True, self.values)],
                     out_words_ok=['plat0'],
                     out_words_no=['label0', 'label1', 'label2',
                                   'plat1'])


class label_create_unittest(cli_mock.cli_unittest):
    def test_execute_create_two_labels(self):
        self.run_cmd(argv=['atest', 'label', 'create', 'label0', 'label1',
                           '--ignore_site_file'],
                     rpcs=[('add_label',
                            {'name': 'label0', 'platform': False,
                             'only_if_needed': False},
                            True, 42),
                           ('add_label',
                            {'name': 'label1', 'platform': False,
                             'only_if_needed': False},
                            True, 43)],
                     out_words_ok=['Created', 'label0', 'label1'])


    def test_execute_create_two_labels_bad(self):
        self.run_cmd(argv=['atest', 'label', 'create', 'label0', 'label1',
                           '--ignore_site_file'],
                     rpcs=[('add_label',
                            {'name': 'label0', 'platform': False,
                             'only_if_needed': False},
                            True, 3),
                           ('add_label',
                            {'name': 'label1', 'platform': False,
                             'only_if_needed': False},
                            False,
                            '''ValidationError: {'name':
                            'This value must be unique (label0)'}''')],
                     out_words_ok=['Created', 'label0'],
                     out_words_no=['label1'],
                     err_words_ok=['label1', 'ValidationError'])



class label_delete_unittest(cli_mock.cli_unittest):
    def test_execute_delete_labels(self):
        self.run_cmd(argv=['atest', 'label', 'delete', 'label0', 'label1',
                           '--ignore_site_file'],
                     rpcs=[('delete_label', {'id': 'label0'}, True, None),
                           ('delete_label', {'id': 'label1'}, True, None)],
                     out_words_ok=['Deleted', 'label0', 'label1'])


class label_add_unittest(cli_mock.cli_unittest):
    def test_execute_add_labels_to_hosts(self):
        self.run_cmd(argv=['atest', 'label', 'add', 'label0',
                           '--machine', 'host0,host1', '--ignore_site_file'],
                     rpcs=[('label_add_hosts', {'id': 'label0',
                                                'hosts': ['host1', 'host0']},
                            True, None)],
                     out_words_ok=['Added', 'label0', 'host0', 'host1'])


class label_remove_unittest(cli_mock.cli_unittest):
    def test_execute_remove_labels_from_hosts(self):
        self.run_cmd(argv=['atest', 'label', 'remove', 'label0',
                           '--machine', 'host0,host1', '--ignore_site_file'],
                     rpcs=[('label_remove_hosts', {'id': 'label0',
                                               'hosts': ['host1', 'host0']},
                            True, None)],
                     out_words_ok=['Removed', 'label0', 'host0', 'host1'])


if __name__ == '__main__':
    unittest.main()
