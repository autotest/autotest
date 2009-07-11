#!/usr/bin/python
#
# Copyright 2008 Google Inc. All Rights Reserved.

"""Test for acl."""

import unittest, sys

import common
from autotest_lib.cli import topic_common, action_common, acl, cli_mock


class acl_list_unittest(cli_mock.cli_unittest):
    def test_parse_list_acl(self):
        acl_list = acl.acl_list()
        afile = cli_mock.create_file('acl0\nacl3\nacl4\n')
        sys.argv = ['atest', 'acl0', 'acl1,acl2',
                    '--alist', afile.name, 'acl5', 'acl6,acl7']
        acl_list.parse()
        self.assertEqualNoOrder(['acl%s' % x for x in range(8)],
                                acl_list.acls)
        afile.clean()


    def test_parse_list_user(self):
        acl_list = acl.acl_list()
        sys.argv = ['atest', '--user', 'user0']
        acl_list.parse()
        self.assertEqual('user0', acl_list.users)


    def test_parse_list_host(self):
        acl_list = acl.acl_list()
        sys.argv = ['atest', '--mach', 'host0']
        acl_list.parse()
        self.assertEqual('host0', acl_list.hosts)


    def _test_parse_bad_options(self):
        acl_list = acl.acl_list()
        self.god.mock_io()
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException, acl_list.parse)
        (out, err) = self.god.unmock_io()
        self.god.check_playback()
        self.assert_(err.find('usage'))


    def test_parse_list_acl_user(self):
        sys.argv = ['atest', 'acl0', '-u', 'user']
        self._test_parse_bad_options()


    def test_parse_list_acl_2users(self):
        sys.argv = ['atest', '-u', 'user0,user1']
        self._test_parse_bad_options()


    def test_parse_list_acl_host(self):
        sys.argv = ['atest', 'acl0', '--mach', 'mach']
        self._test_parse_bad_options()


    def test_parse_list_acl_2hosts(self):
        sys.argv = ['atest', '--mach', 'mach0,mach1']
        self._test_parse_bad_options()


    def test_parse_list_user_host(self):
        sys.argv = ['atest', '-u', 'user', '--mach', 'mach']
        self._test_parse_bad_options()


    def test_parse_list_all(self):
        sys.argv = ['atest', '-u', 'user', '--mach', 'mach', 'acl0']
        self._test_parse_bad_options()


    def test_execute_list_all_acls(self):
        self.run_cmd(argv=['atest', 'acl', 'list', '-v'],
                     rpcs=[('get_acl_groups', {}, True,
                           [{'id': 1L,
                             'name': 'Everyone',
                             'description': '',
                             'users': ['debug_user'],
                             'hosts': []}])],
                     out_words_ok=['debug_user'])


    def test_execute_list_acls_for_acl(self):
        self.run_cmd(argv=['atest', 'acl', 'list', 'acl0'],
                     rpcs=[('get_acl_groups', {'name__in': ['acl0']}, True,
                           [{'id': 1L,
                             'name': 'Everyone',
                             'description': '',
                             'users': ['user0'],
                             'hosts': []}])],
                     out_words_ok=['Everyone'])


    def test_execute_list_acls_for_user(self):
        self.run_cmd(argv=['atest', 'acl', 'list', '-v', '--user', 'user0'],
                     rpcs=[('get_acl_groups', {'users__login': 'user0'}, True,
                           [{'id': 1L,
                             'name': 'Everyone',
                             'description': '',
                             'users': ['user0'],
                             'hosts': []}])],
                     out_words_ok=['user0'])


    def test_execute_list_acls_for_host(self):
        self.run_cmd(argv=['atest', 'acl', 'list', '-m', 'host0'],
                     rpcs=[('get_acl_groups', {'hosts__hostname': 'host0'},
                            True,
                           [{'id': 1L,
                             'name': 'Everyone',
                             'description': '',
                             'users': ['user0'],
                             'hosts': ['host0']}])],
                     out_words_ok=['Everyone'],
                     out_words_no=['host0'])


    def test_execute_list_acls_for_host_verb(self):
        self.run_cmd(argv=['atest', 'acl', 'list', '-m', 'host0', '-v'],
                     rpcs=[('get_acl_groups', {'hosts__hostname': 'host0'},
                            True,
                           [{'id': 1L,
                             'name': 'Everyone',
                             'description': '',
                             'users': ['user0'],
                             'hosts': ['host0']}])],
                     out_words_ok=['Everyone', 'host0'])



class acl_create_unittest(cli_mock.cli_unittest):
    def test_acl_create_parse_ok(self):
        acls = acl.acl_create()
        sys.argv = ['atest', 'acl0',
                    '--desc', 'my_favorite_acl']
        acls.parse()
        self.assertEqual('my_favorite_acl', acls.data['description'])


    def test_acl_create_parse_no_desc(self):
        self.god.mock_io()
        acls = acl.acl_create()
        sys.argv = ['atest', 'acl0']
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException, acls.parse)
        self.god.check_playback()
        self.god.unmock_io()


    def test_acl_create_parse_2_acls(self):
        self.god.mock_io()
        acls = acl.acl_create()
        sys.argv = ['atest', 'acl0', 'acl1',
                    '-desc', 'my_favorite_acl']
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException, acls.parse)
        self.god.check_playback()
        self.god.unmock_io()


    def test_acl_create_parse_no_option(self):
        self.god.mock_io()
        acls = acl.acl_create()
        sys.argv = ['atest']
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException, acls.parse)
        self.god.check_playback()
        self.god.unmock_io()


    def test_acl_create_acl_ok(self):
        self.run_cmd(argv=['atest', 'acl', 'create', 'acl0',
                           '--desc', 'my_favorite_acl'],
                     rpcs=[('add_acl_group',
                           {'description': 'my_favorite_acl',
                            'name': 'acl0'},
                           True,
                            3L)],
                     out_words_ok=['acl0'])


    def test_acl_create_duplicate_acl(self):
        self.run_cmd(argv=['atest', 'acl', 'create', 'acl0',
                           '--desc', 'my_favorite_acl'],
                     rpcs=[('add_acl_group',
                           {'description': 'my_favorite_acl',
                            'name': 'acl0'},
                           False,
                           'ValidationError:'
                           '''{'name': 'This value must be '''
                           '''unique (acl0)'}''')],
                     err_words_ok=['acl0', 'ValidationError',
                                   'unique'])


class acl_delete_unittest(cli_mock.cli_unittest):
    def test_acl_delete_acl_ok(self):
        self.run_cmd(argv=['atest', 'acl', 'delete', 'acl0'],
                     rpcs=[('delete_acl_group', {'id': 'acl0'}, True, None)],
                     out_words_ok=['acl0'])


    def test_acl_delete_acl_does_not_exist(self):
        self.run_cmd(argv=['atest', 'acl', 'delete', 'acl0'],
                     rpcs=[('delete_acl_group', {'id': 'acl0'},
                            False,
                            'DoesNotExist: acl_group matching '
                            'query does not exist.')],
                     err_words_ok=['acl0', 'DoesNotExist'])


    def test_acl_delete_multiple_acl_ok(self):
        alist = cli_mock.create_file('acl2\nacl1')
        self.run_cmd(argv=['atest', 'acl', 'delete',
                           'acl0', 'acl1', '--alist', alist.name],
                     rpcs=[('delete_acl_group',
                           {'id': 'acl0'},
                           True,
                           None),
                          ('delete_acl_group',
                           {'id': 'acl1'},
                           True,
                           None),
                          ('delete_acl_group',
                           {'id': 'acl2'},
                           True,
                           None)],
                     out_words_ok=['acl0', 'acl1', 'acl2', 'Deleted'])
        alist.clean()


    def test_acl_delete_multiple_acl_bad(self):
        alist = cli_mock.create_file('acl2\nacl1')
        self.run_cmd(argv=['atest', 'acl', 'delete',
                           'acl0', 'acl1', '--alist', alist.name],
                     rpcs=[('delete_acl_group',
                           {'id': 'acl0'},
                           True,
                           None),
                          ('delete_acl_group',
                           {'id': 'acl1'},
                           False,
                           'DoesNotExist: acl_group '
                           'matching query does not exist.'),
                          ('delete_acl_group',
                           {'id': 'acl2'},
                           True,
                           None)],
                     out_words_ok=['acl0', 'acl2', 'Deleted'],
                     err_words_ok=['acl1', 'delete_acl_group',
                                   'DoesNotExist', 'acl_group',
                                   'matching'])
        alist.clean()


class acl_add_unittest(cli_mock.cli_unittest):
    def test_acl_add_parse_no_option(self):
        self.god.mock_io()
        acls = acl.acl_add()
        sys.argv = ['atest']
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException, acls.parse)
        self.god.unmock_io()
        self.god.check_playback()


    def test_acl_add_users_hosts(self):
        self.run_cmd(argv=['atest', 'acl', 'add', 'acl0',
                           '-u', 'user0,user1', '-m', 'host0'],
                     rpcs=[('acl_group_add_users',
                           {'id': 'acl0',
                            'users': ['user0', 'user1']},
                           True,
                           None),
                          ('acl_group_add_hosts',
                           {'id': 'acl0',
                            'hosts': ['host0']},
                           True,
                           None)],
                     out_words_ok=['acl0', 'user0',
                                   'user1', 'host0'])


    def test_acl_add_bad_users(self):
        self.run_cmd(argv=['atest', 'acl', 'add', 'acl0',
                           '-u', 'user0,user1'],
                     rpcs=[('acl_group_add_users',
                           {'id': 'acl0',
                            'users': ['user0', 'user1']},
                            False,
                            'DoesNotExist: The following Users do not exist: '
                            'user0, user1')],
                     err_words_ok=['user0', 'user1'])


    def test_acl_add_bad_users_hosts(self):
        self.run_cmd(argv=['atest', 'acl', 'add', 'acl0',
                           '-u', 'user0,user1', '-m', 'host0'],
                     rpcs=[('acl_group_add_users',
                           {'id': 'acl0',
                            'users': ['user0', 'user1']},
                            False,
                            'DoesNotExist: The following Users do not exist: '
                            'user0'),
                           ('acl_group_add_users',
                           {'id': 'acl0',
                            'users': ['user1']},
                            True,
                            None),
                           ('acl_group_add_hosts',
                            {'id': 'acl0',
                             'hosts': ['host0', 'host1']},
                            False,
                            'DoesNotExist: The following Hosts do not exist: '
                            'host1'),
                           ('acl_group_add_hosts',
                            {'id': 'acl0',
                             'hosts': ['host0']},
                            True,
                            None)],
                     out_words_ok=['acl0', 'user1', 'host0'],
                     out_words_no=['user0', 'host1'],
                     err_words_ok=['user0', 'host1'],
                     err_words_no=['user1', 'host0'])


class acl_remove_unittest(cli_mock.cli_unittest):
    def test_acl_remove_remove_users(self):
        self.run_cmd(argv=['atest', 'acl', 'remove',
                           'acl0', '-u', 'user0,user1'],
                     rpcs=[('acl_group_remove_users',
                           {'id': 'acl0',
                            'users': ['user0', 'user1']},
                           True,
                           None)],
                     out_words_ok=['acl0', 'user0', 'user1'],
                     out_words_no=['host'])


    def test_acl_remove_remove_hosts(self):
        self.run_cmd(argv=['atest', 'acl', 'remove',
                           'acl0', '--mach', 'host0,host1'],
                     rpcs=[('acl_group_remove_hosts',
                           {'id': 'acl0',
                            'hosts': ['host1', 'host0']},
                           True,
                           None)],
                     out_words_ok=['acl0', 'host0', 'host1'],
                     out_words_no=['user'])


    def test_acl_remove_remove_both(self):
        self.run_cmd(argv=['atest', 'acl', 'remove',
                           'acl0', '--user', 'user0,user1',
                           '-m', 'host0,host1'],
                     rpcs=[('acl_group_remove_users',
                           {'id': 'acl0',
                            'users': ['user0', 'user1']},
                           True,
                           None),
                          ('acl_group_remove_hosts',
                           {'id': 'acl0',
                            'hosts': ['host1', 'host0']},
                           True,
                           None)],
                     out_words_ok=['acl0', 'user0', 'user1',
                                   'host0', 'host1'])


if __name__ == '__main__':
    unittest.main()
