#!/usr/bin/python
#
# Copyright 2008 Google Inc. All Rights Reserved.

"""Test for host."""

import unittest, os, sys

import common
from autotest_lib.cli import cli_mock, host


class host_ut(cli_mock.cli_unittest):
    def test_parse_lock_options_both_set(self):
        hh = host.host()
        class opt(object):
            lock = True
            unlock = True
        options = opt()
        self.usage = "unused"
        sys.exit.expect_call(1).and_raises(cli_mock.ExitException)
        self.god.mock_io()
        self.assertRaises(cli_mock.ExitException,
                          hh._parse_lock_options, options)
        self.god.unmock_io()


    def test_cleanup_labels_with_platform(self):
        labels = ['l0', 'l1', 'l2', 'p0', 'l3']
        hh = host.host()
        self.assertEqual(['l0', 'l1', 'l2', 'l3'],
                         hh._cleanup_labels(labels, 'p0'))


    def test_cleanup_labels_no_platform(self):
        labels = ['l0', 'l1', 'l2', 'l3']
        hh = host.host()
        self.assertEqual(['l0', 'l1', 'l2', 'l3'],
                         hh._cleanup_labels(labels))


    def test_cleanup_labels_with_non_avail_platform(self):
        labels = ['l0', 'l1', 'l2', 'l3']
        hh = host.host()
        self.assertEqual(['l0', 'l1', 'l2', 'l3'],
                         hh._cleanup_labels(labels, 'p0'))


class host_list_unittest(cli_mock.cli_unittest):
    def test_parse_host_not_required(self):
        hl = host.host_list()
        sys.argv = ['atest']
        (options, leftover) = hl.parse()
        self.assertEqual([], hl.hosts)
        self.assertEqual([], leftover)


    def test_parse_with_hosts(self):
        hl = host.host_list()
        mfile = cli_mock.create_file('host0\nhost3\nhost4\n')
        sys.argv = ['atest', 'host1', '--mlist', mfile.name, 'host3']
        (options, leftover) = hl.parse()
        self.assertEqualNoOrder(['host0', 'host1','host3', 'host4'],
                                hl.hosts)
        self.assertEqual(leftover, [])
        mfile.clean()


    def test_parse_with_labels(self):
        hl = host.host_list()
        sys.argv = ['atest', '--label', 'label0']
        (options, leftover) = hl.parse()
        self.assertEqual('label0', hl.labels)
        self.assertEqual(leftover, [])


    def test_parse_with_multi_labels(self):
        hl = host.host_list()
        sys.argv = ['atest', '--label', 'label0,label2']
        (options, leftover) = hl.parse()
        self.assertEqual('label0,label2', hl.labels)
        self.assertEqual(leftover, [])


    def test_parse_with_both(self):
        hl = host.host_list()
        mfile = cli_mock.create_file('host0\nhost3\nhost4\n')
        sys.argv = ['atest', 'host1', '--mlist', mfile.name, 'host3',
                    '--label', 'label0']
        (options, leftover) = hl.parse()
        self.assertEqualNoOrder(['host0', 'host1','host3', 'host4'],
                                hl.hosts)
        self.assertEqual('label0', hl.labels)
        self.assertEqual(leftover, [])
        mfile.clean()


    def test_execute_list_all_no_labels(self):
        self.run_cmd(argv=['atest', 'host', 'list', '--ignore_site_file'],
                     rpcs=[('get_hosts', {},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': None,
                              u'id': 1},
                             {u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 2}])],
                     out_words_ok=['host0', 'host1', 'Ready',
                                   'plat1', 'False', 'True'])


    def test_execute_list_all_with_labels(self):
        self.run_cmd(argv=['atest', 'host', 'list', '--ignore_site_file'],
                     rpcs=[('get_hosts', {},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label0', u'label1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': None,
                              u'id': 1},
                             {u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 2}])],
                     out_words_ok=['host0', 'host1', 'Ready', 'plat1',
                                   'label0', 'label1', 'label2', 'label3',
                                   'False', 'True'])


    def test_execute_list_filter_one_host(self):
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '--ignore_site_file'],
                     rpcs=[('get_hosts', {'hostname__in': ['host1']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 2}])],
                     out_words_ok=['host1', 'Ready', 'plat1',
                                   'label2', 'label3', 'True'],
                     out_words_no=['host0', 'host2',
                                   'label1', 'label4', 'False'])


    def test_execute_list_filter_two_hosts(self):
        mfile = cli_mock.create_file('host2')
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '--mlist', mfile.name, '--ignore_site_file'],
                     # This is a bit fragile as the list order may change...
                     rpcs=[('get_hosts', {'hostname__in': ['host2', 'host1']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 2},
                             {u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host1', 'Ready', 'plat1',
                                   'label2', 'label3', 'True',
                                   'host2', 'label4'],
                     out_words_no=['host0', 'label1', 'False'])
        mfile.clean()


    def test_execute_list_filter_two_hosts_one_not_found(self):
        mfile = cli_mock.create_file('host2')
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '--mlist', mfile.name, '--ignore_site_file'],
                     # This is a bit fragile as the list order may change...
                     rpcs=[('get_hosts', {'hostname__in': ['host2', 'host1']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['Ready', 'plat1',
                                   'label3', 'label4', 'True'],
                     out_words_no=['host1', 'False'],
                     err_words_ok=['host1'])
        mfile.clean()


    def test_execute_list_filter_two_hosts_none_found(self):
        self.run_cmd(argv=['atest', 'host', 'list',
                           'host1', 'host2', '--ignore_site_file'],
                     # This is a bit fragile as the list order may change...
                     rpcs=[('get_hosts', {'hostname__in': ['host2', 'host1']},
                            True,
                            [])],
                     out_words_ok=[],
                     out_words_no=['Hostname', 'Status'],
                     err_words_ok=['Unknown', 'host1', 'host2'])


    def test_execute_list_filter_label(self):
        self.run_cmd(argv=['atest', 'host', 'list',
                           '-b', 'label3', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'labels__name__in': ['label3']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 2},
                             {u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host1', 'Ready', 'plat1',
                                   'label2', 'label3', 'True',
                                   'host2', 'label4'],
                     out_words_no=['host0', 'label1', 'False'])


    def test_execute_list_filter_multi_labels(self):
        self.run_cmd(argv=['atest', 'host', 'list',
                           '-b', 'label3,label2', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'multiple_labels': ['label3',
                                                              'label2']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label2', u'label3', u'plat0'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat0',
                              u'id': 2},
                             {u'status': u'Ready',
                              u'hostname': u'host3',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label3', u'label2', u'plat2'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat2',
                              u'id': 4}])],
                     out_words_ok=['host1', 'host3', 'Ready', 'plat0',
                                   'label2', 'label3', 'plat2'],
                     out_words_no=['host2', 'label4', 'False', 'plat1'])


    def test_execute_list_filter_three_labels(self):
        self.run_cmd(argv=['atest', 'host', 'list',
                           '-b', 'label3,label2, label4',
                           '--ignore_site_file'],
                     rpcs=[('get_hosts', {'multiple_labels': ['label3',
                                                              'label2',
                                                              'label4']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label3', u'label2', u'label4',
                                          u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host2', 'plat1',
                                   'label2', 'label3', 'label4'],
                     out_words_no=['host1', 'host3'])


    def test_execute_list_filter_wild_labels(self):
        self.run_cmd(argv=['atest', 'host', 'list',
                           '-b', 'label*',
                           '--ignore_site_file'],
                     rpcs=[('get_hosts',
                            {'labels__name__startswith': 'label'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': 1,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label3', u'label2', u'label4',
                                          u'plat1'],
                              u'invalid': 0,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host2', 'plat1',
                                   'label2', 'label3', 'label4'],
                     out_words_no=['host1', 'host3'])


    def test_execute_list_filter_multi_labels_no_results(self):
        self.run_cmd(argv=['atest', 'host', 'list',
                           '-b', 'label3,label2, ', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'multiple_labels': ['label3',
                                                              'label2']},
                            True,
                            [])],
                     out_words_ok=[],
                     out_words_no=['host1', 'host2', 'host3',
                                   'label2', 'label3', 'label4'])


    def test_execute_list_filter_label_and_hosts(self):
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '-b', 'label3', 'host2', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'labels__name__in': ['label3'],
                                          'hostname__in': ['host2', 'host1']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 2},
                             {u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host1', 'Ready', 'plat1',
                                   'label2', 'label3', 'True',
                                   'host2', 'label4'],
                     out_words_no=['host0', 'label1', 'False'])


    def test_execute_list_filter_label_and_hosts_none(self):
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '-b', 'label3', 'host2', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'labels__name__in': ['label3'],
                                          'hostname__in': ['host2', 'host1']},
                            True,
                            [])],
                     out_words_ok=[],
                     out_words_no=['Hostname', 'Status'],
                     err_words_ok=['Unknown', 'host1', 'host2'])


    def test_execute_list_filter_status(self):
        self.run_cmd(argv=['atest', 'host', 'list',
                           '-s', 'Ready', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'status__in': ['Ready']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 2},
                             {u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host1', 'Ready', 'plat1',
                                   'label2', 'label3', 'True',
                                   'host2', 'label4'],
                     out_words_no=['host0', 'label1', 'False'])



    def test_execute_list_filter_status_and_hosts(self):
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '-s', 'Ready', 'host2', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'status__in': ['Ready'],
                                          'hostname__in': ['host2', 'host1']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 2},
                             {u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host1', 'Ready', 'plat1',
                                   'label2', 'label3', 'True',
                                   'host2', 'label4'],
                     out_words_no=['host0', 'label1', 'False'])


    def test_execute_list_filter_status_and_hosts_none(self):
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '--status', 'Repair',
                           'host2', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'status__in': ['Repair'],
                                          'hostname__in': ['host2', 'host1']},
                            True,
                            [])],
                     out_words_ok=[],
                     out_words_no=['Hostname', 'Status'],
                     err_words_ok=['Unknown', 'host2'])


    def test_execute_list_filter_statuses_and_hosts_none(self):
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '--status', 'Repair',
                           'host2', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'status__in': ['Repair'],
                                          'hostname__in': ['host2', 'host1']},
                            True,
                            [])],
                     out_words_ok=[],
                     out_words_no=['Hostname', 'Status'],
                     err_words_ok=['Unknown', 'host2'])


    def test_execute_list_filter_locked(self):
        self.run_cmd(argv=['atest', 'host', 'list', 'host1',
                           '--locked', 'host2', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'locked': True,
                                          'hostname__in': ['host2', 'host1']},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 2},
                             {u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': True,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host1', 'Ready', 'plat1',
                                   'label2', 'label3', 'True',
                                   'host2', 'label4'],
                     out_words_no=['host0', 'label1', 'False'])


    def test_execute_list_filter_unlocked(self):
        self.run_cmd(argv=['atest', 'host', 'list',
                           '--unlocked', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'locked': False},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label2', u'label3', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 2},
                             {u'status': u'Ready',
                              u'hostname': u'host2',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3}])],
                     out_words_ok=['host1', 'Ready', 'plat1',
                                   'label2', 'label3', 'False',
                                   'host2', 'label4'],
                     out_words_no=['host0', 'label1', 'True'])


class host_stat_unittest(cli_mock.cli_unittest):
    def test_execute_stat_two_hosts(self):
        # The order of RPCs between host1 and host0 could change...
        self.run_cmd(argv=['atest', 'host', 'stat', 'host0', 'host1',
                           '--ignore_site_file'],
                     rpcs=[('get_hosts', {'hostname': 'host1'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'locked_by': 'user0',
                              u'protection': 'No protection',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3}]),
                           ('get_hosts', {'hostname': 'host0'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'protection': u'No protection',
                              u'labels': [u'label0', u'plat0'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat0',
                              u'id': 2}]),
                           ('get_acl_groups', {'hosts__hostname': 'host1'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'host0', u'host1'],
                              u'id': 1,
                              u'name': u'Everyone',
                              u'users': [u'user2', u'debug_user', u'user0']}]),
                           ('get_labels', {'host__hostname': 'host1'},
                            True,
                            [{u'id': 2,
                              u'platform': 1,
                              u'name': u'jme',
                              u'invalid': False,
                              u'kernel_config': u''}]),
                           ('get_acl_groups', {'hosts__hostname': 'host0'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'host0', u'host1'],
                              u'id': 1,
                              u'name': u'Everyone',
                              u'users': [u'user0', u'debug_user']},
                             {u'description': u'myacl0',
                              u'hosts': [u'host0'],
                              u'id': 2,
                              u'name': u'acl0',
                              u'users': [u'user0']}]),
                           ('get_labels', {'host__hostname': 'host0'},
                            True,
                            [{u'id': 4,
                              u'platform': 0,
                              u'name': u'label0',
                              u'invalid': False,
                              u'kernel_config': u''},
                             {u'id': 5,
                              u'platform': 1,
                              u'name': u'plat0',
                              u'invalid': False,
                              u'kernel_config': u''}])],
                     out_words_ok=['host0', 'host1', 'plat0', 'plat1',
                                   'Everyone', 'acl0', 'label0'])


    def test_execute_stat_one_bad_host_verbose(self):
        self.run_cmd(argv=['atest', 'host', 'stat', 'host0',
                           'host1', '-v', '--ignore_site_file'],
                     rpcs=[('get_hosts', {'hostname': 'host1'},
                            True,
                            []),
                           ('get_hosts', {'hostname': 'host0'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'protection': u'No protection',
                              u'labels': [u'label0', u'plat0'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat0',
                              u'id': 2}]),
                           ('get_acl_groups', {'hosts__hostname': 'host0'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'host0', u'host1'],
                              u'id': 1,
                              u'name': u'Everyone',
                              u'users': [u'user0', u'debug_user']},
                             {u'description': u'myacl0',
                              u'hosts': [u'host0'],
                              u'id': 2,
                              u'name': u'acl0',
                              u'users': [u'user0']}]),
                           ('get_labels', {'host__hostname': 'host0'},
                            True,
                            [{u'id': 4,
                              u'platform': 0,
                              u'name': u'label0',
                              u'invalid': False,
                              u'kernel_config': u''},
                             {u'id': 5,
                              u'platform': 1,
                              u'name': u'plat0',
                              u'invalid': False,
                              u'kernel_config': u''}])],
                     out_words_ok=['host0', 'plat0',
                                   'Everyone', 'acl0', 'label0'],
                     out_words_no=['host1'],
                     err_words_ok=['host1', 'Unknown host'],
                     err_words_no=['host0'])


    def test_execute_stat_one_bad_host(self):
        self.run_cmd(argv=['atest', 'host', 'stat', 'host0', 'host1',
                           '--ignore_site_file'],
                     rpcs=[('get_hosts', {'hostname': 'host1'},
                            True,
                            []),
                           ('get_hosts', {'hostname': 'host0'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'protection': u'No protection',
                              u'labels': [u'label0', u'plat0'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat0',
                              u'id': 2}]),
                           ('get_acl_groups', {'hosts__hostname': 'host0'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'host0', u'host1'],
                              u'id': 1,
                              u'name': u'Everyone',
                              u'users': [u'user0', u'debug_user']},
                             {u'description': u'myacl0',
                              u'hosts': [u'host0'],
                              u'id': 2,
                              u'name': u'acl0',
                              u'users': [u'user0']}]),
                           ('get_labels', {'host__hostname': 'host0'},
                            True,
                            [{u'id': 4,
                              u'platform': 0,
                              u'name': u'label0',
                              u'invalid': False,
                              u'kernel_config': u''},
                             {u'id': 5,
                              u'platform': 1,
                              u'name': u'plat0',
                              u'invalid': False,
                              u'kernel_config': u''}])],
                     out_words_ok=['host0', 'plat0',
                                   'Everyone', 'acl0', 'label0'],
                     out_words_no=['host1'],
                     err_words_ok=['host1', 'Unknown host'],
                     err_words_no=['host0'])


    def test_execute_stat_wildcard(self):
        # The order of RPCs between host1 and host0 could change...
        self.run_cmd(argv=['atest', 'host', 'stat', 'ho*',
                           '--ignore_site_file'],
                     rpcs=[('get_hosts', {'hostname__startswith': 'ho'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'locked_by': 'user0',
                              u'protection': 'No protection',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3},
                            {u'status': u'Ready',
                              u'hostname': u'host0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'protection': u'No protection',
                              u'labels': [u'label0', u'plat0'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat0',
                              u'id': 2}]),
                           ('get_acl_groups', {'hosts__hostname': 'host1'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'host0', u'host1'],
                              u'id': 1,
                              u'name': u'Everyone',
                              u'users': [u'user2', u'debug_user', u'user0']}]),
                           ('get_labels', {'host__hostname': 'host1'},
                            True,
                            [{u'id': 2,
                              u'platform': 1,
                              u'name': u'jme',
                              u'invalid': False,
                              u'kernel_config': u''}]),
                           ('get_acl_groups', {'hosts__hostname': 'host0'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'host0', u'host1'],
                              u'id': 1,
                              u'name': u'Everyone',
                              u'users': [u'user0', u'debug_user']},
                             {u'description': u'myacl0',
                              u'hosts': [u'host0'],
                              u'id': 2,
                              u'name': u'acl0',
                              u'users': [u'user0']}]),
                           ('get_labels', {'host__hostname': 'host0'},
                            True,
                            [{u'id': 4,
                              u'platform': 0,
                              u'name': u'label0',
                              u'invalid': False,
                              u'kernel_config': u''},
                             {u'id': 5,
                              u'platform': 1,
                              u'name': u'plat0',
                              u'invalid': False,
                              u'kernel_config': u''}])],
                     out_words_ok=['host0', 'host1', 'plat0', 'plat1',
                                   'Everyone', 'acl0', 'label0'])


    def test_execute_stat_wildcard_and_host(self):
        # The order of RPCs between host1 and host0 could change...
        self.run_cmd(argv=['atest', 'host', 'stat', 'ho*', 'newhost0',
                           '--ignore_site_file'],
                     rpcs=[('get_hosts', {'hostname': 'newhost0'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'newhost0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'protection': u'No protection',
                              u'labels': [u'label0', u'plat0'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat0',
                              u'id': 5}]),
                           ('get_hosts', {'hostname__startswith': 'ho'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'locked_by': 'user0',
                              u'protection': 'No protection',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3},
                            {u'status': u'Ready',
                              u'hostname': u'host0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'protection': 'No protection',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label0', u'plat0'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat0',
                              u'id': 2}]),
                           ('get_acl_groups', {'hosts__hostname': 'newhost0'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'newhost0', 'host1'],
                              u'id': 42,
                              u'name': u'my_acl',
                              u'users': [u'user0', u'debug_user']},
                             {u'description': u'my favorite acl',
                              u'hosts': [u'newhost0'],
                              u'id': 2,
                              u'name': u'acl10',
                              u'users': [u'user0']}]),
                           ('get_labels', {'host__hostname': 'newhost0'},
                            True,
                            [{u'id': 4,
                              u'platform': 0,
                              u'name': u'label0',
                              u'invalid': False,
                              u'kernel_config': u''},
                             {u'id': 5,
                              u'platform': 1,
                              u'name': u'plat0',
                              u'invalid': False,
                              u'kernel_config': u''}]),
                           ('get_acl_groups', {'hosts__hostname': 'host1'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'host0', u'host1'],
                              u'id': 1,
                              u'name': u'Everyone',
                              u'users': [u'user2', u'debug_user', u'user0']}]),
                           ('get_labels', {'host__hostname': 'host1'},
                            True,
                            [{u'id': 2,
                              u'platform': 1,
                              u'name': u'jme',
                              u'invalid': False,
                              u'kernel_config': u''}]),
                           ('get_acl_groups', {'hosts__hostname': 'host0'},
                            True,
                            [{u'description': u'',
                              u'hosts': [u'host0', u'host1'],
                              u'id': 1,
                              u'name': u'Everyone',
                              u'users': [u'user0', u'debug_user']},
                             {u'description': u'myacl0',
                              u'hosts': [u'host0'],
                              u'id': 2,
                              u'name': u'acl0',
                              u'users': [u'user0']}]),
                           ('get_labels', {'host__hostname': 'host0'},
                            True,
                            [{u'id': 4,
                              u'platform': 0,
                              u'name': u'label0',
                              u'invalid': False,
                              u'kernel_config': u''},
                             {u'id': 5,
                              u'platform': 1,
                              u'name': u'plat0',
                              u'invalid': False,
                              u'kernel_config': u''}])],
                     out_words_ok=['host0', 'host1', 'newhost0',
                                   'plat0', 'plat1',
                                   'Everyone', 'acl10', 'label0'])


class host_jobs_unittest(cli_mock.cli_unittest):
    def test_execute_jobs_one_host(self):
        self.run_cmd(argv=['atest', 'host', 'jobs', 'host0',
                           '--ignore_site_file'],
                     rpcs=[('get_host_queue_entries',
                            {'host__hostname': 'host0', 'query_limit': 20,
                             'sort_by': ['-job__id']},
                            True,
                            [{u'status': u'Failed',
                              u'complete': 1,
                              u'host': {u'status': u'Ready',
                                        u'locked': True,
                                        u'locked_by': 'user0',
                                        u'hostname': u'host0',
                                        u'invalid': False,
                                        u'id': 3232,
                                        u'synch_id': None},
                              u'priority': 0,
                              u'meta_host': u'meta0',
                              u'job': {u'control_file':
                                       (u"def step_init():\n"
                                        "\tjob.next_step([step_test])\n"
                                        "\ttestkernel = job.kernel("
                                        "'kernel-smp-2.6.xyz.x86_64.rpm')\n"
                                        "\ttestkernel.install()\n"
                                        "\ttestkernel.boot()\n\n"
                                        "def step_test():\n"
                                        "\tjob.run_test('kernbench')\n\n"),
                                       u'name': u'kernel-smp-2.6.xyz.x86_64',
                                       u'control_type': u'Client',
                                       u'synchronizing': None,
                                       u'priority': u'Low',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-01-09 10:45:12',
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 216},
                                       u'active': 0,
                                       u'id': 2981},
                              {u'status': u'Aborted',
                               u'complete': 1,
                               u'host': {u'status': u'Ready',
                                         u'locked': True,
                                         u'locked_by': 'user0',
                                         u'hostname': u'host0',
                                         u'invalid': False,
                                         u'id': 3232,
                                         u'synch_id': None},
                               u'priority': 0,
                               u'meta_host': None,
                               u'job': {u'control_file':
                                        u"job.run_test('sleeptest')\n\n",
                                        u'name': u'testjob',
                                        u'control_type': u'Client',
                                        u'synchronizing': 0,
                                        u'priority': u'Low',
                                        u'owner': u'user1',
                                        u'created_on': u'2008-01-17 15:04:53',
                                        u'synch_count': None,
                                        u'synch_type': u'Asynchronous',
                                        u'id': 289},
                               u'active': 0,
                               u'id': 3167}])],
                     out_words_ok=['216', 'user0', 'Failed',
                                   'kernel-smp-2.6.xyz.x86_64', 'Aborted',
                                   '289', 'user1', 'Aborted',
                                   'testjob'])


    def test_execute_jobs_wildcard(self):
        self.run_cmd(argv=['atest', 'host', 'jobs', 'ho*',
                           '--ignore_site_file'],
                     rpcs=[('get_hosts', {'hostname__startswith': 'ho'},
                            True,
                            [{u'status': u'Ready',
                              u'hostname': u'host1',
                              u'locked': True,
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'locked_by': 'user0',
                              u'labels': [u'label3', u'label4', u'plat1'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat1',
                              u'id': 3},
                            {u'status': u'Ready',
                              u'hostname': u'host0',
                              u'locked': False,
                              u'locked_by': 'user0',
                              u'lock_time': u'2008-07-23 12:54:15',
                              u'labels': [u'label0', u'plat0'],
                              u'invalid': False,
                              u'synch_id': None,
                              u'platform': u'plat0',
                              u'id': 2}]),
                           ('get_host_queue_entries',
                            {'host__hostname': 'host1', 'query_limit': 20,
                             'sort_by': ['-job__id']},
                            True,
                            [{u'status': u'Failed',
                              u'complete': 1,
                              u'host': {u'status': u'Ready',
                                        u'locked': True,
                                        u'locked_by': 'user0',
                                        u'hostname': u'host1',
                                        u'invalid': False,
                                        u'id': 3232,
                                        u'synch_id': None},
                              u'priority': 0,
                              u'meta_host': u'meta0',
                              u'job': {u'control_file':
                                       (u"def step_init():\n"
                                        "\tjob.next_step([step_test])\n"
                                        "\ttestkernel = job.kernel("
                                        "'kernel-smp-2.6.xyz.x86_64.rpm')\n"
                                        "\ttestkernel.install()\n"
                                        "\ttestkernel.boot()\n\n"
                                        "def step_test():\n"
                                        "\tjob.run_test('kernbench')\n\n"),
                                       u'name': u'kernel-smp-2.6.xyz.x86_64',
                                       u'control_type': u'Client',
                                       u'synchronizing': None,
                                       u'priority': u'Low',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-01-09 10:45:12',
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 216},
                                       u'active': 0,
                                       u'id': 2981},
                              {u'status': u'Aborted',
                               u'complete': 1,
                               u'host': {u'status': u'Ready',
                                         u'locked': True,
                                         u'locked_by': 'user0',
                                         u'hostname': u'host1',
                                         u'invalid': False,
                                         u'id': 3232,
                                         u'synch_id': None},
                               u'priority': 0,
                               u'meta_host': None,
                               u'job': {u'control_file':
                                        u"job.run_test('sleeptest')\n\n",
                                        u'name': u'testjob',
                                        u'control_type': u'Client',
                                        u'synchronizing': 0,
                                        u'priority': u'Low',
                                        u'owner': u'user1',
                                        u'created_on': u'2008-01-17 15:04:53',
                                        u'synch_count': None,
                                        u'synch_type': u'Asynchronous',
                                        u'id': 289},
                               u'active': 0,
                               u'id': 3167}]),
                           ('get_host_queue_entries',
                            {'host__hostname': 'host0', 'query_limit': 20,
                             'sort_by': ['-job__id']},
                            True,
                            [{u'status': u'Failed',
                              u'complete': 1,
                              u'host': {u'status': u'Ready',
                                        u'locked': True,
                                        u'locked_by': 'user0',
                                        u'hostname': u'host0',
                                        u'invalid': False,
                                        u'id': 3232,
                                        u'synch_id': None},
                              u'priority': 0,
                              u'meta_host': u'meta0',
                              u'job': {u'control_file':
                                       (u"def step_init():\n"
                                        "\tjob.next_step([step_test])\n"
                                        "\ttestkernel = job.kernel("
                                        "'kernel-smp-2.6.xyz.x86_64.rpm')\n"
                                        "\ttestkernel.install()\n"
                                        "\ttestkernel.boot()\n\n"
                                        "def step_test():\n"
                                        "\tjob.run_test('kernbench')\n\n"),
                                       u'name': u'kernel-smp-2.6.xyz.x86_64',
                                       u'control_type': u'Client',
                                       u'synchronizing': None,
                                       u'priority': u'Low',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-01-09 10:45:12',
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 216},
                                       u'active': 0,
                                       u'id': 2981},
                              {u'status': u'Aborted',
                               u'complete': 1,
                               u'host': {u'status': u'Ready',
                                         u'locked': True,
                                         u'locked_by': 'user0',
                                         u'hostname': u'host0',
                                         u'invalid': False,
                                         u'id': 3232,
                                         u'synch_id': None},
                               u'priority': 0,
                               u'meta_host': None,
                               u'job': {u'control_file':
                                        u"job.run_test('sleeptest')\n\n",
                                        u'name': u'testjob',
                                        u'control_type': u'Client',
                                        u'synchronizing': 0,
                                        u'priority': u'Low',
                                        u'owner': u'user1',
                                        u'created_on': u'2008-01-17 15:04:53',
                                        u'synch_count': None,
                                        u'synch_type': u'Asynchronous',
                                        u'id': 289},
                               u'active': 0,
                               u'id': 3167}])],
                     out_words_ok=['216', 'user0', 'Failed',
                                   'kernel-smp-2.6.xyz.x86_64', 'Aborted',
                                   '289', 'user1', 'Aborted',
                                   'testjob'])


    def test_execute_jobs_one_host_limit(self):
        self.run_cmd(argv=['atest', 'host', 'jobs', 'host0',
                           '--ignore_site_file', '-q', '10'],
                     rpcs=[('get_host_queue_entries',
                            {'host__hostname': 'host0', 'query_limit': 10,
                             'sort_by': ['-job__id']},
                            True,
                            [{u'status': u'Failed',
                              u'complete': 1,
                              u'host': {u'status': u'Ready',
                                        u'locked': True,
                                        u'locked_by': 'user0',
                                        u'hostname': u'host0',
                                        u'invalid': False,
                                        u'id': 3232,
                                        u'synch_id': None},
                              u'priority': 0,
                              u'meta_host': u'meta0',
                              u'job': {u'control_file':
                                       (u"def step_init():\n"
                                        "\tjob.next_step([step_test])\n"
                                        "\ttestkernel = job.kernel("
                                        "'kernel-smp-2.6.xyz.x86_64.rpm')\n"
                                        "\ttestkernel.install()\n"
                                        "\ttestkernel.boot()\n\n"
                                        "def step_test():\n"
                                        "\tjob.run_test('kernbench')\n\n"),
                                       u'name': u'kernel-smp-2.6.xyz.x86_64',
                                       u'control_type': u'Client',
                                       u'synchronizing': None,
                                       u'priority': u'Low',
                                       u'owner': u'user0',
                                       u'created_on': u'2008-01-09 10:45:12',
                                       u'synch_count': None,
                                       u'synch_type': u'Asynchronous',
                                       u'id': 216},
                                       u'active': 0,
                                       u'id': 2981},
                              {u'status': u'Aborted',
                               u'complete': 1,
                               u'host': {u'status': u'Ready',
                                         u'locked': True,
                                         u'locked_by': 'user0',
                                         u'hostname': u'host0',
                                         u'invalid': False,
                                         u'id': 3232,
                                         u'synch_id': None},
                               u'priority': 0,
                               u'meta_host': None,
                               u'job': {u'control_file':
                                        u"job.run_test('sleeptest')\n\n",
                                        u'name': u'testjob',
                                        u'control_type': u'Client',
                                        u'synchronizing': 0,
                                        u'priority': u'Low',
                                        u'owner': u'user1',
                                        u'created_on': u'2008-01-17 15:04:53',
                                        u'synch_count': None,
                                        u'synch_type': u'Asynchronous',
                                        u'id': 289},
                               u'active': 0,
                               u'id': 3167}])],
                     out_words_ok=['216', 'user0', 'Failed',
                                   'kernel-smp-2.6.xyz.x86_64', 'Aborted',
                                   '289', 'user1', 'Aborted',
                                   'testjob'])


class host_mod_unittest(cli_mock.cli_unittest):
    def test_execute_lock_one_host(self):
        self.run_cmd(argv=['atest', 'host', 'mod',
                           '--lock', 'host0', '--ignore_site_file'],
                     rpcs=[('modify_host', {'id': 'host0', 'locked': True},
                            True, None)],
                     out_words_ok=['Locked', 'host0'])


    def test_execute_unlock_two_hosts(self):
        self.run_cmd(argv=['atest', 'host', 'mod',
                           '-u', 'host0,host1', '--ignore_site_file'],
                     rpcs=[('modify_host', {'id': 'host1', 'locked': False},
                            True, None),
                           ('modify_host', {'id': 'host0', 'locked': False},
                            True, None)],
                     out_words_ok=['Unlocked', 'host0', 'host1'])


    def test_execute_lock_unknown_hosts(self):
        self.run_cmd(argv=['atest', 'host', 'mod',
                           '-l', 'host0,host1', 'host2', '--ignore_site_file'],
                     rpcs=[('modify_host', {'id': 'host2', 'locked': True},
                            True, None),
                           ('modify_host', {'id': 'host1', 'locked': True},
                            False, 'DoesNotExist: Host matching '
                            'query does not exist.'),
                           ('modify_host', {'id': 'host0', 'locked': True},
                            True, None)],
                     out_words_ok=['Locked', 'host0', 'host2'],
                     err_words_ok=['Host', 'matching', 'query', 'host1'])


    def test_execute_protection_hosts(self):
        mfile = cli_mock.create_file('host0\nhost1,host2\nhost3 host4')
        self.run_cmd(argv=['atest', 'host', 'mod', '--protection',
                           'Do not repair',
                           'host5' ,'--mlist', mfile.name, 'host1', 'host6',
                           '--ignore_site_file'],
                     rpcs=[('modify_host', {'id': 'host6',
                                            'protection': 'Do not repair'},
                            True, None),
                           ('modify_host', {'id': 'host5',
                                            'protection': 'Do not repair'},
                            True, None),
                           ('modify_host', {'id': 'host4',
                                            'protection': 'Do not repair'},
                            True, None),
                           ('modify_host', {'id': 'host3',
                                            'protection': 'Do not repair'},
                            True, None),
                           ('modify_host', {'id': 'host2',
                                            'protection': 'Do not repair'},
                            True, None),
                           ('modify_host', {'id': 'host1',
                                            'protection': 'Do not repair'},
                            True, None),
                           ('modify_host', {'id': 'host0',
                                            'protection': 'Do not repair'},
                            True, None)],
                     out_words_ok=['Do not repair', 'host0', 'host1', 'host2',
                                   'host3', 'host4', 'host5', 'host6'])
        mfile.clean()



class host_create_unittest(cli_mock.cli_unittest):
    def test_execute_create_muliple_hosts_all_options(self):
        self.run_cmd(argv=['atest', 'host', 'create', '--lock',
                           '-b', 'label0', '--acls', 'acl0', 'host0', 'host1',
                           '--ignore_site_file'],
                     rpcs=[('get_labels', {'name': 'label0'},
                            True,
                            [{u'id': 4,
                              u'platform': 0,
                              u'name': u'label0',
                              u'invalid': False,
                              u'kernel_config': u''}]),
                           ('get_acl_groups', {'name': 'acl0'},
                            True, []),
                           ('add_acl_group', {'name': 'acl0'},
                            True, 5),
                           ('add_host', {'hostname': 'host1',
                                         'status': 'Ready',
                                         'locked': True},
                            True, 42),
                           ('host_add_labels', {'id': 'host1',
                                                'labels': ['label0']},
                            True, None),
                           ('add_host', {'hostname': 'host0',
                                         'status': 'Ready',
                                         'locked': True},
                            True, 42),
                           ('host_add_labels', {'id': 'host0',
                                                'labels': ['label0']},
                            True, None),
                           ('acl_group_add_hosts',
                            {'id': 'acl0', 'hosts': ['host1', 'host0']},
                            True, None)],
                     out_words_ok=['host0', 'host1'])


    def test_execute_create_muliple_hosts_unlocked(self):
        self.run_cmd(argv=['atest', 'host', 'create',
                           '-b', 'label0', '--acls', 'acl0', 'host0', 'host1',
                           '--ignore_site_file'],
                     rpcs=[('get_labels', {'name': 'label0'},
                            True,
                            [{u'id': 4,
                              u'platform': 0,
                              u'name': u'label0',
                              u'invalid': False,
                              u'kernel_config': u''}]),
                           ('get_acl_groups', {'name': 'acl0'},
                            True, []),
                           ('add_acl_group', {'name': 'acl0'},
                            True, 5),
                           ('add_host', {'hostname': 'host1',
                                         'status': 'Ready',
                                         'locked': True},
                            True, 42),
                           ('host_add_labels', {'id': 'host1',
                                                'labels': ['label0']},
                            True, None),
                           ('add_host', {'hostname': 'host0',
                                         'status': 'Ready',
                                         'locked': True},
                            True, 42),
                           ('host_add_labels', {'id': 'host0',
                                                'labels': ['label0']},
                            True, None),
                           ('acl_group_add_hosts',
                            {'id': 'acl0', 'hosts': ['host1', 'host0']},
                            True, None),
                           ('modify_host', {'id': 'host1', 'locked': False},
                            True, None),
                           ('modify_host', {'id': 'host0', 'locked': False},
                            True, None)],
                     out_words_ok=['host0', 'host1'])


if __name__ == '__main__':
    unittest.main()
