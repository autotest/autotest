#!/usr/bin/python2.4

import unittest
import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend import setup_test_environment
from autotest_lib.new_tko.tko import csv_encoder

class CsvEncodingTest(unittest.TestCase):
    def _make_request(self, method, columns=None):
        request = dict(method=method)
        if columns:
            request['columns'] = columns
        return request


    def _make_group(self, header_indices, pass_count, complete_count,
                    incomplete_count=0):
        return dict(header_indices=header_indices, pass_count=pass_count,
                    complete_count=complete_count,
                    incomplete_count=incomplete_count)


    def _encode_and_check_result(self, request, result, *expected_csv_rows):
        encoder = csv_encoder.encoder(request, result)
        response = encoder.encode()
        csv_result = response.content
        expected_csv = '\r\n'.join(expected_csv_rows) + '\r\n'
        self.assertEquals(csv_result, expected_csv)


    def test_spreadsheet_encoder(self):
        request = self._make_request('get_status_counts')
        response = {'header_values' :
                        [[('row1',), ('row2',), ('comma,header',)],
                         [('col1', 'sub1'), ('col1', 'sub2'),
                          ('col2', 'sub1')]],
                    'groups' : [self._make_group((0, 0), 1, 2),
                                self._make_group((1, 2), 3, 4, 5)]}

        self._encode_and_check_result(request, response,
                                      ',col1/sub1,col1/sub2,col2/sub1',
                                      'row1,1 / 2,,',
                                      'row2,,,3 / 4 (5 incomplete)',
                                      '"comma,header",,,')


    def test_table_encoder(self):
        request = self._make_request('get_test_views', [['col1', 'Column 1'],
                                                        ['col2', 'Column 2']])
        response = [{'col1' : 'foo', 'col2' : 'bar'},
                    {'col1' : 'baz', 'col2' : 'asdf'}]
        self._encode_and_check_result(request, response,
                                      'Column 1,Column 2',
                                      'foo,bar',
                                      'baz,asdf')


    def test_grouped_table_encoder(self):
        request = self._make_request('get_group_counts',
                                     [['col1', 'Column 1'],
                                      ['group_count', 'Count in group']])
        response = {'header_values' : 'unused',
                    'groups' : [{'col1' : 'foo', 'group_count' : 1},
                                {'col1' : 'baz', 'group_count' : 3}]}
        self._encode_and_check_result(request, response,
                                      'Column 1,Count in group',
                                      'foo,1',
                                      'baz,3')


    def _status_count_dict(self, col1_value, pass_count, complete_count,
                                  incomplete_count):
        return dict(col1=col1_value, pass_count=pass_count,
                    complete_count=complete_count,
                    incomplete_count=incomplete_count)


    def test_status_count_table_encoder(self):
        request = self._make_request('get_status_counts',
                                     [['col1', 'Column 1'],
                                      ['_unused_', 'Test pass rate']])
        response = {'header_values' : 'unused',
                    'groups' : [self._status_count_dict('foo', 1, 2, 0),
                                self._status_count_dict('baz', 4, 5, 6)]}
        self._encode_and_check_result(request, response,
                                      'Column 1,Test pass rate',
                                      'foo,1 / 2',
                                      'baz,4 / 5 (6 incomplete)')


    def test_extra_info_spreadsheet_encoder(self):
        request = self._make_request('get_latest_tests')


        group1 = self._make_group((0, 0), 1, 1)
        group2 = self._make_group((1, 0), 1, 1)

        group1['extra_info'] = ['info1', 'info2']
        group2['extra_info'] = ['', 'info3']

        response = {'header_values' :
                        [[('row1',), ('row2',)],
                         [('col1',), ('col2',)]],
                    'groups' : [group1, group2]}

        self._encode_and_check_result(request, response,
                                      ',col1,col2',
                                      'row1,"1 / 1\ninfo1\ninfo2",',
                                      'row2,"1 / 1\n\ninfo3",')


    def test_unhandled_method(self):
        request = self._make_request('foo')
        self._encode_and_check_result(request, None,
                                      'Unhandled method foo (this indicates a '
                                      'bug)')


if __name__ == '__main__':
    unittest.main()
