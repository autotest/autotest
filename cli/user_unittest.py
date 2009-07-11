#!/usr/bin/python
#
# Copyright 2008 Google Inc. All Rights Reserved.

"""Test for user."""

import unittest, os, sys

import common
from autotest_lib.cli import cli_mock, user


class user_list_unittest(cli_mock.cli_unittest):
    def test_parse_user_not_required(self):
        ul = user.user_list()
        sys.argv = ['atest']
        (options, leftover) = ul.parse()
        self.assertEqual([], ul.users)
        self.assertEqual([], leftover)


    def test_parse_with_users(self):
        ul = user.user_list()
        ufile = cli_mock.create_file('user0\nuser3\nuser4\n')
        sys.argv = ['atest', 'user1', '--ulist', ufile.name, 'user3']
        (options, leftover) = ul.parse()
        self.assertEqualNoOrder(['user0', 'user1','user3', 'user4'],
                                ul.users)
        self.assertEqual(leftover, [])
        ufile.clean()


    def test_parse_with_acl(self):
        ul = user.user_list()
        sys.argv = ['atest', '--acl', 'acl0']
        (options, leftover) = ul.parse()
        self.assertEqual('acl0', ul.acl)
        self.assertEqual(leftover, [])


    def test_parse_with_access_level(self):
        ul = user.user_list()
        sys.argv = ['atest', '--access_level', '3']
        (options, leftover) = ul.parse()
        self.assertEqual('3', ul.access_level)
        self.assertEqual(leftover, [])


    def test_parse_with_all(self):
        ul = user.user_list()
        ufile = cli_mock.create_file('user0\nuser3\nuser4\n')
        sys.argv = ['atest', 'user1', '--ulist', ufile.name, 'user3',
                    '-l', '4', '-a', 'acl0']
        (options, leftover) = ul.parse()
        self.assertEqualNoOrder(['user0', 'user1','user3', 'user4'],
                                ul.users)
        self.assertEqual('acl0', ul.acl)
        self.assertEqual('4', ul.access_level)
        self.assertEqual(leftover, [])
        ufile.clean()


    def test_execute_list_all(self):
        self.run_cmd(argv=['atest', 'user', 'list'],
                     rpcs=[('get_users', {},
                            True,
                            [{u'access_level': 0,
                              u'login': u'user0',
                              u'id': 41},
                             {u'access_level': 0,
                              u'login': u'user5',
                              u'id': 42},
                             {u'access_level': 2,
                              u'login': u'user0',
                              u'id': 3}])],
                     out_words_ok=['user0', 'user5'],
                     out_words_no=['1', '3', '41', '42'])


    def test_execute_list_all_with_user(self):
        self.run_cmd(argv=['atest', 'user', 'list', 'user0'],
                     rpcs=[('get_users', {'login__in': ['user0']},
                            True,
                            [{u'access_level': 2,
                              u'login': u'user0',
                              u'id': 3}])],
                     out_words_ok=['user0'],
                     out_words_no=['2', '3'])


    def test_execute_list_all_with_acl(self):
        self.run_cmd(argv=['atest', 'user', 'list', '--acl', 'acl0'],
                     rpcs=[('get_users', {'aclgroup__name__in': ['acl0']},
                            True,
                            [{u'access_level': 2,
                              u'login': u'user0',
                              u'id': 3}])],
                     out_words_ok=['user0'],
                     out_words_no=['2', '3'])


    def test_execute_list_all_with_access_level(self):
        self.run_cmd(argv=['atest', 'user', 'list', '--access_level', '2'],
                     rpcs=[('get_users', {'access_level__in': ['2']},
                            True,
                            [{u'access_level': 2,
                              u'login': u'user0',
                              u'id': 3}])],
                     out_words_ok=['user0'],
                     out_words_no=['2', '3'])


    def test_execute_list_all_verbose(self):
        self.run_cmd(argv=['atest', 'user', 'list', '--verbose'],
                     rpcs=[('get_users', {},
                            True,
                            [{u'access_level': 0,
                              u'login': u'user0',
                              u'id': 41},
                             {u'access_level': 0,
                              u'login': u'user5',
                              u'id': 42},
                             {u'access_level': 5,
                              u'login': u'user0',
                              u'id': 3}])],
                     out_words_ok=['user0', 'user5', '41', '42', '0', '5'])


    def test_execute_list_all_with_user_verbose(self):
        ufile = cli_mock.create_file('user0 user1\n')
        self.run_cmd(argv=['atest', 'user', 'list', '--ulist', ufile.name,
                           '-v'],
                     rpcs=[('get_users', {'login__in': ['user0', 'user1']},
                            True,
                            [{u'access_level': 2,
                              u'login': u'user0',
                              u'id': 3},
                             {u'access_level': 5,
                              u'login': u'user1',
                              u'id': 4}])],
                     out_words_ok=['user0', 'user1', '3', '4', '5'])
        ufile.clean()


    def test_execute_list_all_with_acl_verbose(self):
        self.run_cmd(argv=['atest', 'user', 'list', '--acl', 'acl0', '-v'],
                     rpcs=[('get_users', {'aclgroup__name__in': ['acl0']},
                            True,
                            [{u'access_level': 2,
                              u'login': u'user0',
                              u'id': 3}])],
                     out_words_ok=['user0', '3', '2'])


    def test_execute_list_all_with_access_level_verbose(self):
        self.run_cmd(argv=['atest', 'user', 'list',
                           '--access_level', '2', '-v'],
                     rpcs=[('get_users', {'access_level__in': ['2']},
                            True,
                            [{u'access_level': 2,
                              u'login': u'user0',
                              u'id': 3}])],
                     out_words_ok=['user0', '2', '3'])


if __name__ == '__main__':
    unittest.main()
