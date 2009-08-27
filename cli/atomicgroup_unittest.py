#!/usr/bin/python -u

"""Tests for atomicgroup."""

import unittest

import common
from autotest_lib.cli import cli_mock, topic_common, atomicgroup


class atomicgroup_unittest(cli_mock.cli_unittest):
    def setUp(self):
        super(atomicgroup_unittest, self).setUp()


    def run_cmd(self, argv, *args, **kwargs):
        atomicgroup_argv = ['atest', 'atomicgroup'] + argv
        super(atomicgroup_unittest, self).run_cmd(
                argv=atomicgroup_argv, *args, **kwargs)


    atomicgroups = [
                {'name': 'group0',
                 'description': 'description0',
                 'max_number_of_machines': 3,
                 'invalid': True},
                {'name': 'group1',
                 'description': 'description1',
                 'max_number_of_machines': 13,
                 'invalid': False},
                {'name': 'group2',
                 'description': 'description2',
                 'max_number_of_machines': 23,
                 'invalid': False},
            ]


    def test_atomicgroup_list(self):
        valid_groups = [ag for ag in self.atomicgroups if not ag['invalid']]
        self.run_cmd(argv=['list'],
                     rpcs=[('get_atomic_groups', {},
                            True, valid_groups)],
                     out_words_ok=['group1', 'description2', '23', 'True'],
                     out_words_no=['group0', 'description0', 'False'],
                    )


    def test_atomicgroup_list_show_invalid(self):
        self.run_cmd(argv=['list', '--show-invalid'],
                     rpcs=[('get_atomic_groups', {},
                            True, self.atomicgroups)],
                     out_words_ok=['group1', 'description2', '23', 'True'],
                    )


    def test_atomicgroup_create(self):
        self.run_cmd(argv=['create', '-n', '33', '-d', 'Fruits', 'ag-name'],
                     rpcs=[('add_atomic_group',
                            dict(name='ag-name', description='Fruits',
                                 max_number_of_machines=33),
                            True, 1)],
                     out_words_ok=['Created', 'atomicgroup', 'ag-name'],
                    )

    def test_atomicgroup_create_longargs(self):
        self.run_cmd(argv=['create', '--max_number_of_machines', '33',
                           '--description', 'Fruits', 'ag-name'],
                     rpcs=[('add_atomic_group',
                            dict(name='ag-name', description='Fruits',
                                 max_number_of_machines=33),
                            True, 1)],
                     out_words_ok=['Created', 'atomicgroup', 'ag-name'],
                    )


    def test_atomicgroup_delete(self):
        self.run_cmd(argv=['delete', 'ag-name'],
                     rpcs=[('delete_atomic_group', dict(id='ag-name'),
                            True, None)],
                     out_words_ok=['Deleted', 'atomicgroup', 'ag-name'],
                    )


    def test_atomicgroup_add(self):
        self.run_cmd(argv=['add', '--label', 'One', 'ag-name'],
                     rpcs=[('atomic_group_add_labels',
                            dict(id='ag-name', labels=['One']),
                            True, None)],
                     out_words_ok=['Added', 'atomicgroup', 'ag-name'],
                    )

    def test_atomicgroup_remove(self):
        self.run_cmd(argv=['remove', '--label', 'One', 'ag-name'],
                     rpcs=[('atomic_group_remove_labels',
                            dict(id='ag-name', labels=['One']),
                            True, None)],
                     out_words_ok=['Removed', 'atomicgroup', 'ag-name'],
                    )


if __name__ == '__main__':
    unittest.main()
