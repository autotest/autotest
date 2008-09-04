#!/usr/bin/python
#
# Copyright 2008 Google Inc. All Rights Reserved.

"""Test for atest."""

import unittest, os, sys, tempfile, StringIO, urllib2

import common
from autotest_lib.cli import cli_mock, topic_common, rpc
from autotest_lib.frontend.afe.json_rpc import proxy

class topic_common_unittest(cli_mock.cli_unittest):
    def setUp(self):
        super(topic_common_unittest, self).setUp()
        self.atest = topic_common.atest()
        self.atest.afe = rpc.afe_comm()
        if 'AUTOTEST_WEB' in os.environ:
            del os.environ['AUTOTEST_WEB']


    def tearDown(self):
        self.atest = None
        super(topic_common_unittest, self).tearDown()


    def test_file_list_wrong_file(self):
        self.god.mock_io()
        class opt(object):
            mlist = './does_not_exist'
        options = opt()
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException,
                          self.atest._file_list, options, opt_file='mlist')
        self.god.check_playback()
        (output, err) = self.god.unmock_io()
        self.assert_(err.find('./does_not_exist') >= 0)


    def test_file_list_empty_file(self):
        self.god.mock_io()
        class opt(object):
            flist = cli_mock.create_file('')
        options = opt()
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException,
                          self.atest._file_list, options, opt_file='flist')
        self.god.check_playback()
        (output, err) = self.god.unmock_io()
        self.assert_(err.find(options.flist) >= 0)


    def test_file_list_ok(self):
        class opt(object):
            filename = cli_mock.create_file('a\nb\nc\n')
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c'],
                                self.atest._file_list(options,
                                                      opt_file='filename'))
        os.unlink(options.filename)


    def test_file_list_one_line_space(self):
        class opt(object):
            filename = cli_mock.create_file('a b c\nd e\nf\n')
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c', 'd', 'e', 'f'],
                                self.atest._file_list(options,
                                                      opt_file='filename'))
        os.unlink(options.filename)


    def test_file_list_one_line_comma(self):
        class opt(object):
            filename = cli_mock.create_file('a,b,c\nd,e\nf\n')
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c', 'd', 'e', 'f'],
                                self.atest._file_list(options,
                                                      opt_file='filename'))
        os.unlink(options.filename)


    def test_file_list_one_line_mix(self):
        class opt(object):
            filename = cli_mock.create_file('a,b c\nd,e\nf\ng h,i')
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c', 'd', 'e',
                                 'f', 'g', 'h', 'i'],
                                self.atest._file_list(options,
                                                      opt_file='filename'))
        os.unlink(options.filename)


    def test_file_list_one_line_comma_space(self):
        class opt(object):
            filename = cli_mock.create_file('a, b c\nd,e\nf\ng h,i')
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c', 'd', 'e',
                                 'f', 'g', 'h', 'i'],
                                self.atest._file_list(options,
                                                      opt_file='filename'))
        os.unlink(options.filename)


    def test_file_list_line_end_comma_space(self):
        class opt(object):
            filename = cli_mock.create_file('a, b c\nd,e, \nf,\ng h,i ,')
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c', 'd', 'e',
                                 'f', 'g', 'h', 'i'],
                                self.atest._file_list(options,
                                                      opt_file='filename'))
        os.unlink(options.filename)


    def test_file_list_no_eof(self):
        class opt(object):
            filename = cli_mock.create_file('a\nb\nc')
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c'],
                                self.atest._file_list(options,
                                                      opt_file='filename'))
        os.unlink(options.filename)


    def test_file_list_blank_line(self):
        class opt(object):
            filename = cli_mock.create_file('\na\nb\n\nc\n')
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c'],
                                self.atest._file_list(options,
                                                      opt_file='filename'))
        os.unlink(options.filename)


    def test_file_list_opt_list_one(self):
        class opt(object):
            hlist = 'a'
        options = opt()
        self.assertEqualNoOrder(['a'],
                                self.atest._file_list(options,
                                                      opt_list='hlist'))


    def test_file_list_opt_list_space(self):
        class opt(object):
            hlist = 'a b c'
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c'],
                                self.atest._file_list(options,
                                                      opt_list='hlist'))


    def test_file_list_opt_list_mix_space_comma(self):
        class opt(object):
            alist = 'a b,c,d e'
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c', 'd', 'e'],
                                self.atest._file_list(options,
                                                      opt_list='alist'))


    def test_file_list_opt_list_mix_comma_space(self):
        class opt(object):
            alist = 'a b,c, d e'
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c', 'd', 'e'],
                                self.atest._file_list(options,
                                                      opt_list='alist'))


    def test_file_list_opt_list_end_comma_space(self):
        class opt(object):
            alist = 'a b, ,c,, d e, '
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c', 'd', 'e'],
                                self.atest._file_list(options,
                                                      opt_list='alist'))


    def test_file_list_add_on_space(self):
        class opt(object):
            pass
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c'],
                                self.atest._file_list(options,
                                                      add_on=['a','c','b']))


    def test_file_list_add_on_mix_space_comma(self):
        class opt(object):
            pass
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c', 'd'],
                                self.atest._file_list(options,
                                                      add_on=['a', 'c',
                                                              'b,d']))


    def test_file_list_add_on_mix_comma_space(self):
        class opt(object):
            pass
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c', 'd'],
                                self.atest._file_list(options,
                                                      add_on=['a', 'c',
                                                              'b,', 'd']))


    def test_file_list_add_on_end_comma_space(self):
        class opt(object):
            pass
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c', 'd'],
                                self.atest._file_list(options,
                                                      add_on=['a', 'c', 'b,',
                                                              'd,', ',']))


    def test_file_list_all_opt(self):
        class opt(object):
            afile = cli_mock.create_file('f\ng\nh\n')
            alist = 'a b,c,d e'
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c', 'd', 'e',
                                 'f', 'g', 'h', 'i', 'j'],
                                self.atest._file_list(options,
                                                      opt_file='afile',
                                                      opt_list='alist',
                                                      add_on=['i', 'j']))


    def test_file_list_all_opt_empty_file(self):
        self.god.mock_io()
        class opt(object):
            hfile = cli_mock.create_file('')
            hlist = 'a b,c,d e'
        options = opt()
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException,
                          self.atest._file_list,
                          options,
                          opt_file='hfile',
                          opt_list='hlist',
                          add_on=['i', 'j'])
        (output, err) = self.god.unmock_io()
        self.god.check_playback()
        self.assert_(err.find(options.hfile) >= 0)


    def test_file_list_all_opt_in_common(self):
        class opt(object):
            afile = cli_mock.create_file('f\nc\na\n')
            alist = 'a b,c,d e'
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c', 'd', 'e',
                                 'f', 'i', 'j'],
                                self.atest._file_list(options,
                                                      opt_file='afile',
                                                      opt_list='alist',
                                                      add_on=['i','j,d']))


    def test_file_list_all_opt_in_common_space(self):
        class opt(object):
            afile = cli_mock.create_file('a b c\nd,e\nf\ng')
            alist = 'a b,c,d h'
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c', 'd', 'e',
                                 'f', 'g', 'h', 'i', 'j'],
                                self.atest._file_list(options,
                                                      opt_file='afile',
                                                      opt_list='alist',
                                                      add_on=['i','j,d']))


    def test_file_list_all_opt_in_common_weird(self):
        class opt(object):
            afile = cli_mock.create_file('a b c\nd,e\nf\ng, \n, ,,')
            alist = 'a b,c,d h, ,  ,,	'
        options = opt()
        self.assertEqualNoOrder(['a', 'b', 'c', 'd', 'e',
                                 'f', 'g', 'h', 'i', 'j'],
                                self.atest._file_list(options,
                                                      opt_file='afile',
                                                      opt_list='alist',
                                                      add_on=['i','j,d']))


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


    def test_parse_with_flist_add_on(self):
        flist = cli_mock.create_file('host1\nhost2\nleft2')
        sys.argv = ['atest', '--web', 'fooweb', '--parse',
                    '--kill-on-failure', 'left1', 'left2', '-M', flist]
        self.atest.parser.add_option('-M', '--mlist', type='string')
        (options, leftover) = self.atest.parse_with_flist([('hosts',
                                                            'mlist',
                                                            [],
                                                            True)],
                                                          None)
        self.assertEqualNoOrder(self.atest.hosts,
                                ['left1', 'left2', 'host1', 'host2'])

        self.assertEqual({'mlist': flist,
                          'web_server': 'fooweb',
                          'parse': True,
                          'kill_on_failure': True,
                          'verbose': False,
                          'debug': False}, options)
        self.assertEqual(leftover, [])


    def test_parse_with_flist_no_add_on(self):
        flist = cli_mock.create_file('host1\nhost2\nleft2')
        sys.argv = ['atest', '--web', 'fooweb', '--parse', '-g',
                    '--kill-on-failure', 'left1', 'left2', '-M', flist]
        self.atest.parser.add_option('-M', '--mlist', type='string')
        (options, leftover) = self.atest.parse_with_flist([('hosts',
                                                            'mlist',
                                                            [],
                                                            False)],
                                                          None)
        self.assertEqualNoOrder(self.atest.hosts,
                                ['left2', 'host1', 'host2'])

        self.assertEqual({'mlist': flist,
                          'web_server': 'fooweb',
                          'parse': True,
                          'kill_on_failure': True,
                          'verbose': False,
                          'debug': True}, options)
        self.assertEqual(leftover, ['left1', 'left2'])


    def test_parse_with_flists_add_on_first(self):
        flist = cli_mock.create_file('host1\nhost2\nleft2')
        ulist = cli_mock.create_file('user1\nuser2\nuser3\n')
        sys.argv = ['atest', '-g', '--parse', '--ulist', ulist,
                    '-u', 'myuser,youruser',
                    '--kill-on-failure', 'left1', 'left2', '-M', flist]
        self.atest.parser.add_option('-M', '--mlist', type='string')
        self.atest.parser.add_option('-U', '--ulist', type='string')
        self.atest.parser.add_option('-u', '--user', type='string')
        (options, leftover) = self.atest.parse_with_flist([('hosts',
                                                            'mlist',
                                                            '',
                                                            True),
                                                           ('users',
                                                            'ulist',
                                                            'user',
                                                            False)],
                                                          None)
        self.assertEqualNoOrder(self.atest.hosts,
                                ['left1', 'left2', 'host1', 'host2'])
        self.assertEqualNoOrder(self.atest.users,
                                ['user1', 'user2', 'user3',
                                 'myuser', 'youruser'])

        self.assertEqual({'mlist': flist,
                          'ulist': ulist,
                          'user': 'myuser,youruser',
                          'web_server': None,
                          'parse': True,
                          'kill_on_failure': True,
                          'verbose': False,
                          'debug': True}, options)
        self.assertEqual(leftover, [])


    def test_parse_with_flists_add_on_second(self):
        flist = cli_mock.create_file('host1\nhost2\nleft2')
        ulist = cli_mock.create_file('user1\nuser2\nuser3\n')
        sys.argv = ['atest', '-g', '--parse', '-U', ulist,
                    '-u', 'myuser,youruser',
                    '--kill-on-failure', 'left1', 'left2', '-M', flist]
        self.atest.parser.add_option('-M', '--mlist', type='string')
        self.atest.parser.add_option('-U', '--ulist', type='string')
        self.atest.parser.add_option('-u', '--user', type='string')
        (options, leftover) = self.atest.parse_with_flist([('users',
                                                            'ulist',
                                                            'user',
                                                            False),
                                                           ('hosts',
                                                            'mlist',
                                                            '',
                                                            True)],
                                                          None)
        self.assertEqualNoOrder(self.atest.hosts,
                                ['left1', 'left2', 'host1', 'host2'])
        self.assertEqualNoOrder(self.atest.users,
                                ['user1', 'user2', 'user3',
                                 'myuser', 'youruser'])

        self.assertEqual({'mlist': flist,
                          'ulist': ulist,
                          'user': 'myuser,youruser',
                          'web_server': None,
                          'parse': True,
                          'kill_on_failure': True,
                          'verbose': False,
                          'debug': True}, options)
        self.assertEqual(leftover, [])


    def test_parse_with_flists_all_opts(self):
        flist = cli_mock.create_file('host1\nhost2\nleft2')
        ulist = cli_mock.create_file('user1\nuser2\nuser3\n')
        sys.argv = ['atest', '-g', '--parse', '--ulist', ulist,
                    '-u', 'myuser,youruser',
                    '--kill-on-failure', '-M', flist, 'left1', 'left2']
        self.atest.parser.add_option('-M', '--mlist', type='string')
        self.atest.parser.add_option('-U', '--ulist', type='string')
        self.atest.parser.add_option('-u', '--user', type='string')
        (options, leftover) = self.atest.parse_with_flist([('users',
                                                            'ulist',
                                                            'user',
                                                            False),
                                                           ('hosts',
                                                            'mlist',
                                                            '',
                                                            True)],
                                                          None)
        self.assertEqualNoOrder(self.atest.hosts,
                                ['left1', 'left2', 'host1', 'host2'])
        self.assertEqualNoOrder(self.atest.users,
                                ['user1', 'user2', 'user3',
                                 'myuser', 'youruser'])

        self.assertEqual({'mlist': flist,
                          'ulist': ulist,
                          'user': 'myuser,youruser',
                          'web_server': None,
                          'parse': True,
                          'kill_on_failure': True,
                          'verbose': False,
                          'debug': True}, options)
        self.assertEqual(leftover, [])


    def test_parse_with_flists_no_add_on(self):
        flist = cli_mock.create_file('host1\nhost2\nleft2')
        ulist = cli_mock.create_file('user1\nuser2\nuser3\n')
        sys.argv = ['atest', '-U', ulist,
                    '--kill-on-failure', '-M', flist]
        self.atest.parser.add_option('-M', '--mlist', type='string')
        self.atest.parser.add_option('-U', '--ulist', type='string')
        self.atest.parser.add_option('-u', '--user', type='string')
        (options, leftover) = self.atest.parse_with_flist([('hosts',
                                                            'mlist',
                                                            '',
                                                            False),
                                                           ('users',
                                                            'ulist',
                                                            'user',
                                                            False)],
                                                          None)
        self.assertEqualNoOrder(self.atest.hosts,
                                ['left2', 'host1', 'host2'])
        self.assertEqualNoOrder(self.atest.users,
                                ['user1', 'user2', 'user3'])

        self.assertEqual({'mlist': flist,
                          'ulist': ulist,
                          'user': None,
                          'web_server': None,
                          'parse': False,
                          'kill_on_failure': True,
                          'verbose': False,
                          'debug': False}, options)
        self.assertEqual(leftover, [])


    def test_parse_with_flists_no_flist_add_on(self):
        sys.argv = ['atest', '-g', '--parse', '-u', 'myuser,youruser',
                    '--kill-on-failure', 'left1', 'left2']
        self.atest.parser.add_option('-M', '--mlist', type='string')
        self.atest.parser.add_option('-U', '--ulist', type='string')
        self.atest.parser.add_option('-u', '--user', type='string')
        (options, leftover) = self.atest.parse_with_flist([('users',
                                                            '',
                                                            'user',
                                                            False),
                                                           ('hosts',
                                                            '',
                                                            '',
                                                            True)],
                                                          None)
        self.assertEqualNoOrder(self.atest.hosts,
                                ['left1', 'left2'])
        self.assertEqualNoOrder(self.atest.users,
                                ['myuser', 'youruser'])

        self.assertEqual({'mlist': None,
                          'ulist': None,
                          'user': 'myuser,youruser',
                          'web_server': None,
                          'parse': True,
                          'kill_on_failure': True,
                          'verbose': False,
                          'debug': True}, options)
        self.assertEqual(leftover, [])


    def test_parse_with_flists_no_flist_no_add_on(self):
        sys.argv = ['atest', '-u', 'myuser,youruser', '--kill-on-failure',
                    '-a', 'acl1,acl2']
        self.atest.parser.add_option('-u', '--user', type='string')
        self.atest.parser.add_option('-a', '--acl', type='string')
        (options, leftover) = self.atest.parse_with_flist([('users',
                                                            '',
                                                            'user',
                                                            False),
                                                           ('acls',
                                                            '',
                                                            'acl',
                                                            False)],
                                                          None)
        self.assertEqualNoOrder(self.atest.acls,
                                ['acl1', 'acl2'])
        self.assertEqualNoOrder(self.atest.users,
                                ['myuser', 'youruser'])

        self.assertEqual({'user': 'myuser,youruser',
                          'acl': 'acl1,acl2',
                          'web_server': None,
                          'parse': False,
                          'kill_on_failure': True,
                          'verbose': False,
                          'debug': False}, options)
        self.assertEqual(leftover, [])


    def test_parse_with_flists_req_items_ok(self):
        sys.argv = ['atest', '-u', 'myuser,youruser']
        self.atest.parser.add_option('-u', '--user', type='string')
        (options, leftover) = self.atest.parse_with_flist([('users',
                                                            '',
                                                            'user',
                                                            False)],
                                                          'users')
        self.assertEqualNoOrder(self.atest.users,
                                ['myuser', 'youruser'])

        self.assertEqual({'user': 'myuser,youruser',
                          'web_server': None,
                          'parse': False,
                          'kill_on_failure': False,
                          'verbose': False,
                          'debug': False}, options)
        self.assertEqual(leftover, [])


    def test_parse_with_flists_req_items_missing(self):
        sys.argv = ['atest', '-u', 'myuser,youruser', '--kill-on-failure']
        self.atest.parser.add_option('-u', '--user', type='string')
        self.god.mock_io()
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.assertRaises(cli_mock.ExitException,
                          self.atest.parse_with_flist,
                          [('users', '', 'user', False),
                           ('acls', '', 'acl', False)],
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
                    '--kill-on-failure', '--verbose', 'left1', 'left2']
        (options, leftover) = self.atest.parse()
        self.assertEqual({'web_server': 'fooweb',
                          'parse': True,
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
                                       'Host=h0:Platform=p0:'
                                       'Locked=True\n'
                                       'Host=h1:Platform=p1:'
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
                                      'Host=h0:Platform=p0:Locked=True\n'
                                      'Host=h1:Platform=p1:Locked=False\n')

    def test_print_table_parse_empty_fields(self):
        self.__test_print_fields(self.atest.print_table_parse,
                                 'Host=h0:Platform=p0\n'
                                 'Host=h1:Platform=p1:Labels=l2, l3\n',
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
        self.__test_print_mix_table_std(['name', 'hostname'],
                                        ['hosts', 'users'],
                                        'Name   Host\n'
                                        'name0  h0\n'
                                        'name1  h1\n')

    # TODO(jmeurin) Add actual test with sublist_keys.



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
        self.__test_print_by_ids_parse('Id=id0:Name=name0:'
                                       'Id=id1:Name=name1\n')


if __name__ == '__main__':
    unittest.main()
