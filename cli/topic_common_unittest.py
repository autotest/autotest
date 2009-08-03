#!/usr/bin/python
#
# Copyright 2008 Google Inc. All Rights Reserved.

"""Test for atest."""

import unittest, os, sys, StringIO, urllib2

import common
from autotest_lib.cli import cli_mock, topic_common, rpc
from autotest_lib.frontend.afe.json_rpc import proxy


class topic_common_misc_tests(unittest.TestCase):
    def test_get_item_key(self):
        get_item_key = topic_common._get_item_key
        self.assertRaises(ValueError, get_item_key, {}, '')
        self.assertRaises(ValueError, get_item_key, {}, '.')
        self.assertRaises(KeyError, get_item_key, {}, 'a')
        self.assertRaises(KeyError, get_item_key, {}, 'a.')
        self.assertRaises(ValueError, get_item_key, {'a': {}}, 'a.')
        self.assertRaises(KeyError, get_item_key, {'a': {}}, 'a.b')
        self.assertEquals(2, get_item_key({'a.b': 2, 'a': {}}, 'a.b'))
        self.assertEquals(9, get_item_key({'a': {'b': 9}}, 'a.b'))
        self.assertEquals(3, get_item_key({'a': {'b': {'c': 3}}}, 'a.b.c'))
        self.assertEquals(5, get_item_key({'a': 5}, 'a'))
        self.assertEquals({'b': 9}, get_item_key({'a': {'b': 9}}, 'a'))


class item_parse_info_unittest(cli_mock.cli_unittest):
    def __test_parsing_flist_bad(self, options):
        parse_info = topic_common.item_parse_info
        test_parse_info = parse_info(attribute_name='testing',
                                     filename_option='flist')
        self.assertRaises(topic_common.CliError,
                          test_parse_info.get_values, options, [])


    def __test_parsing_flist_good(self, options, expected):
        parse_info = topic_common.item_parse_info
        test_parse_info = parse_info(attribute_name='testing',
                                     filename_option='flist')
        result, leftover = test_parse_info.get_values(options, [])

        self.assertEqualNoOrder(expected, result)
        os.unlink(options.flist)


    def __test_parsing_inline_good(self, options, expected):
        parse_info = topic_common.item_parse_info
        test_parse_info = parse_info(attribute_name='testing',
                                     inline_option='inline')
        result, leftover = test_parse_info.get_values(options, [])

        self.assertEqualNoOrder(expected, result)


    def __test_parsing_leftover_good(self, leftover, expected):
        class opt(object):
            pass
        parse_info = topic_common.item_parse_info
        test_parse_info = parse_info(attribute_name='testing',
                                     inline_option='inline',
                                     use_leftover=True)
        result, leftover = test_parse_info.get_values(opt(), leftover)

        self.assertEqualNoOrder(expected, result)


    def __test_parsing_all_good(self, options, leftover, expected):
        parse_info = topic_common.item_parse_info
        test_parse_info = parse_info(attribute_name='testing',
                                     inline_option='inline',
                                     filename_option='flist',
                                     use_leftover=True)
        result, leftover = test_parse_info.get_values(options, leftover)

        self.assertEqualNoOrder(expected, result)
        os.unlink(options.flist)


    def __test_parsing_all_bad(self, options, leftover):
        parse_info = topic_common.item_parse_info
        test_parse_info = parse_info(attribute_name='testing',
                                     inline_option='inline',
                                     filename_option='flist',
                                     use_leftover=True)
        self.assertRaises(topic_common.CliError,
                          test_parse_info.get_values, options, leftover)


    def test_file_list_wrong_file(self):
        class opt(object):
            flist = './does_not_exist'
        self.__test_parsing_flist_bad(opt())


    def test_file_list_empty_file(self):
        class opt(object):
            flist_obj = cli_mock.create_file('')
            flist = flist_obj.name
        self.__test_parsing_flist_bad(opt())


    def test_file_list_ok(self):
        class opt(object):
            flist_obj = cli_mock.create_file('a\nb\nc\n')
            flist = flist_obj.name
        self.__test_parsing_flist_good(opt(), ['a', 'b', 'c'])


    def test_file_list_one_line_space(self):
        class opt(object):
            flist_obj = cli_mock.create_file('a b c\nd e\nf\n')
            flist = flist_obj.name
        self.__test_parsing_flist_good(opt(), ['a', 'b', 'c', 'd', 'e', 'f'])


    def test_file_list_one_line_comma(self):
        class opt(object):
            flist_obj = cli_mock.create_file('a,b,c\nd,e\nf\n')
            flist = flist_obj.name
        self.__test_parsing_flist_good(opt(), ['a', 'b', 'c', 'd', 'e', 'f'])


    def test_file_list_one_line_mix(self):
        class opt(object):
            flist_obj = cli_mock.create_file('a,b c\nd,e\nf\ng h,i')
            flist = flist_obj.name
        self.__test_parsing_flist_good(opt(), ['a', 'b', 'c', 'd', 'e',
                                         'f', 'g', 'h', 'i'])


    def test_file_list_one_line_comma_space(self):
        class opt(object):
            flist_obj = cli_mock.create_file('a, b c\nd,e\nf\ng h,i')
            flist = flist_obj.name
        self.__test_parsing_flist_good(opt(), ['a', 'b', 'c', 'd', 'e',
                                         'f', 'g', 'h', 'i'])


    def test_file_list_line_end_comma_space(self):
        class opt(object):
            flist_obj = cli_mock.create_file('a, b c\nd,e, \nf,\ng h,i ,')
            flist = flist_obj.name
        self.__test_parsing_flist_good(opt(), ['a', 'b', 'c', 'd', 'e',
                                         'f', 'g', 'h', 'i'])


    def test_file_list_no_eof(self):
        class opt(object):
            flist_obj = cli_mock.create_file('a\nb\nc')
            flist = flist_obj.name
        self.__test_parsing_flist_good(opt(), ['a', 'b', 'c'])


    def test_file_list_blank_line(self):
        class opt(object):
            flist_obj = cli_mock.create_file('\na\nb\n\nc\n')
            flist = flist_obj.name
        self.__test_parsing_flist_good(opt(), ['a', 'b', 'c'])


    def test_file_list_opt_list_one(self):
        class opt(object):
            inline = 'a'
        self.__test_parsing_inline_good(opt(), ['a'])


    def test_file_list_opt_list_space(self):
        class opt(object):
            inline = 'a b c'
        self.__test_parsing_inline_good(opt(), ['a', 'b', 'c'])


    def test_file_list_opt_list_mix_space_comma(self):
        class opt(object):
            inline = 'a b,c,d e'
        self.__test_parsing_inline_good(opt(), ['a', 'b', 'c', 'd', 'e'])


    def test_file_list_opt_list_mix_comma_space(self):
        class opt(object):
            inline = 'a b,c, d e'
        self.__test_parsing_inline_good(opt(), ['a', 'b', 'c', 'd', 'e'])


    def test_file_list_opt_list_end_comma_space(self):
        class opt(object):
            inline = 'a b, ,c,, d e, '
        self.__test_parsing_inline_good(opt(), ['a', 'b', 'c', 'd', 'e'])


    def test_file_list_add_on_space(self):
        self.__test_parsing_leftover_good(['a','c','b'],
                                          ['a', 'b', 'c'])


    def test_file_list_add_on_mix_space_comma(self):
        self.__test_parsing_leftover_good(['a', 'c','b,d'],
                                          ['a', 'b', 'c', 'd'])


    def test_file_list_add_on_mix_comma_space(self):
        self.__test_parsing_leftover_good(['a', 'c', 'b,', 'd'],
                                          ['a', 'b', 'c', 'd'])


    def test_file_list_add_on_end_comma_space(self):
        self.__test_parsing_leftover_good(['a', 'c', 'b,', 'd,', ','],
                                          ['a', 'b', 'c', 'd'])


    def test_file_list_all_opt(self):
        class opt(object):
            flist_obj = cli_mock.create_file('f\ng\nh\n')
            flist = flist_obj.name
            inline = 'a b,c,d e'
        self.__test_parsing_all_good(opt(), ['i', 'j'],
                                     ['a', 'b', 'c', 'd', 'e',
                                      'f', 'g', 'h', 'i', 'j'])


    def test_file_list_all_opt_empty_file(self):
        class opt(object):
            flist_obj = cli_mock.create_file('')
            flist = flist_obj.name
            inline = 'a b,c,d e'
        self.__test_parsing_all_bad(opt(), ['i', 'j'])


    def test_file_list_all_opt_in_common(self):
        class opt(object):
            flist_obj = cli_mock.create_file('f\nc\na\n')
            flist = flist_obj.name
            inline = 'a b,c,d e'
        self.__test_parsing_all_good(opt(), ['i','j,d'],
                                     ['a', 'b', 'c', 'd', 'e', 'f', 'i', 'j'])


    def test_file_list_all_opt_in_common_space(self):
        class opt(object):
            flist_obj = cli_mock.create_file('a b c\nd,e\nf\ng')
            flist = flist_obj.name
            inline = 'a b,c,d h'
        self.__test_parsing_all_good(opt(), ['i','j,d'],
                                     ['a', 'b', 'c', 'd', 'e',
                                      'f', 'g', 'h', 'i', 'j'])


    def test_file_list_all_opt_in_common_weird(self):
        class opt(object):
            flist_obj = cli_mock.create_file('a b c\nd,e\nf\ng, \n, ,,')
            flist = flist_obj.name
            inline = 'a b,c,d h, ,  ,,  '
        self.__test_parsing_all_good(opt(), ['i','j,d'],
                                     ['a', 'b', 'c', 'd', 'e',
                                      'f', 'g', 'h', 'i', 'j'])


class atest_unittest(cli_mock.cli_unittest):
    def setUp(self):
        super(atest_unittest, self).setUp()
        self.atest = topic_common.atest()
        self.atest.afe = rpc.afe_comm()
        if 'AUTOTEST_WEB' in os.environ:
            del os.environ['AUTOTEST_WEB']


    def tearDown(self):
        self.atest = None
        super(atest_unittest, self).tearDown()


    def test_invalid_arg_kill(self):
        self.atest.kill_on_failure = True
        self.god.mock_io()
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException,
                          self.atest.invalid_arg, 'This is bad')
        (output, err) = self.god.unmock_io()
        self.god.check_playback()
        self.assert_(err.find('This is bad') >= 0)


    def test_invalid_arg_continue(self):
        self.god.mock_io()
        self.atest.invalid_arg('This is sort of ok')
        (output, err) = self.god.unmock_io()
        self.assert_(err.find('This is sort of ok') >= 0)


    def test_failure_continue(self):
        self.atest.failure('This is partly bad', item='item0',
                           what_failed='something important')
        err = self.atest.failed['something important']
        self.assert_('This is partly bad' in err.keys())


    def test_failure_continue_multiple_different_errors(self):
        self.atest.failure('This is partly bad', item='item0',
                           what_failed='something important')
        self.atest.failure('This is really bad', item='item0',
                           what_failed='something really important')
        err = self.atest.failed['something important']
        self.assert_('This is partly bad' in err)
        self.assert_('This is really bad' not in err)
        err = self.atest.failed['something really important']
        self.assert_('This is partly bad' not in err)
        self.assert_('This is really bad' in err)


    def test_failure_continue_multiple_same_errors(self):
        self.atest.failure('This is partly bad', item='item0',
                           what_failed='something important')
        self.atest.failure('This is really bad', item='item1',
                           what_failed='something important')
        errs = self.atest.failed['something important']
        self.assert_('This is partly bad' in errs)
        self.assert_('This is really bad' in errs)
        self.assert_(set(['item0']) in errs.values())
        self.assert_(set(['item1']) in errs.values())


    def test_failure_continue_multiple_errors_mixed(self):
        self.atest.failure('This is partly bad', item='item0',
                           what_failed='something important')
        self.atest.failure('This is really bad', item='item0',
                           what_failed='something really important')
        self.atest.failure('This is really bad', item='item1',
                           what_failed='something important')
        errs = self.atest.failed['something important']
        self.assert_('This is partly bad' in errs)
        self.assert_('This is really bad' in errs)
        self.assert_(set(['item0']) in errs.values())
        self.assert_(set(['item1']) in errs.values())

        errs = self.atest.failed['something really important']
        self.assert_('This is really bad' in errs)
        self.assert_('This is partly bad' not in errs)
        self.assert_(set(['item0']) in errs.values())
        self.assert_(set(['item1']) not in errs.values())


    def test_failure_continue_multiple_errors_mixed_same_error(self):
        self.atest.failure('This is partly bad', item='item0',
                           what_failed='something important')
        self.atest.failure('This is really bad', item='item0',
                           what_failed='something really important')
        self.atest.failure('This is partly bad', item='item1',
                           what_failed='something important')
        errs = self.atest.failed['something important']
        self.assert_('This is partly bad' in errs)
        self.assert_('This is really bad' not in errs)
        self.assert_(set(['item0', 'item1']) in errs.values())

        errs = self.atest.failed['something really important']
        self.assert_('This is really bad' in errs)
        self.assert_('This is partly bad' not in errs)
        self.assert_(set(['item0']) in errs.values())
        self.assert_(set(['item1']) not in errs.values())


    def test_failure_exit(self):
        self.atest.kill_on_failure = True
        self.god.mock_io()
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException,
                          self.atest.failure, 'This is partly bad')
        (output, err) = self.god.unmock_io()
        self.god.check_playback()
        self.assert_(err.find('This is partly bad') >= 0)


    def test_failure_exit_item(self):
        self.atest.kill_on_failure = True
        self.god.mock_io()
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException,
                          self.atest.failure, 'This is partly bad',
                          item='item0')
        (output, err) = self.god.unmock_io()
        self.god.check_playback()
        self.assertWords(err, ['This is partly bad'], ['item0'])


    def test_show_all_failures_common(self):
        self.atest.failure('This is partly bad', item='item0',
                           what_failed='something important')
        self.atest.failure('This is partly bad', item='item1',
                           what_failed='something important')
        self.god.mock_io()
        self.atest.show_all_failures()
        (output, err) = self.god.unmock_io()
        self.assertWords(err, ['something important',
                               'This is partly bad', 'item0', 'item1'])


    def test_parse_add_on(self):
        flist = cli_mock.create_file('host1\nhost2\nleft2')
        sys.argv = ['atest', '--web', 'fooweb', '--parse',
                    '--kill-on-failure', 'left1', 'left2', '-M', flist.name]
        self.atest.parser.add_option('-M', '--mlist', type='string')
        item_info = topic_common.item_parse_info(attribute_name='hosts',
                                                 filename_option='mlist',
                                                 use_leftover=True)
        (options, leftover) = self.atest.parse([item_info])
        self.assertEqualNoOrder(self.atest.hosts,
                                ['left1', 'left2', 'host1', 'host2'])

        self.assertEqual({'mlist': flist.name,
                          'web_server': 'fooweb',
                          'parse': True,
                          'parse_delim': '|',
                          'kill_on_failure': True,
                          'verbose': False,
                          'debug': False}, options)
        self.assertEqual(leftover, [])
        flist.clean()


    def test_parse_no_add_on(self):
        flist = cli_mock.create_file('host1\nhost2\nleft2')
        sys.argv = ['atest', '--web', 'fooweb', '--parse', '-g',
                    '--kill-on-failure', 'left1', 'left2', '-M', flist.name]
        self.atest.parser.add_option('-M', '--mlist', type='string')
        item_info = topic_common.item_parse_info(attribute_name='hosts',
                                                 filename_option='mlist')
        (options, leftover) = self.atest.parse([item_info])
        self.assertEqualNoOrder(self.atest.hosts,
                                ['left2', 'host1', 'host2'])

        self.assertEqual({'mlist': flist.name,
                          'web_server': 'fooweb',
                          'parse': True,
                          'parse_delim': '|',
                          'kill_on_failure': True,
                          'verbose': False,
                          'debug': True}, options)
        self.assertEqual(leftover, ['left1', 'left2'])
        flist.clean()


    def test_parse_add_on_first(self):
        flist = cli_mock.create_file('host1\nhost2\nleft2')
        ulist = cli_mock.create_file('user1\nuser2\nuser3\n')
        sys.argv = ['atest', '-g', '--parse', '--ulist', ulist.name,
                    '-u', 'myuser,youruser',
                    '--kill-on-failure', 'left1', 'left2', '-M', flist.name]
        self.atest.parser.add_option('-M', '--mlist', type='string')
        self.atest.parser.add_option('-U', '--ulist', type='string')
        self.atest.parser.add_option('-u', '--user', type='string')
        host_info = topic_common.item_parse_info(attribute_name='hosts',
                                                 filename_option='mlist',
                                                 use_leftover=True)
        user_info = topic_common.item_parse_info(attribute_name='users',
                                                 inline_option='user',
                                                 filename_option='ulist')

        (options, leftover) = self.atest.parse([host_info, user_info])
        self.assertEqualNoOrder(self.atest.hosts,
                                ['left1', 'left2', 'host1', 'host2'])
        self.assertEqualNoOrder(self.atest.users,
                                ['user1', 'user2', 'user3',
                                 'myuser', 'youruser'])

        self.assertEqual({'mlist': flist.name,
                          'ulist': ulist.name,
                          'user': 'myuser,youruser',
                          'web_server': None,
                          'parse': True,
                          'parse_delim': '|',
                          'kill_on_failure': True,
                          'verbose': False,
                          'debug': True}, options)
        self.assertEqual(leftover, [])
        flist.clean()
        ulist.clean()


    def test_parse_add_on_second(self):
        flist = cli_mock.create_file('host1\nhost2\nleft2')
        ulist = cli_mock.create_file('user1\nuser2\nuser3\n')
        sys.argv = ['atest', '-g', '--parse', '-U', ulist.name,
                    '-u', 'myuser,youruser',
                    '--kill-on-failure', 'left1', 'left2', '-M', flist.name]
        self.atest.parser.add_option('-M', '--mlist', type='string')
        self.atest.parser.add_option('-U', '--ulist', type='string')
        self.atest.parser.add_option('-u', '--user', type='string')
        host_info = topic_common.item_parse_info(attribute_name='hosts',
                                                 filename_option='mlist',
                                                 use_leftover=True)
        user_info = topic_common.item_parse_info(attribute_name='users',
                                                 inline_option='user',
                                                 filename_option='ulist')
        (options, leftover) = self.atest.parse([host_info, user_info])

        self.assertEqualNoOrder(self.atest.hosts,
                                ['left1', 'left2', 'host1', 'host2'])
        self.assertEqualNoOrder(self.atest.users,
                                ['user1', 'user2', 'user3',
                                 'myuser', 'youruser'])

        self.assertEqual({'mlist': flist.name,
                          'ulist': ulist.name,
                          'user': 'myuser,youruser',
                          'web_server': None,
                          'parse': True,
                          'parse_delim': '|',
                          'kill_on_failure': True,
                          'verbose': False,
                          'debug': True}, options)
        self.assertEqual(leftover, [])
        flist.clean()
        ulist.clean()


    def test_parse_all_opts(self):
        flist = cli_mock.create_file('host1\nhost2\nleft2')
        ulist = cli_mock.create_file('user1\nuser2\nuser3\n')
        sys.argv = ['atest', '-g', '--parse', '--ulist', ulist.name,
                    '-u', 'myuser,youruser',
                    '--kill-on-failure', '-M', flist.name, 'left1', 'left2']
        self.atest.parser.add_option('-M', '--mlist', type='string')
        self.atest.parser.add_option('-U', '--ulist', type='string')
        self.atest.parser.add_option('-u', '--user', type='string')
        host_info = topic_common.item_parse_info(attribute_name='hosts',
                                                 filename_option='mlist',
                                                 use_leftover=True)
        user_info = topic_common.item_parse_info(attribute_name='users',
                                                 inline_option='user',
                                                 filename_option='ulist')
        (options, leftover) = self.atest.parse([host_info, user_info])
        self.assertEqualNoOrder(self.atest.hosts,
                                ['left1', 'left2', 'host1', 'host2'])
        self.assertEqualNoOrder(self.atest.users,
                                ['user1', 'user2', 'user3',
                                 'myuser', 'youruser'])

        self.assertEqual({'mlist': flist.name,
                          'ulist': ulist.name,
                          'user': 'myuser,youruser',
                          'web_server': None,
                          'parse': True,
                          'parse_delim': '|',
                          'kill_on_failure': True,
                          'verbose': False,
                          'debug': True}, options)
        self.assertEqual(leftover, [])
        flist.clean()
        ulist.clean()


    def test_parse_no_add_on(self):
        flist = cli_mock.create_file('host1\nhost2\nleft2')
        ulist = cli_mock.create_file('user1\nuser2\nuser3\n')
        sys.argv = ['atest', '-U', ulist.name,
                    '--kill-on-failure', '-M', flist.name]
        self.atest.parser.add_option('-M', '--mlist', type='string')
        self.atest.parser.add_option('-U', '--ulist', type='string')
        self.atest.parser.add_option('-u', '--user', type='string')
        host_info = topic_common.item_parse_info(attribute_name='hosts',
                                                 filename_option='mlist',
                                                 use_leftover=True)
        user_info = topic_common.item_parse_info(attribute_name='users',
                                                 inline_option='user',
                                                 filename_option='ulist')
        (options, leftover) = self.atest.parse([host_info, user_info])
        self.assertEqualNoOrder(self.atest.hosts,
                                ['left2', 'host1', 'host2'])
        self.assertEqualNoOrder(self.atest.users,
                                ['user1', 'user2', 'user3'])

        self.assertEqual({'mlist': flist.name,
                          'ulist': ulist.name,
                          'user': None,
                          'web_server': None,
                          'parse': False,
                          'parse_delim': '|',
                          'kill_on_failure': True,
                          'verbose': False,
                          'debug': False}, options)
        self.assertEqual(leftover, [])
        flist.clean()
        ulist.clean()


    def test_parse_no_flist_add_on(self):
        sys.argv = ['atest', '-g', '--parse', '-u', 'myuser,youruser',
                    '--kill-on-failure', 'left1', 'left2']
        self.atest.parser.add_option('-M', '--mlist', type='string')
        self.atest.parser.add_option('-U', '--ulist', type='string')
        self.atest.parser.add_option('-u', '--user', type='string')
        host_info = topic_common.item_parse_info(attribute_name='hosts',
                                                 use_leftover=True)
        user_info = topic_common.item_parse_info(attribute_name='users',
                                                 inline_option='user')
        (options, leftover) = self.atest.parse([host_info, user_info])
        self.assertEqualNoOrder(self.atest.hosts,
                                ['left1', 'left2'])
        self.assertEqualNoOrder(self.atest.users,
                                ['myuser', 'youruser'])

        self.assertEqual({'mlist': None,
                          'ulist': None,
                          'user': 'myuser,youruser',
                          'web_server': None,
                          'parse': True,
                          'parse_delim': '|',
                          'kill_on_failure': True,
                          'verbose': False,
                          'debug': True}, options)
        self.assertEqual(leftover, [])


    def test_parse_no_flist_no_add_on(self):
        sys.argv = ['atest', '-u', 'myuser,youruser', '--kill-on-failure',
                    '-a', 'acl1,acl2']
        self.atest.parser.add_option('-u', '--user', type='string')
        self.atest.parser.add_option('-a', '--acl', type='string')
        acl_info = topic_common.item_parse_info(attribute_name='acls',
                                                inline_option='acl')
        user_info = topic_common.item_parse_info(attribute_name='users',
                                                 inline_option='user')
        (options, leftover) = self.atest.parse([user_info, acl_info])
        self.assertEqualNoOrder(self.atest.acls,
                                ['acl1', 'acl2'])
        self.assertEqualNoOrder(self.atest.users,
                                ['myuser', 'youruser'])

        self.assertEqual({'user': 'myuser,youruser',
                          'acl': 'acl1,acl2',
                          'web_server': None,
                          'parse': False,
                          'parse_delim': '|',
                          'kill_on_failure': True,
                          'verbose': False,
                          'debug': False}, options)
        self.assertEqual(leftover, [])


    def test_parse_req_items_ok(self):
        sys.argv = ['atest', '-u', 'myuser,youruser']
        self.atest.parser.add_option('-u', '--user', type='string')
        user_info = topic_common.item_parse_info(attribute_name='users',
                                                 inline_option='user')
        (options, leftover) = self.atest.parse([user_info],
                                               req_items='users')
        self.assertEqualNoOrder(self.atest.users,
                                ['myuser', 'youruser'])

        self.assertEqual({'user': 'myuser,youruser',
                          'web_server': None,
                          'parse': False,
                          'parse_delim': '|',
                          'kill_on_failure': False,
                          'verbose': False,
                          'debug': False}, options)
        self.assertEqual(leftover, [])


    def test_parse_req_items_missing(self):
        sys.argv = ['atest', '-u', 'myuser,youruser', '--kill-on-failure']
        self.atest.parser.add_option('-u', '--user', type='string')
        acl_info = topic_common.item_parse_info(attribute_name='acls',
                                                inline_option='acl')
        user_info = topic_common.item_parse_info(attribute_name='users',
                                                 inline_option='user')
        self.god.mock_io()
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException,
                          self.atest.parse,
                          [user_info, acl_info],
                          'acls')
        self.assertEqualNoOrder(self.atest.users,
                                ['myuser', 'youruser'])

        self.assertEqualNoOrder(self.atest.acls, [])
        self.god.check_playback()
        self.god.unmock_io()


    def test_parse_bad_option(self):
        sys.argv = ['atest', '--unknown']
        self.god.stub_function(self.atest.parser, 'error')
        self.atest.parser.error.expect_call('no such option: --unknown').and_return(None)
        self.atest.parse()
        self.god.check_playback()


    def test_parse_all_set(self):
        sys.argv = ['atest', '--web', 'fooweb', '--parse', '--debug',
                    '--kill-on-failure', '--verbose', 'left1', 'left2',
                    '--parse-delim', '?']
        (options, leftover) = self.atest.parse()
        self.assertEqual({'web_server': 'fooweb',
                          'parse': True,
                          'parse_delim': '?',
                          'kill_on_failure': True,
                          'verbose': True,
                          'debug': True}, options)
        self.assertEqual(leftover, ['left1', 'left2'])


    def test_execute_rpc_bad_server(self):
        self.atest.afe = rpc.afe_comm('http://does_not_exist')
        self.god.mock_io()
        rpc.afe_comm.run.expect_call('myop').and_raises(urllib2.URLError("<urlopen error (-2, 'Name or service not known')>"))
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException,
                          self.atest.execute_rpc, 'myop')
        (output, err) = self.god.unmock_io()
        self.god.check_playback()
        self.assert_(err.find('http://does_not_exist') >= 0)


    #
    # Print Unit tests
    #
    def __test_print_fields(self, func, expected, **dargs):
        if not dargs.has_key('items'):
            dargs['items']=[{'hostname': 'h0',
                            'platform': 'p0',
                            'labels': [u'l0', u'l1'],
                            'locked': 1,
                            'id': 'id0',
                            'name': 'name0'},
                           {'hostname': 'h1',
                            'platform': 'p1',
                            'labels': [u'l2', u'l3'],
                            'locked': 0,
                            'id': 'id1',
                            'name': 'name1'}]
        self.god.mock_io()
        func(**dargs)
        (output, err) = self.god.unmock_io()
        self.assertEqual(expected, output)


    #
    # Print fields Standard
    #
    def __test_print_fields_std(self, keys, expected):
        self.__test_print_fields(self.atest.print_fields_std,
                                 expected, keys=keys)


    def test_print_fields_std_one_str(self):
        self.__test_print_fields_std(['hostname'],
                                     'Host: h0\n'
                                     'Host: h1\n')


    def test_print_fields_std_conv_bool(self):
        """Make sure the conversion functions are called"""
        self.__test_print_fields_std(['locked'],
                                     'Locked: True\n'
                                     'Locked: False\n')


    def test_print_fields_std_conv_label(self):
        """Make sure the conversion functions are called"""
        self.__test_print_fields_std(['labels'],
                                     'Labels: l0, l1\n'
                                     'Labels: l2, l3\n')


    def test_print_fields_std_all_fields(self):
        """Make sure the conversion functions are called"""
        self.__test_print_fields_std(['hostname', 'platform','locked'],
                                     'Host: h0\n'
                                     'Platform: p0\n'
                                     'Locked: True\n'
                                     'Host: h1\n'
                                     'Platform: p1\n'
                                     'Locked: False\n')


    #
    # Print fields parse
    #
    def __test_print_fields_parse(self, keys, expected):
        self.__test_print_fields(self.atest.print_fields_parse,
                                 expected, keys=keys)


    def test_print_fields_parse_one_str(self):
        self.__test_print_fields_parse(['hostname'],
                                       'Host=h0\n'
                                       'Host=h1\n')


    def test_print_fields_parse_conv_bool(self):
        self.__test_print_fields_parse(['locked'],
                                       'Locked=True\n'
                                       'Locked=False\n')


    def test_print_fields_parse_conv_label(self):
        self.__test_print_fields_parse(['labels'],
                                       'Labels=l0, l1\n'
                                       'Labels=l2, l3\n')


    def test_print_fields_parse_all_fields(self):
        self.__test_print_fields_parse(['hostname', 'platform', 'locked'],
                                       'Host=h0|Platform=p0|'
                                       'Locked=True\n'
                                       'Host=h1|Platform=p1|'
                                       'Locked=False\n')


    #
    # Print table standard
    #
    def __test_print_table_std(self, keys, expected):
        self.__test_print_fields(self.atest.print_table_std,
                                 expected, keys_header=keys)


    def test_print_table_std_all_fields(self):
        self.__test_print_table_std(['hostname', 'platform','locked'],
                                    'Host  Platform  Locked\n'
                                    'h0    p0        True\n'
                                    'h1    p1        False\n')

    # TODO JME - add long fields tests


    #
    # Print table parse
    #
    def __test_print_table_parse(self, keys, expected):
        self.__test_print_fields(self.atest.print_table_parse,
                                 expected, keys_header=keys)


    def test_print_table_parse_all_fields(self):
        self.__test_print_table_parse(['hostname', 'platform',
                                       'locked'],
                                      'Host=h0|Platform=p0|Locked=True\n'
                                      'Host=h1|Platform=p1|Locked=False\n')


    def test_print_table_parse_all_fields(self):
        self.atest.parse_delim = '?'
        self.__test_print_table_parse(['hostname', 'platform',
                                       'locked'],
                                      'Host=h0?Platform=p0?Locked=True\n'
                                      'Host=h1?Platform=p1?Locked=False\n')


    def test_print_table_parse_empty_fields(self):
        self.__test_print_fields(self.atest.print_table_parse,
                                 'Host=h0|Platform=p0\n'
                                 'Host=h1|Platform=p1|Labels=l2, l3\n',
                                 items=[{'hostname': 'h0',
                                         'platform': 'p0',
                                         'labels': [],
                                         'locked': 1,
                                         'id': 'id0',
                                         'name': 'name0'},
                                        {'hostname': 'h1',
                                         'platform': 'p1',
                                         'labels': [u'l2', u'l3'],
                                         'locked': 0,
                                         'id': 'id1',
                                         'name': 'name1'}],
                                 keys_header=['hostname', 'platform',
                                              'labels'])


    #
    # Print mix table standard
    #
    def __test_print_mix_table_std(self, keys_header, sublist_keys,
                                   expected):
        self.__test_print_fields(self.atest.print_table_std,
                                 expected,
                                 keys_header=keys_header,
                                 sublist_keys=sublist_keys)


    def test_print_mix_table(self):
        self.__test_print_mix_table_std(['name', 'hostname'], [],
                                        'Name   Host\n'
                                        'name0  h0\n'
                                        'name1  h1\n')


    def test_print_mix_table_sublist(self):
        self.__test_print_mix_table_std(['name', 'hostname'], ['labels'],
                                        'Name   Host\n'
                                        'name0  h0\n'
                                        'Labels: \n'
                                        '\tl0, l1\n\n\n'
                                        'name1  h1\n'
                                        'Labels: \n'
                                        '\tl2, l3\n\n\n')


    #
    # Print by ID standard
    #
    def __test_print_by_ids_std(self, expected):
        self.__test_print_fields(self.atest.print_by_ids_std,
                                 expected)


    def test_print_by_ids_std_all_fields(self):
        self.__test_print_by_ids_std('Id   Name\n'
                                     'id0  name0\n'
                                     'id1  name1\n')


    #
    # Print by ID parse
    #
    def __test_print_by_ids_parse(self, expected):
        self.__test_print_fields(self.atest.print_by_ids_parse,
                                 expected)


    def test_print_by_ids_parse_all_fields(self):
        self.__test_print_by_ids_parse('Id=id0|Name=name0|'
                                       'Id=id1|Name=name1\n')


if __name__ == '__main__':
    unittest.main()
